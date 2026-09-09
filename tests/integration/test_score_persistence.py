import datetime as dt

import pytest

from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.repositories import FactorRepository
from fip.services.fund_service.models import (
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTier,
    PeerGroupSnapshot,
)
from fip.services.fund_service.ranking import rank_and_save
from fip.services.fund_service.scoring import ScoreCandidate, calculate_and_save
from fip.services.fund_service.tier import classify_and_save
from fip.strategy_library.scoring import ScoringItem

pytestmark = pytest.mark.integration


def test_score_ranking_and_tier_are_persisted_with_attribution(db_session):
    policy = PolicyVersion(policy_kind="evaluation", version_label="score-v1", content={})
    metric = PolicyVersion(policy_kind="metric", version_label="metric-v1", content={})
    db_session.add_all((policy, metric))
    fund = Fund(fund_code="score-fund", product_name="Score", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    shares = (
        FundShareClass(fund_id=fund.id, share_class_code="A", display_name="Score A"),
        FundShareClass(fund_id=fund.id, share_class_code="B", display_name="Score B"),
    )
    db_session.add_all(shares)
    db_session.flush()
    peer = PeerGroupSnapshot(
        decision_id="score-decision",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=policy.id,
        classification_code="BOND",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=2,
    )
    db_session.add(peer)
    db_session.flush()
    factor_run_id = FactorRepository(db_session).save_run(
        decision_id="score-decision",
        peer_group_snapshot_id=peer.id,
        metric_version_id=metric.id,
        evaluation_policy_version_id=policy.id,
        input_quality_summary={"quality": "EXACT"},
    )

    stage = calculate_and_save(
        db_session,
        decision_id="score-decision",
        peer_group_snapshot_id=peer.id,
        factor_run_id=factor_run_id,
        policy_version_id=policy.id,
        candidates=(
            ScoreCandidate(
                shares[0].id,
                (
                    ScoringItem(
                        "F-REL-002", 80.0, 0.6, "VALID", 0.03, None, "HIGHER_IS_BETTER", "3Y"
                    ),
                    ScoringItem(
                        "F-RISK-003", 70.0, 0.4, "VALID", -0.2, None, "LOWER_IS_BETTER", "3Y"
                    ),
                ),
            ),
            ScoreCandidate(
                shares[1].id,
                (
                    ScoringItem("F-REL-002", 60.0, 0.6, "VALID"),
                    ScoringItem("F-RISK-003", 50.0, 0.4, "VALID"),
                ),
            ),
        ),
        minimum_factors=2,
        minimum_completeness=0.8,
    )
    rankings = rank_and_save(db_session, stage, minimum_sample=2)
    classify_and_save(db_session, rankings, minimum_sample=2)

    assert db_session.query(FundScore).count() == 2
    assert db_session.query(FundScoreAttribution).count() == 4
    assert db_session.query(FundRanking).count() == 2
    assert db_session.query(FundTier).count() == 2
    best = db_session.query(FundScore).filter_by(share_class_id=shares[0].id).one()
    assert float(best.value) == pytest.approx(76.0)
    assert float(best.data_completeness) == pytest.approx(1.0)
    assert best.weight_source == "PROFILE_FIXED_V1"
    details = [row.detail for row in db_session.query(FundScoreAttribution).all()]
    assert {detail["verdict"] for detail in details} == {"INCLUDED"}
    assert all("weighted_contribution" in detail for detail in details)
    assert {detail["window"] for detail in details if detail["window"] is not None} == {"3Y"}
    assert {detail["direction"] for detail in details if detail["direction"] is not None} == {
        "HIGHER_IS_BETTER",
        "LOWER_IS_BETTER",
    }


def test_score_persists_validation_pending_without_numeric_value(db_session):
    policy = PolicyVersion(policy_kind="evaluation", version_label="pending-v1", content={})
    metric = PolicyVersion(policy_kind="metric", version_label="pending-metric-v1", content={})
    db_session.add_all((policy, metric))
    fund = Fund(fund_code="pending-fund", product_name="Pending", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    share = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="Pending A")
    db_session.add(share)
    peer = PeerGroupSnapshot(
        decision_id="pending-decision",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=policy.id,
        classification_code="BOND",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=1,
    )
    db_session.add(peer)
    db_session.flush()
    run_id = FactorRepository(db_session).save_run(
        decision_id="pending-decision",
        peer_group_snapshot_id=peer.id,
        metric_version_id=metric.id,
        evaluation_policy_version_id=policy.id,
        input_quality_summary={},
    )

    stage = calculate_and_save(
        db_session,
        decision_id="pending-decision",
        peer_group_snapshot_id=peer.id,
        factor_run_id=run_id,
        policy_version_id=policy.id,
        candidates=(
            ScoreCandidate(
                share.id,
                (ScoringItem("F-REL-002", 80.0, 1.0, "VALIDATION_PENDING"),),
            ),
        ),
        minimum_factors=1,
        minimum_completeness=0.0,
    )

    score = db_session.get(FundScore, stage.scores[0].score_id)
    assert score is not None
    assert score.value is None
    assert score.status == "VALIDATION_PENDING"
    assert score.reason_code == "OOS_PENDING"
    assert float(score.data_completeness) == pytest.approx(1.0)
    assert score.weight_source == "PROFILE_FIXED_V1"