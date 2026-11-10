from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from fip.api.errors import InvalidQueryError
from fip.api.repositories import FundRepository
from fip.services.data_service.models.fund import (
    Fund,
    FundBasicInfoHistory,
    FundClassificationHistory,
    FundClassificationReviewCase,
    FundClassificationRevision,
    FundManager,
    FundManagerAssignment,
    FundShareClass,
    FundStatusHistory,
    InvestmentEligibility,
    ProviderFundIdentity,
)
from fip.services.data_service.models.governance import AuditLog, DataProvider, DataProviderDataset
from fip.services.data_service.models.raw import RawPayload

pytestmark = pytest.mark.integration

DAY = date(2026, 11, 3)
VISIBLE = datetime(2026, 11, 3, tzinfo=UTC)


def _fund(db_session, code: str, name: str, *classes: str):
    fund = Fund(fund_code=code, product_name=name, grouping_status="GROUPED")
    db_session.add(fund)
    db_session.flush()
    share_classes = []
    for suffix in classes:
        share_class = FundShareClass(
            fund_id=fund.id,
            share_class_code=suffix,
            display_name=f"{name} {suffix}",
            inception_date=DAY,
        )
        db_session.add(share_class)
        share_classes.append(share_class)
    db_session.flush()
    return fund, share_classes


def _identity(
    db_session,
    provider,
    code: str,
    share_class,
    *,
    valid_from=date(2000, 1, 1),
    valid_to=None,
    available_at=VISIBLE,
):
    row = ProviderFundIdentity(
        provider_id=provider.id,
        provider_fund_id=code,
        share_class_id=share_class.id,
        valid_from=valid_from,
        valid_to=valid_to,
        available_at=available_at,
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=VISIBLE,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _classification(
    db_session,
    fund,
    *,
    asset,
    available=VISIBLE,
    version=1,
    state="EVALUATED",
    asset_status=None,
    strategy="UNKNOWN",
    strategy_status="UNKNOWN",
    tag_status=None,
    tag_evidence=None,
    tag_evaluation_state="EVALUATED",
    tag_manual_action=None,
    other_dimensions=None,
    snapshot_scheme="FIP_CLASSIFICATION",
):
    revision = FundClassificationRevision(
        fund_id=fund.id,
        scheme="FIP_CLASSIFICATION",
        version=version,
        content_hash=f"{fund.id}-{version}",
        classified_at=available,
        reason="synthetic test fixture",
        actor="test",
        reviewed=False,
        available_at=available,
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=available,
    )
    db_session.add(revision)
    db_session.flush()
    result = {
        "scheme": snapshot_scheme,
        "asset_class": {
            "status": asset_status or ("UNKNOWN" if asset == "UNKNOWN" else "CONFIRMED"),
            "value": asset,
            "candidates": [],
            "evidence": [],
            "evaluation_state": state,
        },
        "strategy": {
            "status": strategy_status,
            "value": strategy,
            "candidates": [],
            "evidence": [],
            "evaluation_state": "EVALUATED" if strategy_status != "UNKNOWN" else "NOT_EVALUATED",
        },
        "geography": {
            "status": "UNKNOWN",
            "value": "UNKNOWN",
            "candidates": [],
            "evidence": [],
            "evaluation_state": "PAUSED",
            "carried_from_revision_id": revision.id,
        },
        "product_structure": {
            "status": "UNKNOWN",
            "value": "UNKNOWN",
            "candidates": [],
            "evidence": [],
            "evaluation_state": "PAUSED",
            "carried_from_revision_id": revision.id,
        },
        "market_attributes": {
            "status": "UNKNOWN",
            "value": "UNKNOWN",
            "candidates": [],
            "evidence": [],
            "evaluation_state": "PAUSED",
            "carried_from_revision_id": revision.id,
        },
    }
    if tag_status is not None:
        result["strategy_tag_results"] = {
            "QUANTITATIVE": {
                "status": tag_status,
                "value": "QUANTITATIVE" if tag_status == "CONFIRMED" else "UNKNOWN",
                "candidates": [],
                "evidence": tag_evidence or [],
                "evaluation_state": tag_evaluation_state,
                **({"manual_action": tag_manual_action} if tag_manual_action else {}),
            }
        }
    for dimension, value in (other_dimensions or {}).items():
        result[dimension] = {
            "status": "CONFIRMED",
            "value": value,
            "candidates": [],
            "evidence": [],
            "evaluation_state": "EVALUATED",
        }
    db_session.add(
        FundClassificationHistory(
            fund_id=fund.id,
            revision_id=revision.id,
            classification_scheme="FIP_CLASSIFICATION",
            classification_code="UNKNOWN",
            classification_result=result,
            trading_eligibility={"status": "UNKNOWN"},
            valid_from=date(2020, 1, 1),
            valid_to=None,
            available_at=available,
            availability_quality="INFERRED",
            published_at=None,
            provider_available_at=None,
            ingested_at=available,
        )
    )
    db_session.flush()
    return revision


def test_list_page_selects_akshare_code_and_returns_unique_share_class_rows(db_session):
    # Create a non-AKShare provider first. Its DB ID can coincide with a fund ID;
    # it must never be mistaken for the fund's provider mapping.
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    other = DataProvider(provider_code="OTHER_TEST", display_name="Other")
    db_session.add(other)
    db_session.flush()
    fund_a, classes_a = _fund(db_session, "PRODUCT-A", "Alpha", "A", "C")
    fund_b, classes_b = _fund(db_session, "PRODUCT-B", "Beta", "A")
    _identity(db_session, other, "999999", classes_a[0])
    _identity(db_session, akshare, "000001", classes_a[0])
    _identity(db_session, akshare, "000002", classes_a[1])
    _identity(db_session, akshare, "000003", classes_b[0])
    assert fund_b.id == other.id

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=2,
        sort="fund_code",
        order="asc",
        as_of_date=DAY.isoformat(),
    )

    assert total == 3
    assert [(row["fund_id"], row["share_class"], row["fund_code"]) for row in rows] == [
        ("PRODUCT-A", "A", "000001"),
        ("PRODUCT-A", "C", "000002"),
    ]
    assert rows[0]["share_class_id"] == str(classes_a[0].id)
    assert all(row["fund_id"] != str(akshare.id) for row in rows)


