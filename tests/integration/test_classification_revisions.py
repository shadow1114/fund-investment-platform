"""Revision-first PIT, immutable interval correction and review transactions."""

import datetime as dt

import pytest
from sqlalchemy import func, select

from fip.services.data_service.classification import classify, normalize_evidence
from fip.services.data_service.classification.service import (
    ClassificationConflict,
    ClassificationService,
    ReviewDecision,
)
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundClassificationReviewCase,
    FundClassificationRevision,
)
from fip.services.data_service.models.governance import AuditLog
from fip.services.data_service.repositories.classification import SqlClassificationPitRepository

pytestmark = pytest.mark.integration
T1 = dt.datetime(2026, 1, 2, 10, tzinfo=dt.UTC)
T2 = T1 + dt.timedelta(hours=1)
DAY = dt.date(2026, 1, 1)


@pytest.fixture()
def product(db_session):
    item = Fund(fund_code="REV-TEST", product_name="分类测试", grouping_status="CONFIRMED")
    db_session.add(item)
    db_session.flush()
    return item


def snapshot(kind="股票型", at=T1):
    return classify(
        [normalize_evidence(source="AGGREGATOR", field="基金类型", value=kind, classified_at=at)],
        classified_at=at,
    )


def write(db_session, product, kind="股票型", at=T1, **kwargs):
    return ClassificationService(db_session).write(
        product.id,
        snapshot(kind, at),
        valid_from=DAY,
        available_at=at,
        actor="test",
        reason="fixture",
        **kwargs,
    )


def test_correction_preserves_old_decision_and_rows(db_session, product):
    first = write(db_session, product)
    second = write(db_session, product, "债券型", T2)
    assert (first.version, second.version) == (1, 2)
    old = SqlClassificationPitRepository(db_session, T1).snapshot(product.id, effective_at=DAY)
    new = SqlClassificationPitRepository(db_session, T2).snapshot(product.id, effective_at=DAY)
    assert old["asset_class"]["value"] == "EQUITY"
    assert new["asset_class"]["value"] == "BOND"
    assert old["revision_id"] == first.id
    assert db_session.scalar(select(func.count()).select_from(FundClassificationHistory)) == 2


def test_idempotence_ignores_reclassification_clock(db_session, product):
    first = write(db_session, product)
    again = write(db_session, product, at=T2)
    assert first.id == again.id
    assert db_session.scalar(select(func.count()).select_from(FundClassificationRevision)) == 1


def test_transformation_copies_full_intervals_without_closing_old(db_session, product):
    first = write(db_session, product)
    service = ClassificationService(db_session)
    second = service.write(
        product.id,
        snapshot("债券型", T2),
        valid_from=dt.date(2026, 2, 1),
        available_at=T2,
        actor="test",
        reason="transformation",
    )
    repo = SqlClassificationPitRepository(db_session, T2)
    assert repo.snapshot(product.id, effective_at=DAY)["asset_class"]["value"] == "EQUITY"
    assert (
        repo.snapshot(product.id, effective_at=dt.date(2026, 2, 1))["asset_class"]["value"]
        == "BOND"
    )
    old = db_session.scalars(
        select(FundClassificationHistory).where(FundClassificationHistory.revision_id == first.id)
    ).one()
    assert old.valid_to is None
    assert len(service.intervals(second.id)) == 2


def test_latest_revision_gap_never_falls_back(db_session, product):
    write(db_session, product)
    ClassificationService(db_session).replace_intervals(
        product.id,
        [(dt.date(2026, 2, 1), None, snapshot("债券型", T2))],
        available_at=T2,
        actor="test",
        reason="explicit gap",
    )
    assert (
        SqlClassificationPitRepository(db_session, T2).snapshot(product.id, effective_at=DAY)
        is None
    )


def test_version_precedes_available_time_order(db_session, product):
    write(db_session, product, at=T2)
    newest = write(db_session, product, "债券型", T1)
    result = SqlClassificationPitRepository(db_session, T2).snapshot(product.id, effective_at=DAY)
    assert result["revision_id"] == newest.id


