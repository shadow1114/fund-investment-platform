from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fip.api.app import create_app
from fip.platform.jobs.executor import JobExecutor
from fip.settings import Settings

pytestmark = pytest.mark.integration


def test_plan6_local_flow(db_engine, db_session):
    app = create_app(
        settings_override=Settings(database_url=str(db_engine.url)),
        persistent_operations=True,
        strict_contracts=True,
    )
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        created = client.post(
            "/api/v1/backtests",
            json={
                "strategy_id": "STRAT-1",
                "start_date": "2020-01-01",
                "end_date": "2020-12-31",
                "initial_capital": {"amount": 100000, "currency": "CNY"},
                "backtest_mode": "HISTORICAL_FIDELITY",
                "benchmark_id": "BM-1",
                "equal_weight_baseline_enabled": True,
                "rebalancing_policy_version": "rebal-v1",
                "portfolio_rule_version": "portfolio-v1",
                "return_estimate_version": "return-v1",
                "risk_model_version": "risk-v1",
                "eligibility_rules_version": "eligibility-v1",
                "transaction_cost_model_version": "cost-v1",
                "execution_price_rule": "CLOSE",
                "cash_return_assumption": "ZERO",
                "infeasible_handling": "ABORT",
            },
        )
        assert created.status_code == 201
        backtest_id = created.json()["data"]["backtest_id"]
        submitted = client.post(
            f"/api/v1/backtests/{backtest_id}/runs",
            headers={"Idempotency-Key": "plan6-run-1"},
        )
        assert submitted.status_code == 202
        operation_id = submitted.json()["data"]["operation_id"]

        with Session(db_engine, future=True) as worker_session:
            executor = JobExecutor()
            executor.execute_one(worker_session, "plan6-worker", datetime.now(UTC))
            worker_session.commit()

        polled = client.get(f"/api/v1/operations/{operation_id}")

    assert polled.status_code == 200
    assert polled.json()["data"]["status"] == "FAILED"
    assert polled.json()["data"]["failure"]["code"] == "HANDLER_UNAVAILABLE"