def test_list_page_does_not_invent_management_company_id_or_fund_company(db_session):
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    fund, classes = _fund(db_session, "NO-COMPANY", "No company evidence", "A")
    _identity(db_session, akshare, "000001", classes[0])

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_code",
        order="asc",
        as_of_date=DAY.isoformat(),
    )

    assert total == 1
    assert rows[0]["fund_classification"] == "UNKNOWN"
    assert rows[0]["fund_company"] is None
    assert rows[0]["management_company_id"] is None


def test_provider_identity_uses_visible_effective_mapping_and_keeps_missing_code(db_session):
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    fund, classes = _fund(db_session, "PIT", "PIT Fund", "A")
    _fund(db_session, "NO-CODE", "No Code", "A")
    _identity(
        db_session,
        akshare,
        "000001",
        classes[0],
        valid_from=date(2020, 1, 1),
        valid_to=date(2025, 1, 1),
        available_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    _identity(
        db_session,
        akshare,
        "000002",
        classes[0],
        valid_from=date(2025, 1, 1),
        available_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    _identity(
        db_session,
        akshare,
        "000003",
        classes[0],
        valid_from=date(2020, 1, 1),
        available_at=datetime(2027, 1, 1, tzinfo=UTC),
    )

    prior, prior_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_code",
        order="asc",
        as_of_date="2024-06-01",
    )
    current, current_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_code",
        order="asc",
        as_of_date=DAY.isoformat(),
    )

    assert prior_total == current_total == 2
    assert next(row for row in prior if row["fund_id"] == fund.fund_code)["fund_code"] == "000001"
    assert next(row for row in current if row["fund_id"] == fund.fund_code)["fund_code"] == "000002"
    assert next(row for row in prior if row["fund_id"] == "NO-CODE")["fund_code"] is None