def test_review_is_compare_and_swap_audited_and_refresh_protected(db_session, product):
    first = write(db_session, product)
    case = db_session.scalars(
        select(FundClassificationReviewCase).where(
            FundClassificationReviewCase.revision_id == first.id
        )
    ).first()
    assert case is not None
    evidence = normalize_evidence(
        source="OFFICIAL", field="strategy", value="ACTIVE", classified_at=T2, locator="contract §3"
    )
    service = ClassificationService(db_session)
    revision = service.review(
        case.id,
        expected_revision=first.id,
        decisions={
            "strategy": ReviewDecision(action="OVERRIDE", value="ACTIVE", evidence=(evidence,))
        },
        actor="reviewer",
        reason="contract confirmed",
        can_review=True,
        reviewed_at=T2,
    )
    assert revision.version == 2
    audit = db_session.scalars(
        select(AuditLog).where(
            AuditLog.resource_type == "fund_classification", AuditLog.action == "REVIEW"
        )
    ).one()
    assert audit.operator == "reviewer"
    with pytest.raises(ClassificationConflict):
        service.review(
            case.id,
            expected_revision=first.id,
            decisions={},
            actor="reviewer",
            reason="duplicate",
            can_review=True,
            reviewed_at=T2,
        )
    refreshed = write(db_session, product, "债券型", T2 + dt.timedelta(hours=1))
    assert refreshed.id == revision.id
    assert db_session.scalar(select(func.count()).select_from(FundClassificationRevision)) == 2


def test_review_requires_capability_and_evidence(db_session, product):
    first = write(db_session, product)
    case = db_session.scalars(select(FundClassificationReviewCase)).first()
    with pytest.raises(PermissionError):
        ClassificationService(db_session).review(
            case.id,
            expected_revision=first.id,
            decisions={},
            actor="researcher",
            reason="no authorization",
            can_review=False,
            reviewed_at=T2,
        )


def test_same_start_value_overlay_still_replaces_future_changes(db_session, product):
    service = ClassificationService(db_session)
    service.replace_intervals(
        product.id,
        [
            (DAY, dt.date(2026, 2, 1), snapshot()),
            (dt.date(2026, 2, 1), None, snapshot("债券型")),
        ],
        available_at=T1,
        actor="test",
        reason="future transition",
    )
    revision = service.write(
        product.id,
        snapshot(),
        valid_from=dt.date(2026, 1, 15),
        available_at=T2,
        actor="test",
        reason="cancel transition",
    )
    assert revision.version == 2
    result = SqlClassificationPitRepository(db_session, T2).snapshot(
        product.id, effective_at=dt.date(2026, 3, 1)
    )
    assert result["asset_class"]["value"] == "EQUITY"


def test_identical_write_still_validates_actor_time_and_bounds(db_session, product):
    write(db_session, product)
    service = ClassificationService(db_session)
    for invalid in ({"actor": ""}, {"available_at": T1.replace(tzinfo=None)}, {"valid_to": DAY}):
        kwargs = {"valid_from": DAY, "available_at": T2, "actor": "test", "reason": "same"}
        kwargs.update(invalid)
        with pytest.raises(ValueError):
            service.write(product.id, snapshot(), **kwargs)


def test_unrelated_revision_preserves_exchange_eligibility(db_session, product):
    first = write(db_session, product)
    row = db_session.scalars(
        select(FundClassificationHistory).where(FundClassificationHistory.revision_id == first.id)
    ).one()
    row.trading_eligibility = {"status": "CONFIRMED", "exchange": "SSE", "eligible": True}
    db_session.flush()
    write(db_session, product, "债券型", T2)
    result = SqlClassificationPitRepository(db_session, T2).snapshot(product.id, effective_at=DAY)
    assert result["trading_eligibility"] == {
        "status": "CONFIRMED",
        "exchange": "SSE",
        "eligible": True,
    }


def test_peer_candidate_adapter_preserves_revision_and_exclusion_reason(db_session, product):
    from fip.services.data_service.models.fund import FundShareClass
    from fip.services.fund_service.peer_group import build_peer_groups, excluded_candidates
    from fip.services.fund_service.peer_group.classification import (
        SqlClassificationCandidateProvider,
    )

    sc = FundShareClass(fund_id=product.id, share_class_code="A", display_name="测试A")
    db_session.add(sc)
    db_session.flush()
    first = write(db_session, product)
    candidates = SqlClassificationCandidateProvider(db_session).at(T1)
    assert candidates[0].classification_revision_id == first.id
    assert build_peer_groups(candidates, {"ACTIVE_EQUITY": "Active"}) == ()
    assert excluded_candidates(candidates, {"ACTIVE_EQUITY": "Active"})[0].reason == (
        "UNSUPPORTED_COMBINATION"
    )


