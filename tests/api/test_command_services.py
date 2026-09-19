from __future__ import annotations

import pytest

from fip.api.command_services import DecisionCommandService, validate_backtest_configuration
from fip.api.errors import InvalidQueryError


def test_backtest_validation_returns_contract_shape() -> None:
    payload = {
        "strategy_id": "S-1",
        "start_date": "2024-01-01",
        "end_date": "2024-01-10",
        "initial_capital": {"amount": "100000", "currency": "CNY"},
        "backtest_mode": "HISTORICAL_FIDELITY",
        "benchmark_id": "CSI300",
        "equal_weight_baseline_enabled": True,
        "rebalancing_policy_version": "r1",
        "portfolio_rule_version": "p1",
        "return_estimate_version": "ret1",
        "risk_model_version": "risk1",
        "eligibility_rules_version": "e1",
        "transaction_cost_model_version": "tc1",
        "execution_price_rule": "CLOSE",
        "cash_return_assumption": "ZERO",
        "infeasible_handling": "ABORT",
    }
    result = validate_backtest_configuration(payload)
    assert result["validation_result"] == "PASS"
    assert result["effective_period"] == {"from": "2024-01-01", "to": "2024-01-10"}


def test_backtest_validation_rejects_missing_fields() -> None:
    with pytest.raises(InvalidQueryError, match="Missing backtest fields"):
        validate_backtest_configuration({})


def test_decision_review_requires_reason_for_override() -> None:
    with pytest.raises(InvalidQueryError, match="reason is required"):
        DecisionCommandService().review("D-1", "OVERRIDDEN", None, "reviewer", [], [], None)