def test_list_page_paginates_stably_without_manager_join_duplicates(db_session):
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    fund_a, classes_a = _fund(db_session, "A", "同名基金", "A")
    fund_b, classes_b = _fund(db_session, "B", "同名基金", "A")
    fund_c, classes_c = _fund(db_session, "C", "同名基金", "A")
    for index, share_class in enumerate((classes_a[0], classes_b[0], classes_c[0]), 1):
        _identity(db_session, akshare, f"00000{index}", share_class)
    managers = [
        FundManager(manager_code=f"M{index}", manager_name=f"经理{index}") for index in (1, 2)
    ]
    db_session.add_all(managers)
    db_session.flush()
    for manager in managers:
        db_session.add(
            FundManagerAssignment(
                fund_id=fund_a.id,
                manager_id=manager.id,
                valid_from=date(2020, 1, 1),
                valid_to=None,
                available_at=VISIBLE,
                availability_quality="INFERRED",
                published_at=None,
                provider_available_at=None,
                ingested_at=VISIBLE,
            )
        )
    db_session.flush()

    first, total = FundRepository(db_session).list_page(
        page=1,
        page_size=2,
        sort="fund_name",
        order="asc",
        as_of_date=DAY.isoformat(),
        manager_id=str(managers[0].id),
    )
    second, second_total = FundRepository(db_session).list_page(
        page=2,
        page_size=2,
        sort="fund_name",
        order="asc",
        as_of_date=DAY.isoformat(),
        manager_id=str(managers[0].id),
    )

    assert total == second_total == 1
    assert [row["fund_id"] for row in first] == ["A"]
    assert second == []


@pytest.mark.parametrize("page_size", [20, 50, 200])
def test_list_page_accepts_supported_page_sizes_and_nulls_last_sort(page_size, db_session):
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    fund_z, classes_z = _fund(db_session, "Z", "Same", "A")
    fund_a, classes_a = _fund(db_session, "A", "Same", "A")
    _fund(db_session, "M", "Same", "A")
    _identity(db_session, akshare, "000001", classes_z[0])
    _identity(db_session, akshare, "000002", classes_a[0])

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=page_size,
        sort="fund_code",
        order="desc",
        as_of_date=DAY.isoformat(),
    )

    assert total == 3
    assert [row["fund_id"] for row in rows] == ["A", "Z", "M"]

    tied_rows, tied_total = FundRepository(db_session).list_page(
        page=1,
        page_size=page_size,
        sort="fund_name",
        order="desc",
        as_of_date=DAY.isoformat(),
    )
    assert tied_total == 3
    assert [row["fund_id"] for row in tied_rows] == ["A", "M", "Z"]


def test_list_page_filters_literal_name_and_current_company_and_keeps_null_code_rows(db_session):
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    target, target_classes = _fund(db_session, "P-1", "Alpha 50%_\u91d1\\资", "A")
    target.fund_company = "管理公司甲"
    missing, missing_classes = _fund(db_session, "P-2", "Alpha 50ZZ金\\资", "A")
    missing.fund_company = None
    _identity(db_session, akshare, "000001", target_classes[0])
    _identity(db_session, akshare, "not-six-digit", missing_classes[0])
    db_session.flush()

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_code",
        order="asc",
        fund_name="50%_金\\",
        fund_code="000001",
        fund_company="管理公司甲",
    )

    assert total == 1
    assert rows[0]["fund_id"] == "P-1"
    assert rows[0]["fund_code"] == "000001"
    assert rows[0]["fund_company"] == "管理公司甲"
    assert rows[0]["sub_status"] == "开放"


