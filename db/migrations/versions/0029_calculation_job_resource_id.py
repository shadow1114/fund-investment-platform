"""Keep API operation resource identity separate from decision lineage."""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calculation_job",
        sa.Column("resource_id", sa.String(128), nullable=True),
        schema="governance",
    )


def downgrade() -> None:
    op.drop_column("calculation_job", "resource_id", schema="governance")
