import datetime as dt

import pytest

from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.repositories import FactorRepository, FactorRunConflict
from fip.services.fund_service.models import PeerGroupSnapshot

pytestmark = pytest.mark.integration


def test_factor_run_idempotency_key_reuses_same_run(db_session):
    policy = PolicyVersion(policy_kind="metric", version_label="test-v1", content={})
    db_session.add(policy)
    db_session.flush()
    snapshot = PeerGroupSnapshot(
        decision_id="decision-1",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=policy.id,
        classification_code="BOND",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=0,
    )
    db_session.add(snapshot)
    db_session.flush()
    repository = FactorRepository(db_session)
    first = repository.save_run(
        decision_id="decision-1",
        peer_group_snapshot_id=snapshot.id,
        metric_version_id=policy.id,
        evaluation_policy_version_id=None,
        input_quality_summary={"quality": "EXACT"},
    )
    second = repository.save_run(
        decision_id="decision-1",
        peer_group_snapshot_id=snapshot.id,
        metric_version_id=policy.id,
        evaluation_policy_version_id=None,
        input_quality_summary={"quality": "EXACT"},
    )
    assert second == first
    with pytest.raises(FactorRunConflict):
        repository.save_run(
            decision_id="decision-1",
            peer_group_snapshot_id=snapshot.id,
            metric_version_id=policy.id,
            evaluation_policy_version_id=None,
            input_quality_summary={"quality": "INFERRED"},
        )