def test_asset_class_filter_uses_visible_revision_interval_and_evaluated_unknown(db_session):
    funds = {}
    for index, asset in enumerate(
        (
            "EQUITY",
            "BOND",
            "MIXED",
            "MONEY_MARKET",
            "FOF",
            "REIT",
            "COMMODITY",
            "OTHER",
            "UNKNOWN",
        ),
        1,
    ):
        fund, _ = _fund(db_session, f"C-{index}", f"分类{index}", "A")
        _classification(db_session, fund, asset=asset)
        funds[asset] = fund

    no_snapshot, _ = _fund(db_session, "C-10", "没有快照", "A")
    unknown_not_evaluated, _ = _fund(db_session, "C-11", "未评价未知", "A")
    _classification(db_session, unknown_not_evaluated, asset="UNKNOWN", state="NOT_EVALUATED")
    unknown_candidate, _ = _fund(db_session, "C-13", "候选未知", "A")
    _classification(
        db_session,
        unknown_candidate,
        asset="UNKNOWN",
        asset_status="CANDIDATE",
        state="EVALUATED",
    )
    unknown_conflict, _ = _fund(db_session, "C-14", "冲突未知", "A")
    _classification(
        db_session,
        unknown_conflict,
        asset="UNKNOWN",
        asset_status="CONFLICT",
        state="EVALUATED",
    )
    past, _ = _fund(db_session, "C-12", "时点分类", "A")
    _classification(
        db_session,
        past,
        asset="BOND",
        available=datetime(2025, 1, 1, tzinfo=UTC),
    )
    _classification(db_session, past, asset="EQUITY", available=VISIBLE, version=2)
    db_session.flush()

    for asset, fund in funds.items():
        rows, total = FundRepository(db_session).list_page(
            page=1,
            page_size=20,
            sort="fund_name",
            order="asc",
            asset_class=(asset,),
            as_of_date=DAY.isoformat(),
        )
        if asset == "UNKNOWN":
            assert total == 2
            assert {row["fund_id"] for row in rows} == {
                fund.fund_code,
                no_snapshot.fund_code,
            }
        elif asset == "EQUITY":
            assert total == 2
            assert {row["fund_id"] for row in rows} == {fund.fund_code, past.fund_code}
        else:
            assert total == 1, asset
            assert rows[0]["fund_id"] == fund.fund_code

    unknown_rows, unknown_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        asset_class=("UNKNOWN",),
        as_of_date=DAY.isoformat(),
    )
    assert unknown_total == 2
    assert {row["fund_id"] for row in unknown_rows} == {
        no_snapshot.fund_code,
        funds["UNKNOWN"].fund_code,
    }

    bond_rows, bond_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        asset_class=("BOND",),
        as_of_date="2025-06-01",
    )
    assert bond_total == 1
    assert bond_rows[0]["fund_id"] == past.fund_code


def test_strategy_tag_filter_and_status_follow_active_dimension_evidence_rules(
    db_session,
):
    confirmed, _ = _fund(db_session, "TAG-1", "Confirmed", "A")
    _classification(
        db_session,
        confirmed,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        tag_status="CONFIRMED",
        tag_evidence=[
            {
                "source": "OFFICIAL",
                "rule_id": "TAG_QUANTITATIVE",
                "confidence": "OFFICIAL_DOCUMENT",
                "classified_at": VISIBLE.isoformat(),
                "raw_field": "test",
                "raw_value": "test",
            }
        ],
    )
    not_confirmed, _ = _fund(db_session, "TAG-2", "Not Confirmed", "A")
    _classification(
        db_session,
        not_confirmed,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        tag_status="CANDIDATE",
        tag_evidence=[
            {
                "source": "OFFICIAL",
                "rule_id": "TAG_QUANTITATIVE",
                "confidence": "OFFICIAL_DOCUMENT",
                "classified_at": VISIBLE.isoformat(),
                "raw_field": "test",
                "raw_value": "candidate",
            }
        ],
    )
    tag_unknown, _ = _fund(db_session, "TAG-3", "Tag Unknown", "A")
    _classification(
        db_session,
        tag_unknown,
        asset="UNKNOWN",
        tag_status="UNKNOWN",
    )
    unclassified, _ = _fund(db_session, "TAG-4", "No Classification", "A")
    db_session.flush()

    tagged, tagged_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        strategy_tags=("QUANTITATIVE",),
        as_of_date=DAY.isoformat(),
    )
    status_unknown, status_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        classification_status=("UNKNOWN",),
        as_of_date=DAY.isoformat(),
    )
    status_confirmed, confirmed_total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        classification_status=("CONFIRMED",),
        as_of_date=DAY.isoformat(),
    )

    assert tagged_total == 1
    assert [row["fund_id"] for row in tagged] == [confirmed.fund_code]
    assert status_total == 2
    assert {row["fund_id"] for row in status_unknown} == {
        tag_unknown.fund_code,
        unclassified.fund_code,
    }
    assert confirmed_total == 2