def test_partial_source_refresh_preserves_other_dimensions_and_conflicting_sources(
    db_session, product
):
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
    from fip.services.data_service.ingest import IngestService
    from fip.services.data_service.models.raw import RawPayload

    ingest = IngestService(db_session, AkShareSourceAdapter(caller=lambda *a, **kw: None), None)
    one = ingest.ensure_dataset("fund_overview")
    two = ingest.ensure_dataset("fund_list")

    def payload(dataset):
        row = RawPayload(
            dataset_id=dataset.id,
            payload=b"fixture",
            row_count=1,
            request_params={"symbol": "1"},
            library_version="test",
            ingested_at=T1,
        )
        db_session.add(row)
        db_session.flush()
        return row

    first = payload(one)
    second = payload(two)
    ingest.classify_fields(
        product.id, {"formal_type": "股票型", "strategy": "ACTIVE"}, first, actor="test"
    )
    result = ingest.classify_fields(product.id, {"formal_type": "股票型"}, second, actor="test")
    assert result.strategy.value == "ACTIVE"
    conflict = ingest.classify_fields(product.id, {"formal_type": "债券型"}, second, actor="test")
    assert conflict.asset_class.status == "CONFLICT"


def test_confirmed_dimension_rejects_name_only_proof(db_session, product):
    from fip.services.data_service.classification import DimensionResult

    source = normalize_evidence(source="NAME", field="name", value="股票", classified_at=T1)
    invalid = snapshot().model_copy(
        update={
            "asset_class": DimensionResult(status="CONFIRMED", value="EQUITY", evidence=(source,))
        }
    )
    with pytest.raises(ValueError):
        ClassificationService(db_session).write(
            product.id, invalid, valid_from=DAY, available_at=T1, actor="test", reason="invalid"
        )


def test_refresh_review_only_changes_explicit_interval_and_audits_rejection(db_session, product):
    service = ClassificationService(db_session)
    service.replace_intervals(
        product.id,
        [
            (DAY, dt.date(2026, 2, 1), snapshot()),
            (dt.date(2026, 2, 1), None, snapshot("债券型")),
        ],
        available_at=T1,
        actor="reviewer",
        reason="confirmed history",
        reviewed=True,
    )
    current = service.latest(product.id)
    service.write(
        product.id,
        snapshot("混合型"),
        valid_from=dt.date(2026, 3, 1),
        available_at=T2,
        actor="source",
        reason="new evidence",
    )
    case = db_session.scalars(
        select(FundClassificationReviewCase).where(
            FundClassificationReviewCase.issue_type == "NEW_EVIDENCE_AFTER_REVIEW"
        )
    ).one()
    assert case.details["valid_from"] == "2026-03-01"
    proof = normalize_evidence(
        source="OFFICIAL",
        field="asset_class",
        value="MIXED",
        classified_at=T2,
        locator="contract amendment",
    )
    reviewed = service.review(
        case.id,
        expected_revision=current.id,
        decisions={
            "asset_class": ReviewDecision(action="OVERRIDE", value="MIXED", evidence=(proof,))
        },
        actor="reviewer",
        reason="confirmed transformation",
        can_review=True,
        reviewed_at=T2,
    )
    repo = SqlClassificationPitRepository(db_session, T2)
    assert repo.snapshot(product.id, effective_at=DAY)["asset_class"]["value"] == "EQUITY"
    assert (
        repo.snapshot(product.id, effective_at=dt.date(2026, 2, 15))["asset_class"]["value"]
        == "BOND"
    )
    assert (
        repo.snapshot(product.id, effective_at=dt.date(2026, 3, 1))["asset_class"]["value"]
        == "MIXED"
    )
    pending = db_session.scalars(
        select(FundClassificationReviewCase).where(
            FundClassificationReviewCase.revision_id == reviewed.id,
            FundClassificationReviewCase.status == "PENDING",
        )
    ).first()
    service.review(
        pending.id,
        expected_revision=reviewed.id,
        decisions={"strategy": ReviewDecision(action="REJECT", evidence=(proof,))},
        actor="reviewer",
        reason="unsupported candidate",
        can_review=True,
        reviewed_at=T2,
    )
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "REVIEW").order_by(AuditLog.id.desc())
    ).first()
    assert audit.detail["decisions"]["strategy"]["action"] == "REJECT"
    assert audit.detail["decisions"]["strategy"]["evidence"][0]["locator"] == "contract amendment"


