import os
import subprocess

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


def _alembic(*arguments: str) -> None:
    environment = os.environ.copy()
    environment.setdefault("LC_ALL", "en_US.UTF-8")
    subprocess.run(
        [".venv/bin/alembic", "-x", "db=test", *arguments],
        check=True,
        env=environment,
    )


def test_0040_adds_nullable_projection_to_old_fund_and_reverses_cleanly(db_engine):
    _alembic("downgrade", "0039")
    with db_engine.begin() as connection:
        fund_id = connection.execute(
            text(
                "INSERT INTO fund.fund "
                "(fund_code, product_name, grouping_status) "
                "VALUES ('P-MIG-0040', 'existing fund', 'CONFIRMED') RETURNING id"
            )
        ).scalar_one()

    try:
        _alembic("upgrade", "0040")
        with db_engine.connect() as connection:
            row = connection.execute(
                text("SELECT company_name FROM fund.fund WHERE id=:fund_id"),
                {"fund_id": fund_id},
            ).one()
            assert row.company_name is None

        _alembic("downgrade", "0039")
        with db_engine.connect() as connection:
            exists = connection.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='fund' AND table_name='fund' "
                    "AND column_name='company_name'"
                )
            ).scalar_one_or_none()
            assert exists is None
            assert connection.execute(
                text("SELECT 1 FROM fund.fund WHERE id=:fund_id"),
                {"fund_id": fund_id},
            ).scalar_one()
    finally:
        _alembic("upgrade", "head")
        with db_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM fund.fund WHERE id=:fund_id"), {"fund_id": fund_id}
            )
