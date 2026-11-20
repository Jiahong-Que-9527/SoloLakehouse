"""The container entrypoint must build offline: the GCP adapter's client is
lazy, so constructing the default app never touches BigQuery."""


def test_default_app_is_constructible_offline():
    from energy_api.asgi import app

    assert app.title == "Energy Analytics API"
