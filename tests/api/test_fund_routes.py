from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from fastapi.testclient import TestClient

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.fund_queries import _matches
from fip.api.repositories import ApiRepositories, FundRepository


class _SeededFundRepository(FundRepository):
    """A request-scoped fake whose data is deliberately out of display order."""

    def __init__(self) -> None:
        super().__init__(object())
        self.list_filters: dict[str, object] | None = None
        self.rows = [
            {
                "fund_id": "fund-3",
                "fund_code": "000003",
                "fund_name": "Beta",
                "share_class": "A",
                "share_class_id": "3",
                "fund_company": "Company Two",
                "sub_status": "开放",
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
                "fund_code": "000002",
                "fund_name": "Alpha",
                "share_class": "C",
                "share_class_id": "2",
                "fund_company": "Company One",
                "sub_status": "开放",
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
                "fund_code": "000001",
                "fund_name": "Alpha",
                "share_class": "A",
                "share_class_id": "1",
                "fund_company": "Company One",
                "sub_status": "开放",
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

    def list_page(self, *, page: int, page_size: int, sort: str | None, order: str, **filters):
        self.list_filters = filters
        rows = [
            row
            for row in self.rows
            if _matches(row, filters)
            and (not filters.get("fund_code") or row.get("fund_code") == filters["fund_code"])
            and (
                not filters.get("fund_company")
                or row.get("fund_company") == filters["fund_company"]
            )
            and (not filters.get("sub_status") or row.get("sub_status") == filters["sub_status"])
        ]
        field = (
            sort
            if sort
            in {"fund_code", "fund_name", "fund_company", "sub_status", "inception_date", "aum"}
            else "fund_name"
        )
        rows.sort(key=lambda row: str(row.get("fund_id", "")))
        rows.sort(key=lambda row: str(row.get(field) or ""), reverse=order == "desc")
        offset = (page - 1) * page_size
        selected = rows[offset : offset + page_size]
        return [
            {key: value for key, value in row.items() if key != "aum"}
            for row in selected
        ], len(rows)

    def list_management_companies(self, *, as_of_date: str | None = None) -> list[str]:
        _ = as_of_date
        return sorted({str(row["fund_company"]) for row in self.rows if row.get("fund_company")})

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

    def read_live_factor_analysis(self, identifier: str, **filters: object) -> Mapping[str, object]:
        assert identifier == "fund-1"
        assert filters == {"evaluation_period": "5Y", "as_of_date": "2025-01-31"}
        return {
            "data": {
                "fund_id": identifier,
                "evaluation_period": "5Y",
                "as_of_date": "2025-01-31",
                "factor_categories": [],
            },
            "meta": {"calculation_mode": "ON_DEMAND"},
        }


def _client(
    repository: FundRepository,
    *,
    strict_contracts: bool = False,
    raise_server_exceptions: bool = True,
) -> TestClient:
    app = create_app(strict_contracts=strict_contracts)
    repositories = ApiRepositories.from_session(object())
    app.dependency_overrides[get_api_repositories] = lambda: replace(repositories, funds=repository)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


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
        "fund_code": None,
        "fund_company": None,
        "sub_status": None,
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


def test_fund_list_accepts_code_company_status_and_page_size_200() -> None:
    repository = _SeededFundRepository()

    response = _client(repository).get(
        "/api/v1/funds",
        params={
            "fund_code": "000001",
            "fund_company": "Company One",
            "sub_status": "开放",
            "page_size": 200,
            "sort": "fund_company",
        },
    )

    assert response.status_code == 200
    assert [row["fund_id"] for row in response.json()["data"]] == ["fund-1"]
    assert response.json()["data"][0]["share_class_id"] == "1"
    assert response.json()["data"][0]["fund_code"] == "000001"
    assert response.json()["meta"]["pagination"]["page_size"] == 200
    assert response.json()["meta"]["subscription_status_source"] == "PLACEHOLDER"
    assert repository.list_filters is not None
    assert repository.list_filters["fund_code"] == "000001"
    assert repository.list_filters["fund_company"] == "Company One"
    assert repository.list_filters["sub_status"] == "开放"


def test_fund_list_defaults_to_twenty_rows() -> None:
    response = _client(_SeededFundRepository()).get("/api/v1/funds")

    assert response.status_code == 200
    assert response.json()["meta"]["pagination"]["page_size"] == 20


def test_fund_name_filter_trims_surrounding_whitespace() -> None:
    repository = _SeededFundRepository()

    response = _client(repository).get("/api/v1/funds", params={"fund_name": "  Alpha  "})

    assert response.status_code == 200
    assert {row["fund_id"] for row in response.json()["data"]} == {"fund-1", "fund-2"}
    assert repository.list_filters is not None
    assert repository.list_filters["fund_name"] == "Alpha"


def test_fund_list_unknown_asset_filter_keeps_no_snapshot_rows() -> None:
    repository = _SeededFundRepository()
    repository.rows = [{**row, "classification": None} for row in repository.rows]

    response = _client(repository).get("/api/v1/funds?asset_class=UNKNOWN")

    assert response.status_code == 200
    assert {row["fund_id"] for row in response.json()["data"]} == {
        "fund-1",
        "fund-2",
        "fund-3",
    }
    assert response.json()["meta"]["pagination"]["total_items"] == 3


def test_fund_list_rejects_bad_code_and_non_placeholder_subscription_status() -> None:
    client = _client(_SeededFundRepository())

    assert client.get("/api/v1/funds", params={"fund_code": "１２３４５６"}).status_code == 422
    assert client.get("/api/v1/funds", params={"fund_code": "12345x"}).status_code == 422
    assert client.get("/api/v1/funds", params={"fund_code": " 123456 "}).status_code == 422
    assert client.get("/api/v1/funds", params={"sub_status": "暂停"}).status_code == 422


def test_fund_management_company_options_have_standard_envelope_and_optional_as_of_date() -> None:
    response = _client(_SeededFundRepository()).get(
        "/api/v1/fund-management-companies", params={"as_of_date": "2025-01-31"}
    )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"fund_company": "Company One"},
        {"fund_company": "Company Two"},
    ]
    assert response.json()["meta"]["as_of_date"] == "2025-01-31"
    assert response.json()["meta"]["is_point_in_time"] is True