def test_asset_dimension_filters_require_evaluated_snapshot_values(db_session):
    confirmed, _ = _fund(db_session, "DIM-NO-EVAL", "Missing evaluation state", "A")
    revision = _classification(
        db_session,
        confirmed,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
    )
    unknown, _ = _fund(db_session, "DIM-UNKNOWN-NO-EVAL", "Unknown without evaluation", "A")
    unknown_revision = _classification(
        db_session,
        unknown,
        asset="UNKNOWN",
        strategy="UNKNOWN",
        strategy_status="UNKNOWN",
    )
    history = db_session.query(FundClassificationHistory).filter_by(revision_id=revision.id).one()
    classification_result = dict(history.classification_result)
    asset_result = dict(classification_result["asset_class"])
    asset_result.pop("evaluation_state")
    classification_result["asset_class"] = asset_result
    history.classification_result = classification_result
    unknown_history = (
        db_session.query(FundClassificationHistory).filter_by(revision_id=unknown_revision.id).one()
    )
    unknown_result = dict(unknown_history.classification_result)
    unknown_asset_result = dict(unknown_result["asset_class"])
    unknown_asset_result.pop("evaluation_state")
    unknown_result["asset_class"] = unknown_asset_result
    unknown_history.classification_result = unknown_result
    db_session.flush()

    for asset in ("EQUITY", "UNKNOWN"):
        rows, total = FundRepository(db_session).list_page(
            page=1,
            page_size=20,
            sort="fund_name",
            order="asc",
            asset_class=(asset,),
            as_of_date=DAY.isoformat(),
        )
        assert total == 0
        assert rows == []


def test_active_equity_projection_requires_all_automatic_negative_tag_evidence(db_session):
    def evidence(rule_id="TAG_QUANTITATIVE", rationale="polarity=NEGATIVE explicit statement"):
        observation = {
            "source": "OFFICIAL",
            "rule_id": rule_id,
            "confidence": "OFFICIAL_DOCUMENT",
            "classified_at": VISIBLE.isoformat(),
            "raw_field": "investment_strategy",
            "raw_value": "active",
        }
        return {
            **observation,
            "rationale": rationale,
            "required_observations": [observation],
        }

    valid_negative = evidence()
    mixed, _ = _fund(db_session, "TAG-MIXED", "Mixed evidence", "A")
    mixed.grouping_status = "CONFIRMED"
    _classification(
        db_session,
        mixed,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        tag_status="UNKNOWN",
        tag_evidence=[valid_negative, evidence("OTHER_RULE")],
    )
    all_negative, _ = _fund(db_session, "TAG-ALL-NEG", "All negative evidence", "A")
    all_negative.grouping_status = "CONFIRMED"
    _classification(
        db_session,
        all_negative,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        tag_status="UNKNOWN",
        tag_evidence=[valid_negative, evidence(rationale="other polarity=NEGATIVE")],
    )
    empty, _ = _fund(db_session, "TAG-EMPTY", "Empty evidence", "A")
    empty.grouping_status = "CONFIRMED"
    _classification(
        db_session,
        empty,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        tag_status="UNKNOWN",
        tag_evidence=[],
    )
    positive, _ = _fund(db_session, "TAG-POSITIVE", "Positive evidence", "A")
    positive.grouping_status = "CONFIRMED"
    _classification(
        db_session,
        positive,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        tag_status="UNKNOWN",
        tag_evidence=[evidence(rationale="polarity=POSITIVE")],
    )
    db_session.flush()

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        fund_type=("ACTIVE_EQUITY",),
        as_of_date=DAY.isoformat(),
    )

    assert total == 1
    assert [row["fund_id"] for row in rows] == [all_negative.fund_code]


