import hashlib
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from urllib.error import URLError

import pytest

from energy_pipeline.cli import main
from energy_pipeline.download import (
    ENDPOINT,
    ROBOTS,
    Client,
    DownloadError,
    Response,
    cache_lock,
    request_form,
)
from energy_pipeline.normalize import Window
from test_normalize import encode, sample_rows

WINDOW = Window.from_dates("2026-06-08", "2026-06-09")


class FakeServer:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.now = datetime(2026, 11, 17, tzinfo=UTC).timestamp()
        self.waits = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def send(self, method, url, payload):
        self.calls.append((method, url, payload, self.now))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def client(self, cache):
        return Client(cache, send=self.send, clock=self.clock, sleep=self.sleep)


def csv_response():
    return Response(200, {"content-type": "text/csv"}, encode(sample_rows()))


def test_download_retains_raw_and_cache_avoids_all_network_calls(tmp_path):
    server = FakeServer(Response(404, {}, b""), csv_response())
    first = server.client(tmp_path).download(WINDOW)
    original = first.csv_path.read_bytes()
    manifest = json.loads(first.manifest_path.read_text())
    assert first.cached is False
    assert original == encode(sample_rows())
    assert manifest["input_sha256"] == hashlib.sha256(original).hexdigest()
    assert manifest["request"] == request_form(WINDOW)
    assert manifest["license"] == "CC-BY-4.0"
    assert manifest["robots_http_status"] == 404
    assert manifest["quality_status"] == "not_validated"
    assert [call[:2] for call in server.calls] == [("GET", ROBOTS), ("POST", ENDPOINT)]
    assert server.calls[1][3] - server.calls[0][3] >= 5
    second = server.client(tmp_path).download(WINDOW)
    assert second.cached is True
    assert second.csv_path == first.csv_path
    assert len(server.calls) == 2
    assert second.csv_path.read_bytes() == original


def test_request_uses_utc_boundaries_for_dst_and_fixed_load_metric():
    form = request_form(Window.from_dates("2026-10-25", "2026-10-26"))["request_form"][0]
    assert form["moduleIds"] == [5000410]
    assert form["region"] == "DE"
    assert form["resolution"] == "quarterhour"
    assert form["timestamp_from"] == int(datetime(2026, 10, 24, 22, tzinfo=UTC).timestamp() * 1000)
    assert form["timestamp_to"] - form["timestamp_from"] == 25 * 60 * 60 * 1000


@pytest.mark.parametrize(
    "start,until",
    [
        ("2026-06-01", "2026-07-03"),
        ("2099-06-08", "2099-06-09"),
    ],
)
def test_unsupported_windows_make_no_requests(tmp_path, start, until):
    server = FakeServer()
    with pytest.raises(DownloadError):
        server.client(tmp_path).download(Window.from_dates(start, until))
    assert server.calls == []
    assert not list(tmp_path.iterdir())


def test_robots_denial_stops_before_export_and_persists_policy(tmp_path):
    server = FakeServer(Response(200, {}, b"User-agent: *\nDisallow: /nip-download-manager/\n"))
    for _ in range(2):
        with pytest.raises(DownloadError, match="robots.txt disallows"):
            server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 1


def test_robots_crawl_delay_is_observed(tmp_path):
    server = FakeServer(Response(200, {}, b"User-agent: *\nCrawl-delay: 20\n"), csv_response())
    server.client(tmp_path).download(WINDOW)
    assert server.waits == [20]


