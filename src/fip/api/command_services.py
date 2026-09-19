from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from fip.api.errors import InvalidQueryError
from fip.services.data_service.models.governance import AuditLog


class DecisionCommandService:
    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def review(
        self,
        decision_id: str,
        action: str,
        reason: str | None,
        principal_id: str,
        original_weights: Any,
        final_weights: Any,
        request_id: str | None,
    ) -> dict[str, Any]:
        if action not in {"APPROVED", "REJECTED", "OVERRIDDEN"}:
            raise InvalidQueryError("action must be APPROVED, REJECTED, or OVERRIDDEN")
        if not reason or not reason.strip():
            raise InvalidQueryError("reason is required for decision reviews")
        audit_id = f"AUD-{decision_id}-{principal_id}"
        if self._session is not None:
            audit = AuditLog(
                resource_type="decision",
                resource_id=decision_id,
                action=action,
                operator=principal_id,
                detail={"reason": reason, "request_id": request_id},
            )
            self._session.add(audit)
            self._session.flush()
            audit_id = str(audit.id)
        return {
            "decision_id": decision_id,
            "decision_status": action,
            "reviewed_by": principal_id,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "original_weights": original_weights,
            "final_weights": final_weights,
            "audit_id": audit_id,
        }


def validate_optimization_request(payload: dict[str, Any]) -> None:
    required = {
        "decision_at",
        "universe_id",
        "portfolio_rule_version",
        "return_estimate_version",
        "risk_model_version",
        "mode",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise InvalidQueryError(f"Missing optimization fields: {', '.join(missing)}")
    if payload["mode"] != "REBALANCE":
        raise InvalidQueryError("Invalid optimization mode")
    from datetime import date

    try:
        date.fromisoformat(str(payload["decision_at"]))
    except ValueError as error:
        raise InvalidQueryError("decision_at must be an ISO date") from error


def validate_backtest_configuration(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "strategy_id",
        "start_date",
        "end_date",
        "initial_capital",
        "backtest_mode",
        "benchmark_id",
        "equal_weight_baseline_enabled",
        "rebalancing_policy_version",
        "portfolio_rule_version",
        "return_estimate_version",
        "risk_model_version",
        "eligibility_rules_version",
        "transaction_cost_model_version",
        "execution_price_rule",
        "cash_return_assumption",
        "infeasible_handling",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise InvalidQueryError(f"Missing backtest fields: {', '.join(missing)}")
    if payload["backtest_mode"] not in {"HISTORICAL_FIDELITY", "CURRENT_RULE"}:
        raise InvalidQueryError("Invalid backtest_mode")
    if payload["infeasible_handling"] not in {"ABORT", "SKIP_PERIOD"}:
        raise InvalidQueryError("Invalid infeasible_handling")
    capital = payload["initial_capital"]
    if not isinstance(capital, dict) or not {"amount", "currency"} <= set(capital):
        raise InvalidQueryError("initial_capital must contain amount and currency")
    from datetime import date

    try:
        start = date.fromisoformat(str(payload["start_date"]))
        end = date.fromisoformat(str(payload["end_date"]))
    except ValueError as error:
        raise InvalidQueryError("start_date and end_date must be ISO dates") from error
    if end < start:
        raise InvalidQueryError("start_date must not be after end_date")
    days = (end - start).days + 1
    return {
        "validation_result": "PASS",
        "warm_up_end_date": start.isoformat(),
        "effective_period": {"from": start.isoformat(), "to": end.isoformat()},
        "in_sample_length_days": days,
        "out_of_sample_length_days": 0,
        "warnings": [],
        "blocking_issues": [],
    }
