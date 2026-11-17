"""A bounded client for the CSV export used by SMARD's download centre.

Limits are project safeguards, not SMARD-published request allowances.
All processes using the same cache share a nonblocking lock and persistent
request pacing, robots policy and access-denial/cooldown state.
"""

import csv
import fcntl
import hashlib
import io
import json
import math
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from energy_pipeline.normalize import HEADER, ZONE, Window

ENDPOINT = "https://www.smard.de/nip-download-manager/nip/download/market-data"
ROBOTS = "https://www.smard.de/robots.txt"
USER_AGENT = (
    "SoloLakehouse-energy-pipeline/0.1 (+https://github.com/Jiahong-Que-9527/SoloLakehouse)"
)
MAX_BYTES = 32 * 1024 * 1024
MIN_INTERVAL = 5
POLICY_TTL = 24 * 60 * 60


class DownloadError(ValueError):
    """Stop without bypassing access restrictions or silently refetching."""


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Download:
    csv_path: Path
    manifest_path: Path
    cached: bool


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transport(method: str, url: str, payload: bytes | None) -> Response:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/csv, text/plain, */*"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        response = build_opener(NoRedirect()).open(request, timeout=30)
    except HTTPError as exc:
        response = exc
    with response:
        if response.code != 200:
            # Preserve denial/rate-limit headers even for large error pages.
            return Response(response.code, {k.lower(): v for k, v in response.headers.items()}, b"")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise DownloadError("response exceeds the 32 MiB project limit; stopped")
        return Response(response.code, {k.lower(): v for k, v in response.headers.items()}, body)


def request_form(window: Window) -> dict:
    start = window.start.astimezone(ZONE).date()
    until = window.end.astimezone(ZONE).date()
    if not 1 <= (until - start).days <= 31:
        raise DownloadError("download window must be 1 to 31 local days")
    if window.end > datetime.now(UTC):
        raise DownloadError("download window must end in the past")
    # The official form converts its inclusive selected end day to the next
    # local midnight. Our CLI already takes that exclusive midnight.
    return {
        "request_form": [
            {
                "moduleIds": [5000410],
                "region": "DE",
                "resolution": "quarterhour",
                "format": "CSV",
                "timestamp_from": int(window.start.timestamp() * 1000),
                "timestamp_to": int(window.end.timestamp() * 1000),
                "type": "discrete",
                "language": "de",
            }
        ]
    }


def save_json(path: Path, data: dict) -> None:
    """Replace small state atomically while holding the cache lock."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".state-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def cache_lock(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / ".download.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DownloadError("another downloader holds this cache lock; try later") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Client:
    def __init__(self, cache: Path, *, send=transport, clock=time.time, sleep=time.sleep):
        self.cache = cache
        self.send, self.clock, self.sleep = send, clock, sleep
        self.state_path = cache / ".download-state.json"
        self.state = {}

    def _save(self):
        save_json(self.state_path, self.state)

    def _load(self):
        self.state = {}
        if not self.state_path.exists():
            return
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                raise ValueError("expected object")
            for field in ("next_request_at", "blocked_until", "crawl_delay"):
                value = state.get(field, 0)
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError("invalid pacing state")
            if type(state.get("access_denied", False)) is not bool:
                raise ValueError("invalid denial state")
            if robots := state.get("robots"):
                if (
                    not isinstance(robots, dict)
                    or robots["http_status"] not in (200, 404)
                    or not isinstance(robots["text"], str)
                    or type(robots["checked_at"]) not in (int, float)
                    or not math.isfinite(robots["checked_at"])
                ):
                    raise ValueError("invalid robots state")
            elif "robots" in state:
                raise ValueError("invalid robots state")
            self.state = state
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise DownloadError("invalid download state; stopped for review") from exc

    def _retry_after(self, header: str | None, fallback: int) -> float:
        if header:
            try:
                if header.isascii() and header.isdigit():
                    return max(MIN_INTERVAL, int(header))
                parsed = parsedate_to_datetime(header)
                if parsed.tzinfo is not None:
                    return max(MIN_INTERVAL, parsed.timestamp() - self.clock())
            except (ValueError, TypeError, OverflowError):
                pass
        return fallback

    def _request(self, method, url, payload=None, *, allow_404=False):
        for attempt in range(3):
            if self.state.get("access_denied"):
                raise DownloadError("provider denied access previously; review with the provider")
            blocked = self.state.get("blocked_until", 0)
            if blocked > self.clock():
                raise DownloadError(f"provider cooldown until Unix time {blocked}; no request sent")
            delay = max(0, self.state.get("next_request_at", 0) - self.clock())
            if delay > 30:
                raise DownloadError("request pacing requires a longer wait; try later")
            if delay:
                self.sleep(delay)
            interval = max(MIN_INTERVAL, self.state.get("crawl_delay", 0))
            self.state["next_request_at"] = self.clock() + interval
            self._save()
            try:
                response = self.send(method, url, payload)
            except (URLError, TimeoutError, OSError) as exc:
                # A timed-out POST might already have been processed; no blind resend.
                raise DownloadError(f"network request failed; no automatic resend: {exc}") from exc
            headers = {k.lower(): v for k, v in response.headers.items()}
            if response.status in (401, 403):
                self.state["access_denied"] = True
                self._save()
                raise DownloadError(f"HTTP {response.status}: access denied; stopped")
            if response.status == 429 or "retry-after" in headers:
                wait = self._retry_after(headers.get("retry-after"), 3600)
                self.state["blocked_until"] = self.clock() + wait
                self._save()
                raise DownloadError(
                    f"HTTP {response.status}: cooldown recorded; no automatic retry"
                )
            if response.status in (502, 503, 504) and attempt < 2:
                self.state["next_request_at"] = max(
                    self.state["next_request_at"], self.clock() + 10 * 2**attempt
                )
                self._save()
                continue
            if response.status == 200 or (allow_404 and response.status == 404):
                return response
            raise DownloadError(
                f"HTTP {response.status}: stopped; no redirect or endpoint fallback"
            )
        raise AssertionError("unreachable")

    def _robots(self):
        cached = self.state.get("robots")
        if cached is None or self.clock() - cached["checked_at"] >= POLICY_TTL:
            response = self._request("GET", ROBOTS, allow_404=True)
            try:
                text = response.body.decode("utf-8-sig") if response.status == 200 else ""
            except UnicodeDecodeError as exc:
                raise DownloadError("robots.txt is not UTF-8; stopped for review") from exc
            if response.status == 200 and text.lstrip().lower().startswith("<"):
                raise DownloadError("robots.txt returned HTML; stopped for review")
            cached = {"checked_at": self.clock(), "http_status": response.status, "text": text}
            self.state["robots"] = cached
            self._save()
        parser = RobotFileParser(ROBOTS)
        parser.parse(cached["text"].splitlines())
        if not parser.can_fetch(USER_AGENT, ENDPOINT):
            raise DownloadError("robots.txt disallows this export path; stopped")
        self.state["crawl_delay"] = max(MIN_INTERVAL, parser.crawl_delay(USER_AGENT) or 0)
        if rate := parser.request_rate(USER_AGENT):
            self.state["crawl_delay"] = max(
                self.state["crawl_delay"], math.ceil(rate.seconds / rate.requests)
            )
        self.state["next_request_at"] = max(
            self.state.get("next_request_at", 0),
            cached["checked_at"] + self.state["crawl_delay"],
        )
        self._save()

    def download(self, window: Window) -> Download:
        form = request_form(window)
        payload = json.dumps(form, sort_keys=True, separators=(",", ":")).encode()
        key = hashlib.sha256(payload).hexdigest()
        destination = self.cache / key
        with cache_lock(self.cache):
            if destination.exists():
                return self._cached(destination, form)
            self._load()
            self._robots()
            response = self._request("POST", ENDPOINT, payload)
            # Retain raw bytes, but never mistake an HTML/error page for an export.
            try:
                header = next(
                    csv.reader(io.StringIO(response.body.decode("utf-8-sig")), delimiter=";"), None
                )
            except (UnicodeDecodeError, csv.Error) as exc:
                raise DownloadError("export is not a UTF-8 CSV; stopped") from exc
            if header != HEADER:
                raise DownloadError("export header changed or response is not CSV; stopped")
            manifest = {
                "schema_version": 1,
                "request": form,
                "endpoint": ENDPOINT,
                "retrieved_at": datetime.fromtimestamp(self.clock(), UTC).isoformat(),
                "input_file": "source.csv",
                "input_sha256": hashlib.sha256(response.body).hexdigest(),
                "window_start": window.start.isoformat(),
                "window_end": window.end.isoformat(),
                "source": "smard",
                "metric": "actual_load_mwh",
                "area": "DE",
                "unit": "MWh",
                "interval_minutes": 15,
                "attribution": "Bundesnetzagentur | SMARD.de",
                "source_url": "https://www.smard.de/home/downloadcenter/download-marktdaten",
                "license": "CC-BY-4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "terms_url": "https://www.smard.de/home/impressum",
                "terms_reviewed_on": "2026-11-17",
                "changes": "None; unmodified CSV response bytes.",
                "content_type": response.headers.get("content-type"),
                "robots_checked_at": datetime.fromtimestamp(
                    self.state["robots"]["checked_at"], UTC
                ).isoformat(),
                "robots_http_status": self.state["robots"]["http_status"],
                "quality_status": "not_validated",
            }
            staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.cache))
            try:
                (staging / "source.csv").write_bytes(response.body)
                save_json(staging / "download.json", manifest)
                staging.rename(destination)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            return Download(destination / "source.csv", destination / "download.json", False)

    @staticmethod
    def _cached(destination, form):
        try:
            manifest = json.loads((destination / "download.json").read_text(encoding="utf-8"))
            checksum = hashlib.sha256((destination / "source.csv").read_bytes()).hexdigest()
            if manifest["request"] != form or manifest["input_sha256"] != checksum:
                raise ValueError("request or checksum mismatch")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DownloadError(
                "cached export is incomplete or changed; no automatic refetch"
            ) from exc
        return Download(destination / "source.csv", destination / "download.json", True)
