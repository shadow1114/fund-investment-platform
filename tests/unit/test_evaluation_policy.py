from decimal import Decimal
from pathlib import Path

from fip.platform.decision_data.context import RuntimeMode
from fip.services.fund_service.policy import load_evaluation_policy


def test_evaluation_policy_v1_matches_decided_contract():
    policy = load_evaluation_policy(Path("config/policy/evaluation/v1.yaml"), RuntimeMode.BACKTEST)

    assert set(policy.profile_weights) == {"active_equity", "passive_equity", "bond", "hybrid"}
    assert all(sum(weights.values()) == Decimal(1) for weights in policy.profile_weights.values())
    assert policy.minimum_peer_group_size == 30
    assert policy.mar == Decimal(0)
    assert all("r_squared" not in weights for weights in policy.profile_weights.values())
    assert policy.beta_target_ranges == {
        "active_equity": (Decimal("0.85"), Decimal("1.15")),
        "passive_equity": (Decimal("0.98"), Decimal("1.02")),
        "bond": (Decimal("0.90"), Decimal("1.10")),
        "hybrid": (Decimal("0.90"), Decimal("1.10")),
    }
