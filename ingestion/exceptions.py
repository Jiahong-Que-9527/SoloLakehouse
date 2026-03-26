"""Custom exceptions for ingestion and pipeline step failures."""


class CollectorUnavailableError(Exception):
    """Raised when a data source is unreachable after all retries."""


class StepError(Exception):
    """Raised when a pipeline step fails. Wraps original exception."""

    def __init__(self, step_number: int, step_name: str, original: Exception):
        self.step_number = step_number
        self.step_name = step_name
        self.original = original
        super().__init__(f"Step {step_number} ({step_name}) failed: {original}")
