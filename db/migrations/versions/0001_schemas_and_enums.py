"""8 个 schema 与共享枚举类型

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = (
    "raw", "fund", "market", "factor",
    "evaluation", "portfolio", "backtest", "governance",
)


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    op.execute(
        "CREATE TYPE availability_quality_enum "
        "AS ENUM ('EXACT', 'DERIVED', 'INFERRED')"
    )


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS availability_quality_enum")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
