from __future__ import annotations

from datetime import date

import pytest

from fip.api.repositories import FundRepository, UniverseRepository
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.models import FactorRun
from fip.services.fund_service.models import (
    FundEvaluation,
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupMember,
    PeerGroupSnapshot,
)


@pytest.mark.integration
def test_production_fund_and_universe_repositories_read_persisted_rows(db_session) -> None:
    """Replacing ORM reads with fake hooks would make this seeded production data invisible."""
    policy = PolicyVersion(policy_kind="EVALUATION", version_label="v1", content={})
    fund = Fund(fund_code="F-1", product_name="Concrete Fund", grouping_status="GROUPED")
    db_session.add_all([policy, fund])
    db_session.flush()
    share_class = FundShareClass(
        fund_id=fund.id,
        share_class_code="A",
        display_name="Concrete Fund A",
        inception_date=date(2024, 1, 1),
    )
    peer_group = PeerGroupSnapshot(
        decision_id="decision-1",
        classification_code="EQUITY",
        base_currency="CNY",
        policy_version_id=policy.id,
        decision_at=date(2025, 1, 31),
        status="COMPLETED",
        member_count=1,
    )
    db_session.add_all([share_class, peer_group])
    db_session.flush()
    factor_run = FactorRun(
        decision_id="decision-1",
        peer_group_snapshot_id=peer_group.id,
        metric_version_id=policy.id,
        evaluation_policy_version_id=policy.id,
        input_quality_summary={},
    )
    db_session.add(factor_run)
    db_session.flush()
    evaluation = FundEvaluation(
        decision_id="decision-1",
        peer_group_snapshot_id=peer_group.id,
        factor_run_id=factor_run.id,
        policy_version_id=policy.id,
    )
    db_session.add_all(
        [
            PeerGroupMember(
                snapshot_id=peer_group.id,
                share_class_id=share_class.id,
                status="INCLUDED",
            ),
            evaluation,
        ]
    )
    db_session.flush()
    snapshot = FundUniverseSnapshot(
        decision_id="strategy-1",
        evaluation_id=evaluation.id,
        policy_version_id=policy.id,
    )
    db_session.add(snapshot)
    db_session.flush()
    db_session.add(
        FundUniverseMember(
            snapshot_id=snapshot.id,
            share_class_id=share_class.id,
            status="SELECTED",
        )
    )
    db_session.flush()

    funds = FundRepository(db_session).list(as_of_date="2025-01-31")
    universe_repository = UniverseRepository(db_session)
    universes = universe_repository.list()
    members = universe_repository.read_members(str(snapshot.id))

    assert funds[0]["fund_id"] == "F-1"
    assert universes == [
        {
            "universe_id": str(snapshot.id),
            "strategy_id": "strategy-1",
            "decision_at": "2025-01-31",
            "universe_strategy": "UNKNOWN",
            "member_count": 1,
            "eligibility_rules_version": str(policy.id),
            "scoring_policy_version": str(policy.id),
        }
    ]
    assert members["members"][0]["fund_id"] == "F-1"
    assert members["excluded"] == []