def test_active_equity_projection_requires_evaluated_verified_manual_rejection(db_session):
    def reviewed_fund(code: str, evaluation_state: str):
        fund, _ = _fund(db_session, code, code, "A")
        fund.grouping_status = "CONFIRMED"
        revision = _classification(
            db_session,
            fund,
            asset="EQUITY",
            strategy="ACTIVE",
            strategy_status="CONFIRMED",
            tag_status="UNKNOWN",
            tag_evaluation_state=evaluation_state,
            tag_manual_action="REJECT",
        )
        revision.reviewed = True
        history = (
            db_session.query(FundClassificationHistory).filter_by(revision_id=revision.id).one()
        )
        tag = history.classification_result["strategy_tag_results"]["QUANTITATIVE"]
        case = FundClassificationReviewCase(
            fund_id=fund.id,
            revision_id=revision.id,
            issue_key=f"{code}-case",
            issue_type="NEW_EVIDENCE_AFTER_REVIEW",
            status="RESOLVED",
            details={},
            created_at=VISIBLE,
            resolved_at=VISIBLE,
            result_revision_id=revision.id,
        )
        db_session.add(case)
        db_session.flush()
        db_session.add(
            AuditLog(
                resource_type="fund_classification",
                resource_id=str(fund.id),
                action="REVIEW",
                operator="reviewer",
                created_at=VISIBLE,
                detail={
                    "revision_id": str(revision.id),
                    "expected_revision": str(revision.id),
                    "case_id": str(case.id),
                    "valid_from": "2020-01-01",
                    "valid_to": None,
                    "reason": "verified tag rejection",
                    "tag_decisions": {
                        "QUANTITATIVE": {"action": "REJECT", "evidence": [{"source": "review"}]}
                    },
                    "result_tag_results": {"QUANTITATIVE": tag},
                },
            )
        )
        return fund

    not_evaluated = reviewed_fund("TAG-MANUAL-NOT-EVAL", "NOT_EVALUATED")
    evaluated = reviewed_fund("TAG-MANUAL-EVAL", "EVALUATED")
    db_session.flush()

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        fund_type=("ACTIVE_EQUITY",),
        as_of_date=DAY.isoformat(),
    )

    assert total == 1
    assert [row["fund_id"] for row in rows] == [evaluated.fund_code]
    assert not_evaluated.fund_code not in {row["fund_id"] for row in rows}


def test_all_legacy_classification_dimensions_remain_sql_filterable(db_session):
    fund, _ = _fund(db_session, "DIM-1", "Dimensions", "A")
    _classification(
        db_session,
        fund,
        asset="EQUITY",
        strategy="ACTIVE",
        strategy_status="CONFIRMED",
        snapshot_scheme="FIP_CLASSIFICATION_V1",
        other_dimensions={
            "geography": "DOMESTIC",
            "product_structure": "ORDINARY",
            "market_attributes": "DOMESTIC",
        },
    )
    db_session.flush()
    for dimension, choice in (
        ("asset_class", "EQUITY"),
        ("strategy", "ACTIVE"),
        ("geography", "DOMESTIC"),
        ("product_structure", "ORDINARY"),
        ("market_attributes", "DOMESTIC"),
    ):
        rows, total = FundRepository(db_session).list_page(
            page=1,
            page_size=20,
            sort="fund_name",
            order="asc",
            **{dimension: (choice,)},
            as_of_date=DAY.isoformat(),
        )
        assert total == 1, dimension
        assert rows[0]["fund_id"] == fund.fund_code


