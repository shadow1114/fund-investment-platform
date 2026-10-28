"""Offline HTTP/schema/query contracts: no engine, database fixture or network."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from fip.api.dependencies import get_api_repositories
from fip.api.errors import ApiError
from fip.api.fund_queries import _matches
from fip.api.routers import classifications, reads
from fip.api.schemas import ClassificationPayloadModel
from fip.services.data_service.classification.models import ClassificationSnapshot
from fip.services.data_service.classification.service import ClassificationService
from fip.services.data_service.models.fund import FundClassificationReviewCase
from fip.services.data_service.repositories.classification import SqlClassificationPitRepository
from tests.unit.test_classification_revision_v3 import (
    DAY,
    LATER,
    NOW,
    MemorySession,
    decision,
    ev,
    persist,
    snap,
)
from tests.unit.test_classification_strategy_v3 import member


class OfflineSession(MemorySession, Session):
    """Real service and SQL predicates over memory; no SQLAlchemy engine exists."""

    def __init__(self):
        MemorySession.__init__(self)
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class Funds:
    def __init__(self, session, rows=()):
        self.session = session
        self.rows = rows

    def list(self, **filters):
        return self.rows

    def _required_share_class(self, fund_id):
        if fund_id != "fixture":
            from fip.api.errors import NotFoundError

            raise NotFoundError("fund", fund_id)
        return self.session.rows[0], None


@pytest.fixture
def offline():
    session = OfflineSession()
    funds = Funds(session)
    app = FastAPI()
    app.include_router(classifications.router, prefix="/api/v1")
    app.include_router(reads.router, prefix="/api/v1")
    app.dependency_overrides[get_api_repositories] = lambda: SimpleNamespace(funds=funds)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status_code
        )

    return TestClient(app), session, funds


def test_catalog_selects_registered_version_without_changing_default(offline):
    client, _, _ = offline
    v3 = client.get("/api/v1/fund-classifications/catalog?enum_version=3.0.0")
    assert v3.status_code == 200
    data = v3.json()["data"]
    assert data["rule_version"] == data["enum_version"] == "3.0.0"
    assert data["active_dimensions"] == ["asset_class", "strategy"]
    assert data["paused_dimensions"] == ["geography", "product_structure", "market_attributes"]
    assert data["strategy_tags"] == ["QUANTITATIVE"]
    assert "QUANTITATIVE" not in data["dimensions"]["strategy"]
    v1 = client.get("/api/v1/fund-classifications/catalog").json()["data"]
    assert v1["rule_version"] == "1.0.0"
    assert "QUANTITATIVE" in v1["dimensions"]["strategy"]
    assert v1["strategy_tags"] == []
    assert len(v1["active_dimensions"]) == 5
    assert (
        client.get("/api/v1/fund-classifications/catalog?rule_version=1.0.0").json()["data"] == v1
    )


@pytest.mark.parametrize(
    "query", ["enum_version=2.0.0", "rule_version=3.0.0&enum_version=1.0.0", "rule_version=invalid"]
)
def test_catalog_rejects_unsupported_version_pairs(offline, query):
    assert offline[0].get("/api/v1/fund-classifications/catalog?" + query).status_code == 422


@pytest.mark.parametrize("status", ["CANDIDATE", "CONFLICT", "UNKNOWN"])
def test_independent_tag_filter_does_not_match_unconfirmed_results(status):
    data = snap().to_dict()
    data["strategy_tags"] = ["QUANTITATIVE"]  # a denormalized summary is not authoritative
    data["strategy_tag_results"]["QUANTITATIVE"].update(status=status, value="UNKNOWN")
    assert not _matches({"classification": data}, {"strategy_tags": ("QUANTITATIVE",)})


def test_legacy_quantitative_strategy_is_never_a_tag():
    legacy = snap(ev("strategy", "QUANTITATIVE"), v3=False).to_dict()
    assert _matches({"classification": legacy}, {"strategy": ("QUANTITATIVE",)})
    assert not _matches({"classification": legacy}, {"strategy_tags": ("QUANTITATIVE",)})


def test_confirmed_tag_requires_evaluated_evidence_and_matching_value():
    data = snap(ev("investment_strategy", "本基金采用量化模型。")).to_dict()
    assert _matches({"classification": data}, {"strategy_tags": ("QUANTITATIVE",)})
    for changes in [
        dict(evaluation_state="NOT_EVALUATED"),
        dict(evidence=[]),
        dict(value="UNKNOWN"),
    ]:
        changed = deepcopy(data)
        changed["strategy_tag_results"]["QUANTITATIVE"].update(changes)
        assert not _matches({"classification": changed}, {"strategy_tags": ("QUANTITATIVE",)})


def test_filters_use_each_snapshot_exact_version_and_explicit_catalog():
    old = snap(ev("strategy", "QUANTITATIVE"), v3=False).to_dict()
    current = snap().to_dict()
    malformed_v3 = deepcopy(current)
    malformed_v3["strategy"].update(status="CONFIRMED", value="QUANTITATIVE")
    assert _matches({"classification": old}, {"strategy": ("QUANTITATIVE",)})
    assert not _matches({"classification": malformed_v3}, {"strategy": ("QUANTITATIVE",)})
    assert not _matches(
        {"classification": old}, {"strategy": ("QUANTITATIVE",), "enum_version": "3.0.0"}
    )
    assert not _matches(
        {"classification": current}, {"asset_class": ("EQUITY",), "enum_version": "1.0.0"}
    )
    assert _matches(
        {"classification": current}, {"asset_class": ("EQUITY",), "enum_version": "3.0.0"}
    )


def test_list_exposes_tag_and_version_filters_and_validates_catalog(offline):
    client, _, funds = offline
    funds.rows = [
        {
            "fund_id": "old",
            "classification": snap(ev("strategy", "QUANTITATIVE"), v3=False).to_dict(),
        },
        {
            "fund_id": "current",
            "classification": snap(ev("investment_strategy", "本基金采用量化模型。")).to_dict(),
        },
    ]
    for row in funds.rows:
        row["classification"].update(
            revision_id=1,
            version=1,
            valid_from=DAY.isoformat(),
            available_at=NOW.isoformat(),
            classified_at=NOW.isoformat(),
            availability_quality="INFERRED",
            source_summary=[],
            trading_eligibility={},
        )
    response = client.get("/api/v1/funds?strategy_tags=QUANTITATIVE&enum_version=3.0.0")
    assert response.status_code == 200
    assert [r["fund_id"] for r in response.json()["data"]] == ["current"]
    assert client.get("/api/v1/funds?strategy=QUANTITATIVE&enum_version=3.0.0").status_code == 422
    assert client.get("/api/v1/funds?strategy_tags=INVALID").status_code == 422
    assert client.get("/api/v1/funds?enum_version=2.0.0").status_code == 422
    response = client.get("/api/v1/funds?strategy=QUANTITATIVE")
    assert [r["fund_id"] for r in response.json()["data"]] == ["old"]


def test_history_and_detail_models_preserve_legacy_absence_and_v3_source_metadata(offline):
    client, session, _ = offline
    first = persist(session, snap(v3=False))
    original = ClassificationService(session).intervals(first.id)[0][2].to_dict()
    persist(session, at=LATER)
    response = client.get("/api/v1/funds/fixture/classification-history")
    assert response.status_code == 200
    history = response.json()["data"]
    assert history[1]["intervals"][0]["classification"] == original
    assert "strategy_tag_results" not in history[1]["intervals"][0]["classification"]
    current = history[0]["intervals"][0]["classification"]
    assert current["strategy_tags"] == []
    assert current["geography"]["evaluation_state"] in ["PAUSED", "NOT_EVALUATED"]
    assert current["geography"]["carried_from_revision_id"] == first.id
    assert history[0]["ingested_at"] == LATER.isoformat()
    raw = SqlClassificationPitRepository(session, LATER).snapshot(1, effective_at=DAY)
    detail = ClassificationPayloadModel.model_validate(raw).model_dump(mode="json")
    assert detail["ingested_at"] == LATER.isoformat()
    assert detail["strategy_tag_results"]["QUANTITATIVE"]["evaluation_state"] == "EVALUATED"
    assert client.get("/api/v1/funds/missing/classification-history").status_code == 404
    assert (
        client.get("/api/v1/funds/fixture/classification-history?decision_at=2026-10-26").json()[
            "data"
        ]
        == []
    )


def test_review_default_scope_omits_paused_but_archive_and_detail_preserve_it(offline):
    client, session, _ = offline
    persist(session, snap(v3=False))
    ClassificationService(session).refresh_v3(
        1, [], available_at=LATER, actor="source", reason="upgrade"
    )
    historical = next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.details.get("evaluation_state") == "PAUSED"
    )
    active = client.get("/api/v1/classification-reviews").json()["data"]
    assert historical.id not in [v["case_id"] for v in active]
    archive = client.get("/api/v1/classification-reviews?scope=HISTORY").json()["data"]
    assert historical.id in [v["case_id"] for v in archive]
    detail = client.get(f"/api/v1/classification-reviews/{historical.id}").json()["data"]
    assert detail["evaluation_state"] == "PAUSED"
    assert detail["active_scope"] == []
    assert "geography" in detail["historical_scope"]
    assert detail["baseline"]["rule_version"] == "1.0.0"
    assert client.get("/api/v1/classification-reviews?scope=invalid").status_code == 422


def test_review_preserves_dual_membership_candidates_rule_provenance_and_tag_state(offline):
    client, session, _ = offline
    revision = persist(session, snap(member(), member("fund_index_passive")))
    case = next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.revision_id == revision.id
        and r.details.get("dimension") == "strategy"
    )
    response = client.get(f"/api/v1/classification-reviews/{case.id}")
    data = response.json()["data"]
    assert data["baseline"]["strategy"]["candidates"] == ["ENHANCED_INDEX", "PASSIVE_INDEX"]
    assert {e["rule_id"] for e in data["baseline"]["strategy"]["evidence"]} == {"STR001", "STR002"}
    assert all(e["required_observations"] for e in data["baseline"]["strategy"]["evidence"])
    assert (
        data["baseline"]["strategy_tag_results"]["QUANTITATIVE"]["evaluation_state"]
        == "NOT_EVALUATED"
    )
    assert data["active_scope"] == ["strategy"]


def upgrade_case(session):
    baseline = persist(session, snap(v3=False), reviewed=True)
    ClassificationService(session).replace_intervals(
        1,
        [
            (
                DAY,
                None,
                snap(
                    ev("formal_type", "股票型"), ev("investment_strategy", "本基金采用量化模型。")
                ),
            )
        ],
        available_at=LATER,
        actor="source",
        reason="version proposal",
    )
    return baseline, next(
        r
        for r in session.rows
        if isinstance(r, FundClassificationReviewCase)
        and r.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
    )


def review_body(revision):
    return {
        "expected_revision": revision.id,
        "reason": "official review",
        "decisions": {
            name: decision(value).model_dump(mode="json")
            for name, value in [("asset_class", "EQUITY"), ("strategy", "ACTIVE")]
        },
        "accept_incoming_version": "3.0.0",
        "tag_decisions": {
            "QUANTITATIVE": {
                "action": "CONFIRM",
                "evidence": [
                    ev("investment_strategy", "本基金采用量化模型。").model_dump(mode="json")
                ],
            }
        },
    }


def test_v3_review_http_keeps_capability_cas_and_independent_tag_decisions(offline):
    client, session, _ = offline
    revision, case = upgrade_case(session)
    url = f"/api/v1/classification-reviews/{case.id}/review"
    body = review_body(revision)
    assert client.post(url, json=body).status_code == 403
    before = client.get(f"/api/v1/classification-reviews/{case.id}").json()["data"]
    assert before["baseline"]["rule_version"] == "1.0.0"
    assert before["incoming"]["rule_version"] == "3.0.0"
    assert before["incoming"]["strategy_tags"] == ["QUANTITATIVE"]
    response = client.post(url, json=body, headers={"X-Roles": "Reviewer"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["version"] == 2
    assert session.commits == 1
    result = ClassificationService(session).intervals(response.json()["data"]["revision_id"])[0][2]
    assert result.strategy.value == "ACTIVE"
    assert result.strategy_tags == ("QUANTITATIVE",)
    assert client.post(url, json=body, headers={"X-Roles": "Reviewer"}).status_code == 409


@pytest.mark.parametrize("mutation", ["paused", "missing_active", "missing_tag", "missing_accept"])
def test_v3_review_http_rejects_invalid_scope_and_missing_version_acceptance(offline, mutation):
    client, session, _ = offline
    revision, case = upgrade_case(session)
    body = review_body(revision)
    if mutation == "paused":
        body["decisions"]["geography"] = decision("US").model_dump(mode="json")
    if mutation == "missing_active":
        del body["decisions"]["strategy"]
    if mutation == "missing_tag":
        body["tag_decisions"] = {}
    if mutation == "missing_accept":
        del body["accept_incoming_version"]
    response = client.post(
        f"/api/v1/classification-reviews/{case.id}/review",
        json=body,
        headers={"X-Roles": "Reviewer"},
    )
    assert response.status_code == 422
    assert session.commits == 0
    assert ClassificationService(session).latest(1).id == revision.id


def test_review_can_reject_upgrade_without_changing_legacy_snapshot(offline):
    client, session, _ = offline
    revision, case = upgrade_case(session)
    original = ClassificationService(session).intervals(revision.id)[0][2].to_dict()
    response = client.post(
        f"/api/v1/classification-reviews/{case.id}/review",
        json={
            "expected_revision": revision.id,
            "reason": "keep baseline",
            "decisions": {},
            "reject_upgrade": True,
        },
        headers={"X-Roles": "Reviewer"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["revision_id"] == revision.id
    assert ClassificationService(session).intervals(revision.id)[0][2].to_dict() == original


def test_frozen_snapshot_and_detail_contract_accepts_v3_additive_fields():
    frozen = yaml.safe_load(Path("frontend/openapi/m17.yaml").read_text())["components"]["schemas"]
    for model in [
        ClassificationSnapshot,
        ClassificationPayloadModel,
        classifications.ReviewSubmission,
        classifications.CatalogPayload,
        classifications.ReviewCasePayload,
        classifications.ClassificationHistoryPayload,
    ]:
        live = model.model_json_schema(ref_template="#/components/schemas/{model}")
        assert set(live["properties"]) == set(frozen[model.__name__]["properties"])
        assert set(live.get("required", [])) == set(frozen[model.__name__].get("required", []))
    invalid = snap().to_dict()
    invalid["strategy"]["value"] = "QUANTITATIVE"
    with pytest.raises(ValidationError):
        ClassificationSnapshot.model_validate(invalid)


@pytest.mark.parametrize(
    "status,value",
    [("CONFIRMED", "BOND"), ("CANDIDATE", "EQUITY"), ("CONFLICT", "EQUITY"), ("UNKNOWN", "EQUITY")],
)
def test_dimension_filter_requires_confirmed_matching_final_value(status, value):
    data = snap().to_dict()
    data["asset_class"].update(status=status, value=value)
    assert not _matches({"classification": data}, {"asset_class": ("EQUITY",)})


def test_classification_status_ignores_v3_paused_and_not_evaluated_dimensions():
    data = snap().to_dict()
    data["asset_class"].update(status="CONFIRMED", value="EQUITY")
    data["strategy"].update(status="CONFIRMED", value="ACTIVE")
    data["geography"].update(status="UNKNOWN", value="UNKNOWN", evaluation_state="PAUSED")
    data["product_structure"].update(
        status="UNKNOWN", value="UNKNOWN", evaluation_state="NOT_EVALUATED"
    )
    data["market_attributes"].update(status="UNKNOWN", value="UNKNOWN", evaluation_state="PAUSED")

    row = {"classification": data}

    assert not _matches(row, {"classification_status": ("UNKNOWN",)})
    assert _matches(row, {"classification_status": ("CONFIRMED",)})


def test_legacy_classification_status_keeps_all_dimensions_in_scope():
    data = snap(v3=False).to_dict()
    data["asset_class"].update(status="CONFIRMED", value="EQUITY")
    data["strategy"].update(status="CONFIRMED", value="ACTIVE")
    data["geography"].update(status="UNKNOWN", value="UNKNOWN")

    assert _matches({"classification": data}, {"classification_status": ("UNKNOWN",)})
