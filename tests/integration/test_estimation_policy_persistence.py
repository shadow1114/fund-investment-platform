from dataclasses import replace
from pathlib import Path

import pytest

from fip.platform.decision_data.context import RuntimeMode
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.portfolio_service.estimation.policy import (
    EstimationPolicyVersionConflict,
    load_estimation_policy,
    load_estimation_validation_policy,
    persist_estimation_policy_version,
    persist_estimation_validation_policy_version,
)

pytestmark = pytest.mark.integration

VALIDATION = Path("config/policy/estimation/validation_v1.yaml")


def test_estimation_policy_is_versioned_and_idempotent(db_session):
    policy = load_estimation_policy(
        Path("config/policy/estimation/v1.yaml"), RuntimeMode.LIVE
    )

    first = persist_estimation_policy_version(db_session, policy)
    second = persist_estimation_policy_version(db_session, policy)

    assert second == first
    row = db_session.get(PolicyVersion, first)
    assert row is not None
    assert row.policy_kind == "estimation"
    assert row.content["primary_return_basis"] == "ABSOLUTE"
    assert row.content["secondary_return_bases"] == ["EXCESS"]


def test_estimation_policy_version_rejects_different_content(db_session):
    policy = load_estimation_policy(
        Path("config/policy/estimation/v1.yaml"), RuntimeMode.LIVE
    )
    persist_estimation_policy_version(db_session, policy)

    with pytest.raises(EstimationPolicyVersionConflict):
        persist_estimation_policy_version(
            db_session,
            replace(policy, lookback_trading_days=252),
        )


def test_validation_policy_persists_as_distinct_kind(db_session):
    policy = load_estimation_validation_policy(VALIDATION, RuntimeMode.LIVE)
    row_id = persist_estimation_validation_policy_version(db_session, policy)

    row = db_session.get(PolicyVersion, row_id)
    assert row is not None
    assert row.policy_kind == "estimation_validation"


def test_validation_policy_version_rejects_different_content(db_session):
    policy = load_estimation_validation_policy(VALIDATION, RuntimeMode.LIVE)
    persist_estimation_validation_policy_version(db_session, policy)

    with pytest.raises(EstimationPolicyVersionConflict):
        persist_estimation_validation_policy_version(
            db_session,
            replace(policy, condition_reject=1.0e5),
        )