def test_concurrent_writers_allocate_unique_product_versions(db_engine):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    # Committed seed is visible to independent connections; this database is disposable.
    with Session(db_engine) as seed:
        product = Fund(
            fund_code="CONCURRENT-REV", product_name="并发修订", grouping_status="CONFIRMED"
        )
        seed.add(product)
        seed.commit()
        fund_id = product.id
    try:

        def run(kind):
            with Session(db_engine) as session:
                revision = ClassificationService(session).write(
                    fund_id,
                    snapshot(kind),
                    valid_from=DAY,
                    available_at=T1,
                    actor="concurrent-test",
                    reason="independent source",
                )
                version = revision.version
                session.commit()
                return version

        with ThreadPoolExecutor(max_workers=2) as pool:
            versions = list(pool.map(run, ["股票型", "债券型"]))
        assert sorted(versions) == [1, 2]
    finally:
        with Session(db_engine) as cleanup:
            for model in (
                FundClassificationReviewCase,
                FundClassificationHistory,
                FundClassificationRevision,
            ):
                cleanup.execute(delete(model).where(model.fund_id == fund_id))
            cleanup.execute(
                delete(AuditLog).where(
                    AuditLog.resource_type == "fund_classification",
                    AuditLog.resource_id == str(fund_id),
                )
            )
            cleanup.execute(delete(Fund).where(Fund.id == fund_id))
            cleanup.commit()


def test_review_preserves_other_incoming_proposals_on_new_baseline(db_session, product):
    service = ClassificationService(db_session)

    def full(kind):
        return classify(
            [
                normalize_evidence(source="OFFICIAL", field=field, value=value, classified_at=T1)
                for field, value in (
                    ("formal_type", kind),
                    ("strategy", "ACTIVE"),
                    ("geography", "DOMESTIC"),
                    ("product_structure", "ORDINARY"),
                    ("market_attributes", "DOMESTIC"),
                )
            ],
            classified_at=T1,
        )

    service.replace_intervals(
        product.id,
        [(DAY, dt.date(2026, 2, 1), full("股票型")), (dt.date(2026, 2, 1), None, full("债券型"))],
        available_at=T1,
        actor="reviewer",
        reason="baseline",
        reviewed=True,
    )
    baseline = service.latest(product.id)
    service.replace_intervals(
        product.id,
        [(DAY, dt.date(2026, 2, 1), full("混合型")), (dt.date(2026, 2, 1), None, full("股票型"))],
        available_at=T2,
        actor="source",
        reason="new proposals",
    )
    proposals = db_session.scalars(
        select(FundClassificationReviewCase)
        .where(FundClassificationReviewCase.status == "PENDING")
        .order_by(FundClassificationReviewCase.id)
    ).all()
    assert len(proposals) == 2
    proof = normalize_evidence(
        source="OFFICIAL",
        field="asset_class",
        value="MIXED",
        classified_at=T2,
        locator="official amendment",
    )
    revised = service.review(
        proposals[0].id,
        expected_revision=baseline.id,
        decisions={
            "asset_class": ReviewDecision(action="OVERRIDE", value="MIXED", evidence=(proof,))
        },
        actor="reviewer",
        reason="first proposal",
        can_review=True,
        reviewed_at=T2,
    )
    pending = db_session.scalars(
        select(FundClassificationReviewCase).where(FundClassificationReviewCase.status == "PENDING")
    ).all()
    assert len(pending) == 1
    assert pending[0].revision_id == revised.id
    assert pending[0].details["valid_from"] == "2026-02-01"
    service.review(
        pending[0].id,
        expected_revision=revised.id,
        decisions={
            "asset_class": ReviewDecision(action="OVERRIDE", value="EQUITY", evidence=(proof,))
        },
        actor="reviewer",
        reason="second proposal",
        can_review=True,
        reviewed_at=T2,
    )
    assert service.latest(product.id).version == 3
