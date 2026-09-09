import datetime as dt

import pytest

from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.repositories import FactorRepository
from fip.services.fund_service.models import (
    FundEvaluation,
    PeerGroupSnapshot,
    SelectionConditionRecord,
)
from fip.services.fund_service.universe import UniverseRepository
from fip.strategy_library.universe import SelectionCondition, evaluate_candidate

pytestmark = pytest.mark.integration


def test_universe_persists_rejected_member_and_all_conditions(db_session):
    policy = PolicyVersion(policy_kind="evaluation", version_label="universe-v1", content={})
    db_session.add(policy)
    fund = Fund(fund_code="universe-fund", product_name="Universe", grouping_status="CONFIRMED")
    db_session.add(fund)
    db_session.flush()
    share_class = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="Universe A")
    db_session.add(share_class)
    db_session.flush()
    peer = PeerGroupSnapshot(
        decision_id="universe-decision",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=policy.id,
        classification_code="BOND",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=1,
    )
    db_session.add(peer)
    db_session.flush()
    factor_run_id = FactorRepository(db_session).save_run(
        decision_id="universe-decision",
        peer_group_snapshot_id=peer.id,
        metric_version_id=policy.id,
        evaluation_policy_version_id=policy.id,
        input_quality_summary={},
    )
    evaluation = FundEvaluation(
        decision_id="universe-decision",
        peer_group_snapshot_id=peer.id,
        factor_run_id=factor_run_id,
        policy_version_id=policy.id,
    )
    db_session.add(evaluation)
    db_session.flush()
    decision = evaluate_candidate(
        (
            SelectionCondition("eligible", "AVAILABLE", True),
            SelectionCondition("score", "UNAVAILABLE", None),
        )
    )
    UniverseRepository(db_session).save(
        decision_id="universe-decision",
        evaluation_id=evaluation.id,
        policy_version_id=policy.id,
        members=((share_class.id, decision),),
    )
    assert db_session.query(SelectionConditionRecord).count() == 2


def test_universe_supports_multiple_peer_group_evaluations_for_one_decision(db_session):
    policy = PolicyVersion(policy_kind="evaluation", version_label="multi-group-v1", content={})
    db_session.add(policy)
    fund = Fund(
        fund_code="multi-group-fund",
        product_name="Multi Group",
        grouping_status="CONFIRMED",
    )
    db_session.add(fund)
    db_session.flush()
    shares = (
        FundShareClass(fund_id=fund.id, share_class_code="A", display_name="Multi A"),
        FundShareClass(fund_id=fund.id, share_class_code="B", display_name="Multi B"),
    )
    db_session.add_all(shares)
    db_session.flush()
    repository = UniverseRepository(db_session)
    for share, classification in zip(shares, ("ACTIVE_EQUITY", "BOND"), strict=True):
        peer = PeerGroupSnapshot(
            decision_id="multi-group-decision",
            decision_at=dt.date(2026, 9, 8),
            policy_version_id=policy.id,
            classification_code=classification,
            base_currency="CNY",
            status="AVAILABLE",
            member_count=1,
        )
        db_session.add(peer)
        db_session.flush()
        factor_run_id = FactorRepository(db_session).save_run(
            decision_id="multi-group-decision",
            peer_group_snapshot_id=peer.id,
            metric_version_id=policy.id,
            evaluation_policy_version_id=policy.id,
            input_quality_summary={"group": classification},
        )
        evaluation = FundEvaluation(
            decision_id="multi-group-decision",
            peer_group_snapshot_id=peer.id,
            factor_run_id=factor_run_id,
            policy_version_id=policy.id,
        )
        db_session.add(evaluation)
        db_session.flush()
        repository.save(
            decision_id="multi-group-decision",
            evaluation_id=evaluation.id,
            policy_version_id=policy.id,
            members=(
                (
                    share.id,
                    evaluate_candidate(
                        (SelectionCondition("eligible", "AVAILABLE", True),)
                    ),
                ),
            ),
        )

    assert db_session.query(SelectionConditionRecord).count() == 2