def test_old_fund_type_fallback_and_unsupported_filters_are_explicit(db_session):
    legacy, _ = _fund(db_session, "LEGACY", "Legacy Bond", "A")
    db_session.add(
        FundClassificationHistory(
            fund_id=legacy.id,
            revision_id=None,
            classification_scheme="FIP_INTERNAL_L2",
            classification_code="BOND",
            classification_result=None,
            trading_eligibility=None,
            valid_from=date(2020, 1, 1),
            valid_to=None,
            available_at=VISIBLE,
            availability_quality="INFERRED",
            published_at=None,
            provider_available_at=None,
            ingested_at=VISIBLE,
        )
    )
    current, _ = _fund(db_session, "CURRENT", "Current Bond", "A")
    current.grouping_status = "CONFIRMED"
    _classification(
        db_session, current, asset="BOND", strategy="ACTIVE", strategy_status="CONFIRMED"
    )
    db_session.flush()

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_name",
        order="asc",
        fund_type=("BOND",),
        as_of_date=DAY.isoformat(),
    )

    assert total == 2
    assert {row["fund_id"] for row in rows} == {legacy.fund_code, current.fund_code}
    with pytest.raises(InvalidQueryError, match="management_company_id is unavailable"):
        FundRepository(db_session).list_page(
            page=1,
            page_size=20,
            sort="fund_name",
            order="asc",
            management_company_id="unrelated-company-table-id",
        )
    with pytest.raises(InvalidQueryError, match="aum filters are unavailable"):
        FundRepository(db_session).list_page(
            page=1,
            page_size=20,
            sort="fund_name",
            order="asc",
            aum_min=1.0,
        )


def test_current_eligibility_lifecycle_and_inception_filters_are_sql_backed(db_session):
    akshare = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    eligible, classes_eligible = _fund(db_session, "ELIGIBLE", "Eligible", "A")
    closed, classes_closed = _fund(db_session, "CLOSED", "Closed", "A")
    _identity(db_session, akshare, "000001", classes_eligible[0])
    _identity(db_session, akshare, "000002", classes_closed[0])
    for share_class, status, code in (
        (classes_eligible[0], "NORMAL", "FULLY_ELIGIBLE"),
        (classes_closed[0], "LIQUIDATED", "NOT_TRADABLE"),
    ):
        db_session.add(
            FundStatusHistory(
                share_class_id=share_class.id,
                lifecycle_status=status,
                subscription_open=status == "NORMAL",
                redemption_open=status == "NORMAL",
                valid_from=date(2020, 1, 1),
                valid_to=None,
                available_at=VISIBLE,
                availability_quality="INFERRED",
                published_at=None,
                provider_available_at=None,
                ingested_at=VISIBLE,
            )
        )
        db_session.add(
            InvestmentEligibility(
                share_class_id=share_class.id,
                effective_at=date(2020, 1, 1),
                version=1,
                eligibility_status=code,
                available_at=VISIBLE,
                availability_quality="INFERRED",
                published_at=None,
                provider_available_at=None,
                ingested_at=VISIBLE,
            )
        )
    db_session.flush()

    rows, total = FundRepository(db_session).list_page(
        page=1,
        page_size=20,
        sort="fund_code",
        order="asc",
        lifecycle_status=("NORMAL",),
        investment_eligibility=("FULLY_ELIGIBLE",),
        inception_date_from=DAY.isoformat(),
        inception_date_to=DAY.isoformat(),
        as_of_date=DAY.isoformat(),
    )

    assert total == 1
    assert rows[0]["fund_id"] == eligible.fund_code


