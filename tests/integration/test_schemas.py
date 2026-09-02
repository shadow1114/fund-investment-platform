import pytest
from sqlalchemy import text

from fip.platform.db.base import SCHEMAS

pytestmark = pytest.mark.integration


def test_all_eight_schemas_exist(db_engine):
    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT schema_name FROM information_schema.schemata")
        ).scalars().all()
    for schema in SCHEMAS:
        assert schema in rows, f"schema {schema} 缺失"


def test_availability_quality_enum_exists(db_engine):
    with db_engine.connect() as conn:
        labels = conn.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'availability_quality_enum' "
                "ORDER BY e.enumsortorder"
            )
        ).scalars().all()
    assert labels == ["EXACT", "DERIVED", "INFERRED"]
