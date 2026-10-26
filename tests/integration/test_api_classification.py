"""Real PostgreSQL API classification/filter/review contract."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from fip.api.app import create_app
from fip.api.dependencies import get_api_repositories
from fip.api.repositories import ApiRepositories
from fip.services.data_service.classification import classify, normalize_evidence
from fip.services.data_service.classification.service import ClassificationService
from fip.services.data_service.models.fund import Fund, FundClassificationReviewCase, FundShareClass

pytestmark = pytest.mark.integration
AT = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


@pytest.fixture()
def seeded(db_session):
    fund = Fund(fund_code="CLASS-API", product_name="分类 API 测试", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    db_session.add(
        FundShareClass(
            fund_id=fund.id,
            share_class_code="A",
            display_name="测试A",
            inception_date=dt.date(2020, 1, 1),
        )
    )
    snap = classify(
        [
            normalize_evidence(
                source="AGGREGATOR", field="基金类型", value="股票型", classified_at=AT
            )
        ],
        classified_at=AT,
    )
    rev = ClassificationService(db_session).write(
        fund.id, snap, valid_from=AT.date(), available_at=AT, actor="test", reason="seed"
    )
    case = db_session.scalars(
        select(FundClassificationReviewCase).where(
            FundClassificationReviewCase.revision_id == rev.id,
            FundClassificationReviewCase.issue_key.like("%:strategy"),
        )
    ).one()
    app = create_app(strict_contracts=True)
    app.dependency_overrides[get_api_repositories] = lambda: ApiRepositories.from_session(
        db_session
    )
    return TestClient(app), fund, rev, case


def test_five_dimension_filters_do_not_match_candidates(seeded):
    client, fund, rev, _ = seeded
    response = client.get("/api/v1/funds?asset_class=EQUITY&strategy=ACTIVE")
    assert response.status_code == 200
    assert response.json()["data"] == []
    response = client.get("/api/v1/funds?asset_class=EQUITY&classification_status=UNKNOWN")
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["classification"]["revision_id"] == rev.id
    assert row["classification"]["asset_class"]["value"] == "EQUITY"
    assert row["fund_id"] == fund.fund_code
    assert client.get("/api/v1/funds?asset_class=INVALID").status_code == 422


def test_catalog_history_and_detail_share_visibility(seeded):
    client, fund, rev, _ = seeded
    assert (
        "EQUITY"
        in client.get("/api/v1/fund-classifications/catalog").json()["data"]["dimensions"][
            "asset_class"
        ]
    )
    old = client.get(
        f"/api/v1/funds/{fund.fund_code}/classification-history?decision_at=2025-12-31"
    )
    assert old.status_code == 200
    assert old.json()["data"] == []
    current = client.get(f"/api/v1/funds/{fund.fund_code}/classification-history")
    assert current.json()["data"][0]["version"] == 1
    detail = client.get(f"/api/v1/funds/{fund.fund_code}")
    assert detail.json()["data"]["classification"]["revision_id"] == rev.id


def test_review_403_success_409_and_pit_stability(seeded):
    client, fund, rev, case = seeded
    url = f"/api/v1/classification-reviews/{case.id}/review"
    proof = normalize_evidence(
        source="OFFICIAL",
        field="strategy",
        value="ACTIVE",
        classified_at=dt.datetime.now(dt.UTC),
        locator="prospectus §3",
    )
    body = {
        "expected_revision": rev.id,
        "reason": "官方策略确认",
        "decisions": {
            "strategy": {
                "action": "OVERRIDE",
                "value": "ACTIVE",
                "evidence": [proof.model_dump(mode="json")],
            }
        },
    }
    assert client.post(url, json=body).status_code == 403
    response = client.post(url, json=body, headers={"X-Roles": "Reviewer"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["version"] == 2
    assert client.post(url, json=body, headers={"X-Roles": "Reviewer"}).status_code == 409
    old = client.get(f"/api/v1/funds/{fund.fund_code}?as_of_date=2026-01-01")
    assert old.json()["data"]["classification"]["strategy"]["status"] == "UNKNOWN"
    current = client.get(f"/api/v1/funds/{fund.fund_code}")
    assert current.json()["data"]["classification"]["strategy"]["value"] == "ACTIVE"
