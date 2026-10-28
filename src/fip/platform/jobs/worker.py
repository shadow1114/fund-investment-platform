from __future__ import annotations

import argparse
import signal
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fip.platform.jobs.executor import JobExecutor
from fip.platform.jobs.fund_classification import handle_fund_classification
from fip.platform.jobs.fund_ingestion import handle_fund_ingestion
from fip.settings import settings


def _job_executor() -> JobExecutor:
    return JobExecutor(
        {
            "fund_basic_info_ingest": handle_fund_ingestion,
            "fund_nav_ingest": handle_fund_ingestion,
            "fund_classification_refresh": handle_fund_classification,
            "fund_classification_index_sets": handle_fund_classification,
        },
        lease_seconds=settings.worker_lease_seconds,
    )


def run_once(*, worker_id: str | None = None) -> bool:
    engine = create_engine(settings.database_url, future=True)
    try:
        with Session(engine, future=True) as session:
            executor = _job_executor()
            outcome = executor.execute_one(
                session,
                worker_id or f"worker-{uuid.uuid4().hex[:8]}",
                datetime.now(UTC),
            )
            session.commit()
            return outcome is not None
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local PostgreSQL calculation jobs")
    parser.add_argument("--once", action="store_true", help="process one job and exit")
    args = parser.parse_args()
    if args.once:
        run_once()
        return

    stopped = False

    def stop(*_: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while not stopped:
        if not run_once():
            import time

            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
