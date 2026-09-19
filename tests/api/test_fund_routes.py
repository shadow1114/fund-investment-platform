from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories, FundRepository


class _SeededFundRepository(FundRepository):
    """A request-scoped fake whose data is deliberately out of display order."""

    def __init__(self) -> None:
        super().__init__(object())
        self.list_filters: dict[str, object] | None = None
        self.rows = [
            {
                "fund_id": "fund-3",
                "fund_name": "Beta",
                "share_class": "A",
                "fund_classification": "BOND",
                "management_company_id": "manager-company-2",
                "manager_ids": ["manager-2"],
                "inception_date": "2021-01-01",
                "lifecycle_status": "NORMAL",
                "investment_eligibility": "LIMITED",
                "aum": 30.0,
            },
            {
                "fund_id": "fund-2",
                "fund_name": "Alpha",
                "share_class": "C",
                "fund_classification": "EQUITY",
                "management_company_id": "manager-company-1",
                "manager_ids": ["manager-1"],
                "inception_date": "2020-01-02",
                "lifecycle_status": "NORMAL",
                "investment_eligibility": "FULLY_ELIGIBLE",
                "aum": 20.0,
            },
            {
                "fund_id": "fund-1",
                "fund_name": "Alpha",
                "share_class": "A",
                "fund_classification": "EQUITY",
                "management_company_id": "manager-company-1",
                "manager_ids": ["manager-1"],
                "inception_date": "2019-01-01",
                "lifecycle_status": "NORMAL",
                "investment_eligibility": "FULLY_ELIGIBLE",
                "aum": 10.0,
            },
        ]

    def list(self, **filters: object) -> list[dict[str, object]]:
        self.list_filters = filters
        return list(self.rows)

    def get(self, identifier: str) -> Mapping[str, object]:
        for row in self.rows:
            if row["fund_id"] == identifier:
                return {
                    **row,
                    "classification_version": "classification-v1",
                    "benchmark": {},
                    "fee_structure": [],
                }
        return super().get(identifier)

    def read_detail(self, identifier: str, **filters: object) -> Mapping[str, object]:
        assert filters in ({"as_of_date": "2025-01-31"}, {"as_of_date": None})
        return self.get(identifier)

    def read_nav_series(self, identifier: str, **filters: object) -> Mapping[str, object]:
        assert identifier == "fund-1"
        assert filters == {
            "date_from": None,
            "date_to": None,
            "frequency": "DAILY",
            "nav_type": "ADJUSTED",
            "as_of_date": "2025-01-31",
        }
        return {
            "data": {"fund_id": identifier, "points": [{"date": "2025-01-01", "nav": 1.2}]},
            "meta": {"adjustment_rule_version": "adjustment-v2", "unavailable_count": 0},
        }

    def read_evaluation(self, identifier: str, **filters: object) -> Mapping[str, object]:
        assert identifier == "fund-1"
        assert filters == {"evaluation_period": "1Y", "as_of_date": "2025-01-31"}
        return {
            "data": {"fund_id": identifier, "evaluation_period": "1Y", "factor_results": []},
            "meta": {"factor_version": "factor-v3"},
        }

    def read_scores(self, identifier: str, **filters: object) -> Mapping[str, object]:
        assert identifier == "fund-1"
        assert filters == {"evaluation_period": "1Y", "as_of_date": "2025-01-31"}
        return {
            "data": {"fund_id": identifier, "evaluation_period": "1Y", "attribution": []},
            "meta": {"scoring_policy_version": "score-v4"},
        }


def _client(repository: FundRepository) -> TestClient:
    app = create_app()
    repositories = ApiRepositories.from_session(object())
    app.dependency_overrides[get_api_repositories] = lambda: replace(repositories, funds=repository)
    return TestClient(app)