@pytest.mark.parametrize("status", [401, 403])
def test_denial_is_not_retried_even_by_new_client(tmp_path, status):
    server = FakeServer(Response(404, {}, b""), Response(status, {}, b"denied"))
    with pytest.raises(DownloadError, match="access denied"):
        server.client(tmp_path).download(WINDOW)
    with pytest.raises(DownloadError, match="denied access previously"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2
    assert not list(tmp_path.glob("*/source.csv"))


@pytest.mark.parametrize("retry_after", ["120", "http-date", None, "bad header"])
def test_429_records_cooldown_and_prevents_new_process_retry(tmp_path, retry_after):
    server = FakeServer()
    if retry_after == "http-date":
        retry_after = format_datetime(datetime.fromtimestamp(server.now + 300, UTC), usegmt=True)
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    server.responses = [Response(404, {}, b""), Response(429, headers, b"")]
    with pytest.raises(DownloadError, match="cooldown recorded"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2
    state = json.loads((tmp_path / ".download-state.json").read_text())
    assert state["blocked_until"] >= server.now + 120
    with pytest.raises(DownloadError, match="cooldown until"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2


def test_503_retry_after_stops_without_shortening_wait(tmp_path):
    server = FakeServer(Response(404, {}, b""), Response(503, {"Retry-After": "600"}, b""))
    with pytest.raises(DownloadError, match="cooldown recorded"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2
    assert server.waits == [5]


def test_temporary_server_errors_have_bounded_backoff(tmp_path):
    server = FakeServer(
        Response(404, {}, b""), Response(502, {}, b""), Response(503, {}, b""), csv_response()
    )
    assert server.client(tmp_path).download(WINDOW).cached is False
    assert server.waits == [5, 10, 20]
    assert len(server.calls) == 4


def test_persistent_server_error_stops_after_three_export_attempts(tmp_path):
    server = FakeServer(Response(404, {}, b""), *[Response(503, {}, b"")] * 3)
    with pytest.raises(DownloadError, match="HTTP 503"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 4


@pytest.mark.parametrize("status", [301, 302, 307, 400, 404, 500])
def test_no_redirect_or_endpoint_fallback(tmp_path, status):
    server = FakeServer(
        Response(404, {}, b""), Response(status, {"location": "https://other"}, b"")
    )
    with pytest.raises(DownloadError, match=f"HTTP {status}"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2


@pytest.mark.parametrize("error", [TimeoutError("timeout"), URLError("network")])
def test_uncertain_post_is_not_blindly_resent(tmp_path, error):
    server = FakeServer(Response(404, {}, b""), error)
    with pytest.raises(DownloadError, match="no automatic resend"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2


def test_corrupt_cached_bytes_fail_without_downloading_again(tmp_path):
    server = FakeServer(Response(404, {}, b""), csv_response())
    result = server.client(tmp_path).download(WINDOW)
    result.csv_path.write_bytes(b"damaged")
    with pytest.raises(DownloadError, match="no automatic refetch"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 2


@pytest.mark.parametrize("body", [b"<html>Access denied</html>", b"\xff", b"unexpected;columns"])
def test_changed_export_does_not_commit_cache(tmp_path, body):
    server = FakeServer(Response(404, {}, b""), Response(200, {}, body))
    with pytest.raises(DownloadError):
        server.client(tmp_path).download(WINDOW)
    assert not list(tmp_path.glob("*/source.csv"))


def test_robots_outage_and_html_fail_closed(tmp_path):
    server = FakeServer(Response(200, {}, b"<html>blocked</html>"))
    with pytest.raises(DownloadError, match="robots.txt returned HTML"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 1


def test_lock_stops_second_downloader(tmp_path):
    server = FakeServer()
    with cache_lock(tmp_path), pytest.raises(DownloadError, match="cache lock"):
        server.client(tmp_path).download(WINDOW)
    assert server.calls == []


def test_cli_download_normalizes_and_reuses_cache(tmp_path, monkeypatch, capsys):
    server = FakeServer(Response(404, {}, b""), csv_response())
    monkeypatch.setattr("energy_pipeline.download.Client", lambda cache: server.client(cache))
    args = [
        "download",
        "--from",
        "2026-06-08",
        "--until",
        "2026-06-09",
        "--cache",
        str(tmp_path / "downloads"),
        "--normalize-output",
        str(tmp_path / "output"),
    ]
    assert main(args) == 0
    assert main(args) == 0
    manifests = [json.loads(p.read_text()) for p in (tmp_path / "output").glob("*/manifest.json")]
    assert len(manifests) == 2
    assert manifests[0]["retrieved_at"] == manifests[1]["retrieved_at"]
    assert manifests[0]["output_sha256"] == manifests[1]["output_sha256"]
    assert manifests[0]["row_count"] == 96
    assert len(server.calls) == 2
    assert '"cached": true' in capsys.readouterr().out


def test_source_manifest_mismatch_fails_before_normalization(tmp_path, capsys):
    server = FakeServer(Response(404, {}, b""), csv_response())
    result = server.client(tmp_path / "downloads").download(WINDOW)
    result.csv_path.write_bytes(result.csv_path.read_bytes() + b"\n")
    assert (
        main(
            [
                "normalize",
                "--input",
                str(result.csv_path),
                "--from",
                "2026-06-08",
                "--until",
                "2026-06-09",
                "--output",
                str(tmp_path / "output"),
                "--source-manifest",
                str(result.manifest_path),
            ]
        )
        == 1
    )
    assert "source manifest input_sha256" in capsys.readouterr().err
    assert not (tmp_path / "output").exists()


def test_request_pacing_survives_new_client(tmp_path):
    server = FakeServer(Response(404, {}, b""), csv_response(), csv_response())
    server.client(tmp_path).download(WINDOW)
    server.client(tmp_path).download(
        Window(WINDOW.start + timedelta(days=1), WINDOW.end + timedelta(days=1))
    )
    assert len(server.calls) == 3  # robots reused, second export still paced
    assert server.calls[2][3] - server.calls[1][3] >= 5


@pytest.mark.parametrize(
    "state",
    [
        [],
        {"next_request_at": "bad"},
        {"robots": {}},
        {"access_denied": "false"},
        {"robots": {"http_status": 200}},
    ],
)
def test_corrupt_state_fails_without_requests(tmp_path, state):
    (tmp_path / ".download-state.json").write_text(json.dumps(state))
    server = FakeServer()
    with pytest.raises(DownloadError, match="invalid download state"):
        server.client(tmp_path).download(WINDOW)
    assert server.calls == []


def test_robots_request_rate_does_not_get_shortened(tmp_path):
    server = FakeServer(Response(200, {}, b"User-agent: *\nRequest-rate: 1/60\n"))
    with pytest.raises(DownloadError, match="longer wait"):
        server.client(tmp_path).download(WINDOW)
    assert len(server.calls) == 1
