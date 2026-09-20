from pathlib import Path

from fip.settings import Settings


def test_production_defaults_require_verified_identity(monkeypatch):
    monkeypatch.setenv("FIP_ENV", "production")
    monkeypatch.delenv("FIP_REQUIRE_VERIFIED_PRINCIPAL", raising=False)

    settings = Settings()

    assert settings.require_verified_principal is True


def test_worker_dev_command_is_local_and_not_containerized():
    makefile = Path("Makefile").read_text()

    target = makefile.split("worker-dev:", 1)[1].split("\n\n", 1)[0]
    assert "worker-dev:" in makefile
    assert "fip.platform.jobs.worker" in target
    assert "docker" not in target
