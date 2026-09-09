import datetime as dt

import pytest

from fip.services.data_service.models.governance import PolicyVersion
from fip.services.factor_service.models import FactorDefinition, FactorEffectiveness, FactorVersion
from fip.services.factor_service.validation import (
    EffectivenessEvidence,
    validate_and_save_effectiveness,
    validate_and_save_effectiveness_series,
)
from fip.services.fund_service.models import PeerGroupSnapshot
from fip.strategy_library.validation import EffectivenessThresholds

pytestmark = pytest.mark.integration


def test_oos_effectiveness_is_versioned_and_persisted(db_session):
    evaluation_policy = PolicyVersion(
        policy_kind="evaluation", version_label="effectiveness-eval-v1", content={}
    )
    validation_policy = PolicyVersion(
        policy_kind="validation", version_label="effectiveness-validation-v1", content={}
    )
    db_session.add_all((evaluation_policy, validation_policy))
    definition = FactorDefinition(
        factor_id="F-REL-002", display_name="Alpha", usage="SCORING"
    )
    db_session.add(definition)
    db_session.flush()
    version = FactorVersion(
        factor_definition_id=definition.id,
        version_label="v1",
        parameters={"window": "3Y"},
    )
    peer = PeerGroupSnapshot(
        decision_id="effectiveness-decision",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=evaluation_policy.id,
        classification_code="ACTIVE_EQUITY",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=3,
    )
    db_session.add_all((version, peer))
    db_session.flush()

    persisted = validate_and_save_effectiveness(
        db_session,
        factor_version_id=version.id,
        peer_group_snapshot_id=peer.id,
        evaluation_window="3Y",
        sample_split="2025-01-01/2026-09-08",
        validation_policy_version_id=validation_policy.id,
        observations=((1.0, 1.0), (2.0, 2.0), (3.0, 3.0)),
        minimum_observations=3,
    )

    row = db_session.get(FactorEffectiveness, persisted.effectiveness_id)
    assert row is not None
    assert row.verdict == "VALID"
    assert row.detail["ic"] == pytest.approx(1.0)
    assert row.detail["reason_code"] is None


def test_oos_effectiveness_persists_validation_pending(db_session):
    evaluation_policy = PolicyVersion(
        policy_kind="evaluation", version_label="pending-eval-v1", content={}
    )
    validation_policy = PolicyVersion(
        policy_kind="validation", version_label="pending-validation-v1", content={}
    )
    db_session.add_all((evaluation_policy, validation_policy))
    definition = FactorDefinition(
        factor_id="F-RISK-003", display_name="Maximum Drawdown", usage="SCORING"
    )
    db_session.add(definition)
    db_session.flush()
    version = FactorVersion(
        factor_definition_id=definition.id,
        version_label="v1",
        parameters={"window": "3Y"},
    )
    peer = PeerGroupSnapshot(
        decision_id="pending-effectiveness",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=evaluation_policy.id,
        classification_code="BOND",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=0,
    )
    db_session.add_all((version, peer))
    db_session.flush()

    persisted = validate_and_save_effectiveness(
        db_session,
        factor_version_id=version.id,
        peer_group_snapshot_id=peer.id,
        evaluation_window="3Y",
        sample_split="2025-01-01/2026-09-08",
        validation_policy_version_id=validation_policy.id,
        observations=(),
        minimum_observations=3,
    )

    assert persisted.verdict == "VALIDATION_PENDING"


def test_oos_effectiveness_requires_full_history_and_recent_3y(db_session):
    evaluation_policy = PolicyVersion(
        policy_kind="evaluation", version_label="dual-segment-eval-v1", content={}
    )
    validation_policy = PolicyVersion(
        policy_kind="validation", version_label="dual-segment-validation-v1", content={}
    )
    db_session.add_all((evaluation_policy, validation_policy))
    definition = FactorDefinition(factor_id="F-RAP-001", display_name="Sharpe", usage="SCORING")
    db_session.add(definition)
    db_session.flush()
    version = FactorVersion(
        factor_definition_id=definition.id, version_label="v1", parameters={}
    )
    peer = PeerGroupSnapshot(
        decision_id="dual-segment-effectiveness",
        decision_at=dt.date(2026, 9, 8),
        policy_version_id=evaluation_policy.id,
        classification_code="ACTIVE_EQUITY",
        base_currency="CNY",
        status="AVAILABLE",
        member_count=30,
    )
    db_session.add_all((version, peer))
    db_session.flush()

    persisted = validate_and_save_effectiveness_series(
        db_session,
        factor_version_id=version.id,
        peer_group_snapshot_id=peer.id,
        evaluation_window="3Y",
        sample_split="FULL_HISTORY+RECENT_3Y",
        validation_policy_version_id=validation_policy.id,
        evidence=EffectivenessEvidence(
            ic_series=(0.1, 0.2, 0.3),
            layer_returns=(0.01, 0.02, 0.03),
            expected_direction="POSITIVE",
            recent_ic_series=(0.01, 0.02),
            recent_layer_returns=(0.01, 0.02, 0.03),
        ),
        thresholds=EffectivenessThresholds(0.02, 0.3, 3, 1, 0.8),
        require_both_segments=True,
    )

    assert persisted.verdict == "VALIDATION_PENDING"
    assert persisted.detail["reason_code"] == "RECENT_3Y_INSUFFICIENT_OOS_CROSS_SECTIONS"
    assert persisted.detail["segments"]["full_history"]["verdict"] == "VALID"