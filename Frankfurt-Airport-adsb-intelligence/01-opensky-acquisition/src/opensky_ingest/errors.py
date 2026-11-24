"""Error types shared across the tool."""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH_REQUIRED = 75  # EX_TEMPFAIL: log in, then run the same command again


class IngestError(RuntimeError):
    """Base class for expected, reportable failures."""


class AuthRequired(IngestError):
    """The OpenSky session is missing or expired. Run `login`."""


class SourceError(IngestError):
    """The source rejected or failed a query."""

    def __init__(self, error_class: str, message: str = "") -> None:
        super().__init__(f"{error_class}: {message}" if message else error_class)
        self.error_class = error_class