def test_fund_list_filters_paginates_and_breaks_name_ties_by_fund_id() -> None:
    """Dropping a filter or stable ID tiebreaker would return the wrong first page."""
    repository = _SeededFundRepository()

    response = _client(repository).get(
        "/api/v1/funds",
        params={
            "fund_type": ["EQUITY"],
            "management_company_id": "manager-company-1",
            "manager_id": "manager-1",
            "lifecycle_status": ["NORMAL"],
            "investment_eligibility": ["FULLY_ELIGIBLE"],
            "inception_date_from": "2019-01-01",
            "inception_date_to": "2020-12-31",
            "aum_min": 1,
            "aum_max": 25,
            "as_of_date": "2025-01-31",
            "page": 1,
            "page_size": 1,
            "sort": "fund_name",
            "order": "asc",
        },
    )

    assert response.status_code == 200
    assert [row["fund_id"] for row in response.json()["data"]] == ["fund-1"]
    assert response.json()["meta"]["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 2,
        "total_pages": 2,
    }
    assert response.json()["meta"]["as_of_date"] == "2025-01-31"
    assert response.json()["meta"]["is_point_in_time"] is True
    assert repository.list_filters == {
        "fund_name": None,
        "fund_type": ("EQUITY",),
        "management_company_id": "manager-company-1",
        "manager_id": "manager-1",
        "lifecycle_status": ("NORMAL",),
        "investment_eligibility": ("FULLY_ELIGIBLE",),
        "inception_date_from": "2019-01-01",
        "inception_date_to": "2020-12-31",
        "aum_min": 1.0,
        "aum_max": 25.0,
        "as_of_date": "2025-01-31",
    }


def test_fund_list_parses_comma_delimited_multi_value_filters() -> None:
    """Treating an explode=false value as one enum would discard valid fund types."""
    repository = _SeededFundRepository()

    response = _client(repository).get("/api/v1/funds?fund_type=EQUITY%2CBOND")

    assert response.status_code == 200
    assert [row["fund_id"] for row in response.json()["data"]] == ["fund-1", "fund-2", "fund-3"]
    assert repository.list_filters is not None
    assert repository.list_filters["fund_type"] == ("EQUITY", "BOND")


def test_fund_detail_and_related_reads_delegate_to_seeded_repository() -> None:
    """Replacing repository reads with placeholder payloads would lose its versions and data."""
    client = _client(_SeededFundRepository())

    detail = client.get("/api/v1/funds/fund-1", params={"as_of_date": "2025-01-31"})
    nav = client.get("/api/v1/funds/fund-1/nav-series", params={"as_of_date": "2025-01-31"})
    evaluation = client.get(
        "/api/v1/funds/fund-1/evaluations",
        params={"as_of_date": "2025-01-31", "evaluation_period": "1Y"},
    )
    scores = client.get(
        "/api/v1/funds/fund-1/scores",
        params={"as_of_date": "2025-01-31", "evaluation_period": "1Y"},
    )

    assert detail.json()["data"]["fund_id"] == "fund-1"
    assert detail.json()["meta"]["is_point_in_time"] is True
    assert nav.json()["data"]["points"] == [{"date": "2025-01-01", "nav": 1.2}]
    assert nav.json()["meta"] == {
        **nav.json()["meta"],
        "as_of_date": "2025-01-31",
        "is_point_in_time": True,
        "nav_type": "ADJUSTED",
        "adjustment_convention": "BACKWARD",
        "adjustment_rule_version": "adjustment-v2",
        "unavailable_count": 0,
    }
    assert evaluation.json()["meta"]["factor_version"] == "factor-v3"
    assert scores.json()["meta"]["scoring_policy_version"] == "score-v4"


def test_fund_routes_reject_invalid_dates_and_enums_and_not_found_ids() -> None:
    """Accepting malformed dates, unknown enum values, or missing IDs breaks the frozen boundary."""
    client = _client(_SeededFundRepository())

    assert client.get("/api/v1/funds", params={"as_of_date": "not-a-date"}).status_code == 422
    assert (
        client.get("/api/v1/funds", params={"lifecycle_status": "NOT_A_STATUS"}).status_code == 422
    )
    assert (
        client.get("/api/v1/funds/fund-1/nav-series", params={"nav_type": "LATEST"}).status_code
        == 422
    )
    assert client.get("/api/v1/funds/missing").status_code == 404


def test_fund_list_rejects_unsupported_sort_and_impossible_ranges() -> None:
    """Silently changing an invalid query to a name sort makes pagination non-reproducible."""
    client = _client(_SeededFundRepository())

    assert client.get("/api/v1/funds", params={"sort": "total_score"}).status_code == 422
    assert (
        client.get(
            "/api/v1/funds",
            params={"inception_date_from": "2021-01-01", "inception_date_to": "2020-01-01"},
        ).status_code
        == 422
    )
    assert client.get("/api/v1/funds", params={"aum_min": 3, "aum_max": 2}).status_code == 422
