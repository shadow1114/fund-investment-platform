from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories, UniverseRepository


class _SeededUniverseRepository(UniverseRepository):
    def __init__(self) -> None:
        super().__init__(object())
        self.list_filters: dict[str, object] | None = None
        self.row = {
            "universe_id": "universe-1",
            "strategy_id": "quality",
            "decision_at": "2025-01-31",
            "universe_strategy": "A",
            "member_count": 1,
            "eligibility_rules_version": "eligibility-v2",
            "scoring_policy_version": "score-v4",
        }

    def list(self, **filters: object) -> list[dict[str, object]]:
        self.list_filters = filters
        return [self.row]

    def get(self, identifier: str) -> Mapping[str, object]:
        if identifier == "universe-1":
            return self.row
        return super().get(identifier)

    def read_members(self, identifier: str) -> Mapping[str, object]:
        assert identifier == "universe-1"
        return {
            "members": [
                {
                    "fund_id": "fund-1",
                    "selection_status": "SELECTED",
                    "passed_conditions": [{"condition": "minimum_aum", "result": "PASS"}],
                    "failed_conditions": [],
                }
            ],
            "excluded": [
                {
                    "fund_id": "fund-2",
                    "selection_status": "REJECTED",
                    "passed_conditions": [],
                    "failed_conditions": [{"condition": "minimum_aum", "result": "FAIL"}],
                }
            ],
            "meta": {
                "eligibility_rules_version": "eligibility-v2",
                "scoring_policy_version": "score-v4",
            },
        }


def _client(repository: UniverseRepository) -> TestClient:
    app = create_app()
    repositories = ApiRepositories.from_session(object())
    app.dependency_overrides[get_api_repositories] = lambda: replace(
        repositories, universes=repository
    )
    return TestClient(app)


def test_universe_list_delegates_frozen_filters_and_returns_repository_metadata() -> None:
    """Dropping snapshot filters would make the response select the wrong universe."""
    repository = _SeededUniverseRepository()

    response = _client(repository).get(
        "/api/v1/fund-universes",
        params={
            "strategy_id": "quality",
            "decision_at": "2025-01-31",
            "eligibility_rules_version": "eligibility-v2",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == [repository.row]
    assert response.json()["meta"]["eligibility_rules_version"] == "eligibility-v2"
    assert response.json()["meta"]["scoring_policy_version"] == "score-v4"
    assert repository.list_filters == {
        "strategy_id": "quality",
        "decision_at": "2025-01-31",
        "eligibility_rules_version": "eligibility-v2",
    }


def test_universe_detail_keeps_selected_and_rejected_members_with_conditions() -> None:
    """Returning only selected members would hide recorded eligibility exclusions."""
    response = _client(_SeededUniverseRepository()).get("/api/v1/fund-universes/universe-1")

    assert response.status_code == 200
    assert response.json()["data"]["members"][0]["selection_status"] == "SELECTED"
    assert response.json()["data"]["excluded"][0]["selection_status"] == "REJECTED"
    assert response.json()["data"]["excluded"][0]["failed_conditions"] == [
        {"condition": "minimum_aum", "result": "FAIL"}
    ]


def test_universe_routes_reject_invalid_dates_and_missing_ids() -> None:
    """Malformed decision dates and absent snapshots must not turn into successful empty data."""
    client = _client(_SeededUniverseRepository())

    assert (
        client.get("/api/v1/fund-universes", params={"decision_at": "not-a-date"}).status_code
        == 422
    )
    assert client.get("/api/v1/fund-universes/missing").status_code == 404
