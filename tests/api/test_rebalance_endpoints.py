from __future__ import annotations

from fastapi.testclient import TestClient

from fip.api.app import create_app


def test_get_live_portfolio() -> None:
    client = TestClient(create_app(enable_m2_rebalance=True))
    response = client.get("/api/v1/portfolios/P-TEST-1/live")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["portfolio_id"] == "P-TEST-1"
    assert data["status"] == "ACTIVE"
    assert data["has_pending_execution"] is False
    assert len(data["target_positions"]) == 2
    # Actual positions start empty (never fake actual with target)
    assert len(data["actual_positions"]) == 0


def test_submit_execution_report_updates_live_state() -> None:
    client = TestClient(create_app(enable_m2_rebalance=True))
    payload = {
        "report_id": "REP-001",
        "fund_id": "000001",
        "direction": "BUY",
        "requested_shares": 50000.0,
        "filled_shares": 50000.0,
        "filled_price": 1.0,
        "fee": 50.0,
        "status": "FILLED",
    }
    response = client.post("/api/v1/portfolios/P-TEST-1/execution-reports", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report_id"] == "REP-001"
    assert data["status"] == "ACTIVE"
    assert data["cash_balance"] == 100000.0 - 50050.0

    # Query live portfolio again to verify actual position is now present
    live_res = client.get("/api/v1/portfolios/P-TEST-1/live")
    live_data = live_res.json()["data"]
    actuals = live_data["actual_positions"]
    assert len(actuals) == 1
    assert actuals[0]["fund_id"] == "000001"
    assert actuals[0]["shares"] == 50000.0


def test_evaluate_rebalance_generates_trades_and_stores_history() -> None:
    client = TestClient(create_app(enable_m2_rebalance=True))
    payload = {
        "decision_at": "2026-03-31",
        "prices": {"000001": 1.2, "000002": 0.9},
        "fund_drift_threshold": 0.02,
        "min_trade_threshold": 0.001,
        "fee_rate": 0.0015,
        "expected_annualized_improvement": 0.05,
    }
    response = client.post("/api/v1/portfolios/P-TEST-1/rebalances/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "decision_outcome" in data
    assert "turnover" in data
    assert "trades" in data
    assert "explainability_summary" in data

    # Verify history query
    history_res = client.get("/api/v1/portfolios/P-TEST-1/rebalances")
    assert history_res.status_code == 200
    events = history_res.json()["data"]
    assert len(events) >= 1
    reb_id = events[0]["rebalance_id"]

    # Verify trade details query
    trades_res = client.get(f"/api/v1/rebalances/{reb_id}/trades")
    assert trades_res.status_code == 200
    trades_data = trades_res.json()["data"]
    assert len(trades_data) >= 1
