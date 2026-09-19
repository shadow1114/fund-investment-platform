from __future__ import annotations

from sqlalchemy import delete

from fip.api.operations import PersistentOperationService
from fip.platform.jobs.models import CalculationJob


def test_persistent_operation_idempotency_and_resource_reference(db_session) -> None:
    key = "api-operation|integration|stable"
    db_session.execute(delete(CalculationJob).where(CalculationJob.idempotency_key == key))
    first = PersistentOperationService(db_session).submit(
        "optimization", "OPT-1", key, result_ref="/api/v1/portfolios/P-1/optimizations/OPT-1"
    )
    second = PersistentOperationService(db_session).submit(
        "optimization", "OPT-2", key, result_ref="/api/v1/portfolios/P-1/optimizations/OPT-2"
    )
    assert first.operation_id == second.operation_id
    assert first.resource_id == second.resource_id == "OPT-1"
    assert first.result_ref == "/api/v1/portfolios/P-1/optimizations/OPT-1"
