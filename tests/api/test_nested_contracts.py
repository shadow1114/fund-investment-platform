from __future__ import annotations

from pydantic import ValidationError
import pytest

from fip.api.schemas import (
    BacktestBiasCheckPayloadModel,
    BacktestResultPayloadModel,
    DecisionPayloadModel,
    OptimizationPayloadModel,
    PortfolioPayloadModel,
    UniversePayloadModel,
)


def _weight() -> dict[str, object]:
    return {"fund_id": "000001", "weight": 1.0}


def valid_universe() -> dict[str, object]:
    member = {
        "fund_id": "000001",
        "selection_status": "SELECTED",
        "total_score": 80.0,
        "total_score_status": "VALID",
        "total_score_reason": None,
        "rank": 1,
        "rank_status": "VALID",
        "rank_reason": None,
        "percentile": 0.99,
        "percentile_status": "VALID",
        "percentile_reason": None,
        "fund_tier": "A",
        "investment_eligibility": "FULLY_ELIGIBLE",
        "passed_conditions": [],
        "failed_conditions": [],
    }
    return {
        "universe_id": "U-1",
        "decision_at": "2024-12-31",
        "universe_strategy": "A",
        "members": [member],
        "excluded": [],
    }


def valid_portfolio() -> dict[str, object]:
    return {
        "portfolio_id": "P-1",
        "portfolio_name": "Demo",
        "portfolio_type": "MODEL",
        "status": "ACTIVE",
        "base_currency": "CNY",
        "portfolio_version": "v1",
        "risk_profile": "BALANCED",
        "portfolio_benchmark": {
            "benchmark_id": "BM-1",
            "benchmark_name": "CSI 300",
            "benchmark_type": "INDEX",
            "mapping_version": "v1",
            "components": [],
        },
        "portfolio_rule_version": "v1",
    }


def valid_optimization() -> dict[str, object]:
    return {
        "optimization_id": "O-1",
        "optimization_status": "OPTIMAL",
        "target_weights": [_weight()],
        "objective_value": 1.0,
        "objective_value_status": "VALID",
        "objective_value_reason": None,
        "binding_constraints": [],
        "conflicting_constraints": [],
        "shadow_prices": {},
        "post_optimization_risk": {
            "portfolio_volatility": 0.1,
            "portfolio_volatility_status": "VALID",
            "portfolio_volatility_reason": None,
        },
        "excluded_candidates": [],
        "solve_path": "PRIMARY",
    }


def valid_decision() -> dict[str, object]:
    return {
        "decision_id": "D-1",
        "portfolio_id": "P-1",
        "optimization_id": "O-1",
        "decision_status": "PROPOSED",
        "proposed_weights": [_weight()],
        "review": None,
        "final_weights": None,
    }


