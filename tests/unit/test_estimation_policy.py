from pathlib import Path

import pytest

from fip.platform.decision_data.context import RuntimeMode
from fip.services.portfolio_service.estimation.policy import load_estimation_policy


def test_estimation_policy_v1_matches_decided_contract():
    policy = load_estimation_policy(
        Path("config/policy/estimation/v1.yaml"), RuntimeMode.LIVE
    )

    assert policy.lookback_trading_days == 756
    assert policy.forecast_horizon == policy.rebalance_frequency == "QUARTER"
    assert policy.primary_return_basis == "ABSOLUTE"
    assert policy.secondary_return_bases == ("EXCESS",)
    assert policy.return_method == "HISTORICAL_MEAN_JAMES_STEIN"
    assert policy.covariance_method == "LEDOIT_WOLF_CONSTANT_CORRELATION"
    assert policy.provisional_parameters == ()


def test_live_estimation_rejects_provisional_parameters(tmp_path: Path):
    source = Path("config/policy/estimation/v1.yaml").read_text(encoding="utf-8")
    policy_path = tmp_path / "v2.yaml"
    policy_path.write_text(source.replace("status: DECIDED", "status: PROVISIONAL", 1))

    with pytest.raises(ValueError, match="LIVE estimation rejects provisional"):
        load_estimation_policy(policy_path, RuntimeMode.LIVE)

    research_policy = load_estimation_policy(policy_path, RuntimeMode.BACKTEST)
    assert research_policy.provisional_parameters == ("window.lookback_trading_days",)


def test_estimation_policy_rejects_horizon_mismatch(tmp_path: Path):
    source = Path("config/policy/estimation/v1.yaml").read_text(encoding="utf-8")
    policy_path = tmp_path / "v2.yaml"
    policy_path.write_text(
        source.replace("value: QUARTER", "value: MONTH", 1), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="forecast horizon must equal"):
        load_estimation_policy(policy_path, RuntimeMode.BACKTEST)