def test_fund_list_and_company_options_pass_strict_runtime_contracts() -> None:
    repository = _SeededFundRepository()
    fund_without_company = next(row for row in repository.rows if row["fund_id"] == "fund-1")
    fund_without_company.update(
        fund_company=None,
        management_company_id=None,
        fund_classification="UNKNOWN",
        classification=None,
    )
    client = _client(repository, strict_contracts=True)

    funds = client.get("/api/v1/funds", params={"page_size": 20})
    companies = client.get("/api/v1/fund-management-companies")

    assert funds.status_code == 200
    assert funds.json()["data"][0]["share_class_id"] == "1"
    assert funds.json()["data"][0]["fund_classification"] == "UNKNOWN"
    assert funds.json()["data"][0].get("fund_company") is None
    assert funds.json()["data"][0].get("management_company_id") is None
    assert funds.json()["meta"]["subscription_status_source"] == "PLACEHOLDER"
    assert companies.status_code == 200
    assert companies.json()["data"] == [
        {"fund_company": "Company One"},
        {"fund_company": "Company Two"},
    ]


def test_strict_list_endpoint_rejects_unmodeled_payload_fields() -> None:
    repository = _SeededFundRepository()
    repository.rows[0]["unexpected_field"] = "must not escape the strict contract"
    client = _client(
        repository,
        strict_contracts=True,
        raise_server_exceptions=False,
    )

    response = client.get("/api/v1/funds")

    assert response.status_code == 500


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


def test_live_factor_analysis_accepts_period_and_returns_uncached_factor_payload() -> None:
    response = _client(_SeededFundRepository()).get(
        "/api/v1/funds/fund-1/factor-analysis",
        params={"as_of_date": "2025-01-31", "evaluation_period": "5Y"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["evaluation_period"] == "5Y"
    assert response.json()["meta"]["calculation_mode"] == "ON_DEMAND"


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
