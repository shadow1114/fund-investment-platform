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


def test_0017_backfills_existing_share_classes_before_not_null(db_engine):
    _alembic("downgrade", "0016")
    try:
        with db_engine.begin() as connection:
            fund_id = connection.execute(
                text(
                    "INSERT INTO fund.fund "
                    "(fund_code, product_name, grouping_status) "
                    "VALUES ('P-MIG-0017', 'migration probe', 'CONFIRMED') "
                    "RETURNING id"
                )
            ).scalar_one()
            share_class_id = connection.execute(
                text(
                    "INSERT INTO fund.fund_share_class "
                    "(fund_id, share_class_code, display_name) "
                    "VALUES (:fund_id, 'A', 'migration probe A') "
                    "RETURNING id"
                ),
                {"fund_id": fund_id},
            ).scalar_one()

        _alembic("upgrade", "0017")

        with db_engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT base_currency "
                    "FROM fund.fund_share_class WHERE id = :share_class_id"
                ),
                {"share_class_id": share_class_id},
            ).one()
            assert row.base_currency == "CNY"
            connection.execute(
                text("DELETE FROM fund.fund_share_class WHERE id = :share_class_id"),
                {"share_class_id": share_class_id},
            )
            connection.execute(
                text("DELETE FROM fund.fund WHERE id = :fund_id"),
                {"fund_id": fund_id},
            )
    finally:
        _alembic("upgrade", "head")
