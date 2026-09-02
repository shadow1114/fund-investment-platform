"""calculation_job 表与 execution_status 枚举

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# 注意：必须用 postgresql.ENUM 而非 sa.Enum —— 通用的 sa.Enum 会【静默忽略】
# create_type=False，导致 SQLAlchemy 重复 CREATE TYPE 而报 DuplicateObject。

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE execution_status_enum AS ENUM "
        "('RUNNING', 'COMPLETED', 'BLOCKED', 'FAILED', 'CANCELLED')"
    )
    op.create_table(
        "calculation_job",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("execution_id", sa.String(64), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.Text, nullable=False, unique=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(64), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED",
                name="execution_status_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        schema="governance",
    )
    op.create_index(
        "ix_calculation_job_status", "calculation_job", ["status"], schema="governance"
    )


def downgrade() -> None:
    op.drop_index("ix_calculation_job_status", "calculation_job", schema="governance")
    op.drop_table("calculation_job", schema="governance")
    op.execute("DROP TYPE IF EXISTS execution_status_enum")
