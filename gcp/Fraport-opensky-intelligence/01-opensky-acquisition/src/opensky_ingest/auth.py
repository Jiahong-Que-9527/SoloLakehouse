"""OpenSky Trino connection with browser-based OAuth2 login.

The login URL is short-lived and private. It is opened in the browser and
written to a private file. It is never printed, logged or put in an exception.
The token cache holds one current token with mode 0600 outside the repository.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import Config
from .errors import AuthRequired
from .trino_client import fetch_all
from .util import write_json_atomic

LOGIN_URL_FILE = "login-url.txt"
TOKEN_FILE = "token.json"


class DiskTokenCache:
    """Token cache with the interface the Trino client expects."""

    def __init__(self, directory: Path) -> None:
        self._path = directory / TOKEN_FILE
        self._directory = directory

    def get_token_from_cache(self, key: str | None) -> str | None:
        try:
            stored = json.loads(self._path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        return stored.get("token") if stored.get("key") == key else None

    def store_token_to_cache(self, key: str | None, token: str) -> None:
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._directory, 0o700)
        write_json_atomic(self._path, {"key": key, "token": token}, mode=0o600)

    def has_token(self) -> bool:
        return self._path.exists()


def open_in_browser(url: str) -> bool:
    """Open `url` in the Windows or Linux browser. Returns True if a launcher ran."""
    launchers: list[list[str]] = []
    # Prefer Chrome: an explicit OPENSKY_BROWSER path, then Windows Chrome under WSL.
    candidates = [os.environ.get("OPENSKY_BROWSER", "")] + [
        str(Path(root) / "Google/Chrome/Application/chrome.exe")
        for root in ("/mnt/c/Program Files", "/mnt/c/Program Files (x86)")
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            launchers.append([candidate, url])
            break
    if shutil.which("wslview"):
        launchers.append(["wslview", url])
    if shutil.which("explorer.exe"):
        launchers.append(["explorer.exe", url])
    if shutil.which("xdg-open"):
        launchers.append(["xdg-open", url])
    for command in launchers:
        try:
            subprocess.Popen(  # noqa: S603 - fixed launcher, URL passed as one argument
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except OSError:
            continue
    return False


def interactive_redirect_handler(
    token_dir: Path, opener: Callable[[str], bool] = open_in_browser
) -> Callable[[str], None]:
    def handler(url: str) -> None:
        token_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = token_dir / LOGIN_URL_FILE
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(url)
        if opener(url):
            print("Complete the OpenSky login in your browser. Waiting for it...", flush=True)
        else:
            print(
                f"No browser could be opened. Open the URL stored in {path} in a browser "
                "on this machine. Waiting for the login...",
                flush=True,
            )

    return handler


def noninteractive_redirect_handler() -> Callable[[str], None]:
    def handler(_url: str) -> None:
        raise AuthRequired("AUTH_REQUIRED: renew the OpenSky session with `login`")

    return handler


def _wait_for_token(login_timeout: int) -> Callable[..., str]:
    """Replacement for the client's token poll: wait up to `login_timeout` seconds."""

    def wait_token(self: Any, token_server: str, response: Any, **kwargs: Any) -> str:
        from requests import Request
        from trino import exceptions

        deadline = time.monotonic() + login_timeout
        while time.monotonic() < deadline:
            with response.connection.send(
                Request(method="GET", url=token_server).prepare(), **kwargs
            ) as pending:
                if pending.status_code != 200:
                    raise exceptions.TrinoAuthError("token endpoint rejected the request")
                body = pending.json()
                if body.get("token"):
                    return body["token"]
                if body.get("error") or not body.get("nextUri"):
                    raise exceptions.TrinoAuthError("login did not complete")
                token_server = body["nextUri"]
            time.sleep(1)
        raise AuthRequired("AUTH_REQUIRED: login timed out")

    return wait_token


def make_connection(cfg: Config, *, interactive: bool) -> Any:
    """Create a Trino connection. Non-interactive mode never starts a login."""
    from trino.auth import OAuth2Authentication
    from trino.dbapi import connect

    token_dir = cfg.paths.token_dir
    handler = (
        interactive_redirect_handler(token_dir)
        if interactive
        else noninteractive_redirect_handler()
    )
    auth = OAuth2Authentication(redirect_auth_url_handler=handler)
    auth._bearer._token_cache = DiskTokenCache(token_dir)
    if interactive:
        auth._bearer._get_token = _wait_for_token(cfg.source.login_timeout_seconds).__get__(
            auth._bearer, type(auth._bearer)
        )
    return connect(
        host=cfg.source.host,
        port=cfg.source.port,
        http_scheme="https",
        user=cfg.username,
        catalog=cfg.source.catalog,
        schema=cfg.source.schema,
        auth=auth,
        request_timeout=30,
        max_attempts=1,
        session_properties={"query_max_run_time": "5m"},
    )


def login(cfg: Config, connection_factory: Callable[..., Any] = make_connection) -> int:
    """Start an interactive login and verify it with a cheap query.

    Returns the number of tables visible to the account.
    """
    connection = connection_factory(cfg, interactive=True)
    try:
        rows, _ = fetch_all(
            connection,
            f"SHOW TABLES FROM {cfg.source.catalog}.{cfg.source.schema}",
            timeout=cfg.source.login_timeout_seconds + 60,
        )
    finally:
        close = getattr(connection, "close", None)
        if close:
            close()
    print(f"OpenSky authentication verified. {len(rows)} tables are visible.", file=sys.stdout)
    return len(rows)
