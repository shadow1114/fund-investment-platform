from fip.api.app import create_app
from fip.settings import Settings


def test_create_app_accepts_settings_override(monkeypatch):
    monkeypatch.setattr("fip.api.app.create_api_engine", lambda _: object())
    runtime = Settings(database_url="postgresql+psycopg://example/fip")

    app = create_app(settings_override=runtime)

    assert app.state.settings is runtime
