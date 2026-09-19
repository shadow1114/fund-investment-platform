from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories, PortfolioRepository


class _PortfolioRows(PortfolioRepository):
    def _list_rows(self, **_: object) -> list[Mapping[str, object]]:
        return [
            {
                "portfolio_id": "P-2",
                "portfolio_name": "Beta",
                "portfolio_type": "MODEL",
                "status": "ACTIVE",
                "base_currency": "CNY",
                "portfolio_version": "v1",
                "owner_user_id": "other-user",
            },
            {
                "portfolio_id": "P-1",
                "portfolio_name": "Alpha",
                "portfolio_type": "MODEL",
                "status": "ACTIVE",
                "base_currency": "CNY",
                "portfolio_version": "v1",
                "owner_user_id": "current-user",
                "risk_profile": "BALANCED",
                "portfolio_benchmark": {},
                "portfolio_rule_version": "rules-v1",
            },
        ]

    def _get_row(self, identifier: str) -> Mapping[str, object] | None:
        return next((row for row in self._list_rows() if row["portfolio_id"] == identifier), None)


def test_portfolio_list_filters_by_principal_and_paginates() -> None:
    app = create_app()
    repositories = ApiRepositories.from_session(object())
    app.dependency_overrides[get_api_repositories] = lambda: replace(
        repositories, portfolios=_PortfolioRows(object())
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/portfolios",
            params={"page": 1, "page_size": 1},
            headers={"X-User-ID": "current-user"},
        )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "portfolio_id": "P-1",
            "portfolio_name": "Alpha",
            "portfolio_type": "MODEL",
            "status": "ACTIVE",
            "base_currency": "CNY",
            "portfolio_version": "v1",
        }
    ]
    assert response.json()["meta"]["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 1,
        "total_pages": 1,
    }


def test_portfolio_detail_returns_contract_fields() -> None:
    app = create_app()
    repositories = ApiRepositories.from_session(object())
    app.dependency_overrides[get_api_repositories] = lambda: replace(
        repositories, portfolios=_PortfolioRows(object())
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/portfolios/P-1", headers={"X-User-ID": "current-user"})

    assert response.status_code == 200
    assert response.json()["data"]["risk_profile"] == "BALANCED"
    assert response.json()["data"]["portfolio_rule_version"] == "rules-v1"