def valid_backtest_result() -> dict[str, object]:
    metric = {
        "total_return": 0.1,
        "annualized_return": 0.1,
        "volatility": 0.2,
        "max_drawdown": -0.1,
        "sharpe_ratio": 0.5,
        "sharpe_ratio_status": "VALID",
        "sharpe_ratio_reason": None,
    }
    layer = {"passed": True, "passed_status": "VALID", "passed_reason": None}
    return {
        "backtest_id": "B-1",
        "status": "COMPLETED",
        "validation_status": "VALID",
        "backtest_mode": "HISTORICAL_FIDELITY",
        "period": {"start_date": "2020-01-01", "end_date": "2024-12-31", "warm_up_end_date": "2020-02-01"},
        "initial_capital": {"amount": "100000", "currency": "CNY"},
        "final_value": {"amount": "110000", "currency": "CNY"},
        "summary": {"portfolio": metric, "benchmark": metric, "equal_weight_baseline": None, "equal_weight_baseline_status": "UNAVAILABLE", "equal_weight_baseline_reason": "NOT_REQUESTED"},
        "excess_return": {"vs_benchmark": 0.01, "vs_benchmark_status": "VALID", "vs_benchmark_reason": None, "vs_equal_weight": None, "vs_equal_weight_status": "UNAVAILABLE", "vs_equal_weight_reason": "NOT_REQUESTED"},
        "significance_verdict": {"overall": "CANNOT_DETERMINE", "thresholds_status": "UNKNOWN", "layers": {"statistical": {**layer, "bootstrap_ci_lower_vs_benchmark": None, "bootstrap_ci_lower_vs_benchmark_status": "UNAVAILABLE", "bootstrap_ci_lower_vs_benchmark_reason": "NO_DATA", "bootstrap_ci_lower_vs_equal_weight": None, "bootstrap_ci_lower_vs_equal_weight_status": "UNAVAILABLE", "bootstrap_ci_lower_vs_equal_weight_reason": "NO_DATA"}, "effect_size": {**layer, "ir_vs_benchmark": None, "ir_vs_benchmark_status": "UNAVAILABLE", "ir_vs_benchmark_reason": "NO_DATA", "ir_vs_equal_weight": None, "ir_vs_equal_weight_status": "UNAVAILABLE", "ir_vs_equal_weight_reason": "NO_DATA", "delta_sharpe_vs_benchmark": None, "delta_sharpe_vs_benchmark_status": "UNAVAILABLE", "delta_sharpe_vs_benchmark_reason": "NO_DATA", "delta_sharpe_vs_equal_weight": None, "delta_sharpe_vs_equal_weight_status": "UNAVAILABLE", "delta_sharpe_vs_equal_weight_reason": "NO_DATA"}, "robustness": {**layer, "outperform_ratio_vs_benchmark": None, "outperform_ratio_vs_benchmark_status": "UNAVAILABLE", "outperform_ratio_vs_benchmark_reason": "NO_DATA", "outperform_ratio_vs_equal_weight": None, "outperform_ratio_vs_equal_weight_status": "UNAVAILABLE", "outperform_ratio_vs_equal_weight_reason": "NO_DATA"}, "economic": {**layer, "annualized_return_improvement_vs_benchmark": None, "annualized_return_improvement_vs_benchmark_status": "UNAVAILABLE", "annualized_return_improvement_vs_benchmark_reason": "NO_DATA", "annualized_return_improvement_vs_equal_weight": None, "annualized_return_improvement_vs_equal_weight_status": "UNAVAILABLE", "annualized_return_improvement_vs_equal_weight_reason": "NO_DATA", "max_drawdown_improvement_vs_benchmark": None, "max_drawdown_improvement_vs_benchmark_status": "UNAVAILABLE", "max_drawdown_improvement_vs_benchmark_reason": "NO_DATA", "max_drawdown_improvement_vs_equal_weight": None, "max_drawdown_improvement_vs_equal_weight_status": "UNAVAILABLE", "max_drawdown_improvement_vs_equal_weight_reason": "NO_DATA"}}},
        "validation_summary": {"warnings": [], "invalid_reasons": []},
    }


def valid_bias_check() -> dict[str, object]:
    bias = {"status": "PASS", "violations": [], "reason": "ok", "affected_periods": 0, "unmodeled_costs": []}
    return {"backtest_id": "B-1", "checks": {"look_ahead_bias": bias, "survivorship_bias": bias, "tradability_bias": bias, "point_in_time": {**bias, "availability_quality_distribution": {"EXACT": 1.0, "DERIVED": 0.0, "INFERRED": 0.0}}, "transaction_cost": bias, "subscription_redemption_lag": bias}, "snapshot_summary": {"snapshot_periods": 1, "rebuilt_periods": 1, "total_periods": 1, "rebuilt_period_list": ["2024-01-01"]}, "data_limitations": []}


@pytest.mark.parametrize(
    "factory,model",
    [
        (valid_universe, UniversePayloadModel),
        (valid_portfolio, PortfolioPayloadModel),
        (valid_optimization, OptimizationPayloadModel),
        (valid_decision, DecisionPayloadModel),
        (valid_backtest_result, BacktestResultPayloadModel),
        (valid_bias_check, BacktestBiasCheckPayloadModel),
    ],
)
def test_nested_domain_payload_rejects_unknown_fields(factory, model) -> None:  # type: ignore[no-untyped-def]
    payload = factory()
    payload["nested_unknown"] = True
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_backtest_result_keeps_all_significance_layers() -> None:
    result = BacktestResultPayloadModel.model_validate(valid_backtest_result())
    layers = result.significance_verdict.layers
    assert layers.statistical is not None
    assert layers.effect_size is not None
    assert layers.robustness is not None
    assert layers.economic is not None