def test_request_transaction_is_repeatable_read_across_page_and_enrichment(db_engine):
    reader = Session(bind=db_engine, future=True)
    writer = Session(bind=db_engine, future=True)
    verifier = Session(bind=db_engine, future=True)
    fund = None
    fund_pk = None
    try:
        repo = FundRepository(reader)
        assert not reader.in_transaction()
        first, first_total = repo.list_page(page=1, page_size=20, sort="fund_name", order="asc")
        assert first == [] and first_total == 0
        assert reader.connection().get_isolation_level() == "REPEATABLE READ"

        fund = Fund(
            fund_code="SNAPSHOT-1", product_name="Inserted later", grouping_status="GROUPED"
        )
        writer.add(fund)
        writer.flush()
        writer.add(
            FundShareClass(
                fund_id=fund.id,
                share_class_code="A",
                display_name="Inserted later A",
                inception_date=DAY,
            )
        )
        fund_pk = fund.id
        writer.commit()

        second, second_total = repo.list_page(page=1, page_size=20, sort="fund_name", order="asc")
        assert second == [] and second_total == 0
        reader.rollback()
        visible, visible_total = FundRepository(verifier).list_page(
            page=1, page_size=20, sort="fund_name", order="asc"
        )
        assert visible_total == 1
        assert visible[0]["fund_id"] == "SNAPSHOT-1"
    finally:
        reader.close()
        writer.rollback()
        writer.close()
        if fund_pk is not None:
            verifier.execute(delete(FundShareClass).where(FundShareClass.fund_id == fund_pk))
            verifier.execute(delete(Fund).where(Fund.id == fund_pk))
            verifier.commit()
        verifier.close()


def test_management_company_options_are_distinct_and_historically_visible(db_session):
    fund_a, _ = _fund(db_session, "M-1", "Fund A", "A")
    fund_b, _ = _fund(db_session, "M-2", "Fund B", "A")
    fund_c, _ = _fund(db_session, "M-3", "Fund C", "A")
    fund_d, _ = _fund(db_session, "M-4", "Fund D", "A")
    fund_a.fund_company = "当前甲"
    fund_b.fund_company = "当前甲"
    fund_c.fund_company = None
    db_session.flush()

    db_session.add_all(
        [
            _basic_history(db_session, fund_a, "历史甲", datetime(2024, 1, 1, tzinfo=UTC), 1),
            _basic_history(db_session, fund_a, "当前甲", datetime(2026, 1, 1, tzinfo=UTC), 2),
            _basic_history(db_session, fund_b, "历史乙", datetime(2024, 1, 1, tzinfo=UTC), 1),
        ]
    )
    fallback = _basic_history(
        db_session, fund_c, "同快照原始公司", datetime(2024, 1, 1, tzinfo=UTC), 1
    )
    fallback.normalized_fields = {"fund_company": "nan"}
    fallback.raw_fields = {"基金公司": "同快照原始公司"}
    db_session.add(fallback)
    manager_only = _basic_history(
        db_session, fund_d, "经理姓名不可作公司", datetime(2024, 1, 1, tzinfo=UTC), 1
    )
    manager_only.normalized_fields = {"fund_company": "nan"}
    manager_only.raw_fields = {"基金管理人": "王经理"}
    db_session.add(manager_only)

    current = FundRepository(db_session).list_management_companies()
    historical = FundRepository(db_session).list_management_companies(as_of_date="2024-12-31")

    assert current == ["当前甲"]
    assert historical == ["历史乙", "历史甲", "同快照原始公司"]


def _basic_history(db_session, fund, company: str, available_at: datetime, version: int):
    provider = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    dataset = (
        db_session.query(DataProviderDataset)
        .filter_by(provider_id=provider.id, dataset_code="TEST_FUND_OVERVIEW")
        .one_or_none()
    )
    if dataset is None:
        dataset = DataProviderDataset(
            provider_id=provider.id,
            dataset_code="TEST_FUND_OVERVIEW",
            adapter_version="test",
            library_version="test",
        )
        db_session.add(dataset)
        db_session.flush()
    payload = RawPayload(
        dataset_id=dataset.id,
        request_params={},
        payload=b"synthetic",
        row_count=1,
        library_version="test",
        published_at=None,
        provider_available_at=None,
        ingested_at=available_at,
    )
    db_session.add(payload)
    db_session.flush()

    return FundBasicInfoHistory(
        fund_id=fund.id,
        version=version,
        content_hash=f"{fund.id}-{version}",
        raw_fields={"基金公司": company},
        normalized_fields={"fund_company": company},
        raw_payload_id=payload.id,
        available_at=available_at,
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=available_at,
    )
