"""fund 核心表

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(length=32), nullable=False),
        sa.Column("product_name", sa.String(length=256), nullable=False),
        sa.Column("grouping_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_code"),
        schema="fund",
    )
    op.create_table(
        "fund_share_class",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_id", sa.BigInteger(), nullable=False),
        sa.Column("share_class_code", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("inception_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fund_id"], ["fund.fund.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_id", "share_class_code", name="uq_share_class_business"),
        schema="fund",
    )
    op.create_table(
        "provider_fund_identity",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_fund_id", sa.String(length=64), nullable=False),
        sa.Column("share_class_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["governance.data_provider.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["share_class_id"], ["fund.fund_share_class.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id", "provider_fund_id", "valid_from", name="uq_provider_identity"
        ),
        schema="fund",
    )


def downgrade() -> None:
    op.drop_table("provider_fund_identity", schema="fund")
    op.drop_table("fund_share_class", schema="fund")
    op.drop_table("fund", schema="fund")
