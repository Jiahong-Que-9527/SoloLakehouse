def pytest_configure(config: object) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(  # type: ignore[union-attr]
        "markers", "integration: Integration tests requiring live Docker services"
    )
