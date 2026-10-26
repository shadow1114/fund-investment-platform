from __future__ import annotations

import pytest
from sqlalchemy import text

from fip.api.app import create_app


@pytest.mark.integration
def test_postgres_is_available_for_plan7_contract_acceptance(db_session) -> None:  # type: ignore[no-untyped-def]
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.integration
def test_api_route_models_cover_all_nested_domains() -> None:
    app = create_app(strict_contracts=True)
    operation_ids = {
        route.operation_id for route in app.routes if getattr(route, "operation_id", None)
    }
    assert {
        "listFunds",
        "getFund",
        "getFundNavSeries",
        "getFundEvaluations",
        "getFundScores",
        "listUniverses",
        "getUniverse",
        "listPortfolios",
        "getPortfolio",
        "submitOptimization",
        "getOptimization",
        "getDecision",
        "reviewDecision",
        "createBacktest",
        "validateBacktest",
        "runBacktest",
        "getBacktestStatus",
        "getBacktestResult",
        "getBacktestPerformance",
        "getBacktestBiasCheck",
    } <= operation_ids
