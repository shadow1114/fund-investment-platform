from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fip.api.app import create_app
from fip.platform.jobs.models import CalculationJob

pytestmark = pytest.mark.integration


def test_history_filters_dates_before_count_and_pagination(db_engine):
    with Session(db_engine) as session:
        for day in (26, 27, 28):
            session.add(
                CalculationJob(
                    execution_id=f"history-time-{day}",
                    idempotency_key=f"history-time-{day}",
                    job_type="fund_nav_ingest",
                    status="RUNNING",
                    progress=0,
                    created_at=datetime(2026, 10, day, 12, tzinfo=UTC),
                    job_payload={
                        "dataset": "NAV",
                        "actor": "history-date-user",
                        "scope_type": "SINGLE",
                        "scoped_items": True,
                    },
                )
            )
        session.commit()
    app = create_app(persistent_operations=True, strict_contracts=True)
    app.state.api_engine = db_engine
    headers = {"X-Roles": "operations", "X-User-ID": "history-date-user"}
    with TestClient(app) as client:
        result = client.get(
            "/api/v1/fund-ingestions",
            headers=headers,
            params={
                "created_from": "2026-10-27T00:00:00Z",
                "created_to": "2026-10-27T23:59:59Z",
                "page_size": 1,
            },
        )
        assert result.status_code == 200, result.text
        data = result.json()["data"]
        assert data["total"] == 1
        assert [item["operation_id"] for item in data["items"]] == ["history-time-27"]
        second = client.get(
            "/api/v1/fund-ingestions",
            headers=headers,
            params={"created_from": "2026-10-27T12:00:00Z", "page": 2, "page_size": 1},
        ).json()["data"]
        assert second["total"] == 2
        assert [item["operation_id"] for item in second["items"]] == ["history-time-27"]
