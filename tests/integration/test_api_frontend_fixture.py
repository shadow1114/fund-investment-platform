import pytest
from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories


@pytest.mark.integration
def test_frontend_smoke_contract_against_local_app() -> None:
    app = create_app()
    app.dependency_overrides[get_api_repositories] = lambda: ApiRepositories.from_session(object())
    with TestClient(app) as client:
        assert client.get("/api/v1/session").status_code == 200
        assert client.get("/api/v1/funds").status_code == 200
        assert client.get("/api/v1/portfolios").status_code == 200
        assert client.get("/api/v1/operations/missing").status_code == 404
