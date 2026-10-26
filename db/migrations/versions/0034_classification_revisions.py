"""Immutable five-dimensional classification revisions. Legacy rows remain untouched.

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE fund.fund_classification_revision (\n\tid BIGSERIAL NOT NULL, \n\tfund_id BIGINT NOT NULL, \n\tscheme VARCHAR(32) NOT NULL, \n\tversion INTEGER NOT NULL, \n\trule_version VARCHAR(32) NOT NULL, \n\tenum_version VARCHAR(32) NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tclassified_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\treason VARCHAR(1024) NOT NULL, \n\tactor VARCHAR(64) NOT NULL, \n\treviewed BOOLEAN NOT NULL, \n\tavailable_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tavailability_quality availability_quality_enum NOT NULL, \n\tpublished_at TIMESTAMP WITH TIME ZONE, \n\tprovider_available_at TIMESTAMP WITH TIME ZONE, \n\tingested_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_fcr_version UNIQUE (fund_id, scheme, version), \n\tCONSTRAINT ck_fcr_positive_version CHECK (version > 0), \n\tCONSTRAINT ck_fund_classification_revision_quality_source CHECK ((availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR (availability_quality = 'DERIVED' AND provider_available_at IS NULL  AND published_at IS NOT NULL) OR (availability_quality = 'INFERRED' AND provider_available_at IS NULL  AND published_at IS NULL)), \n\tCONSTRAINT ck_fund_classification_revision_time_order CHECK ((provider_available_at IS NULL OR published_at IS NULL  OR provider_available_at >= published_at) AND (ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND (available_at >= COALESCE(provider_available_at, published_at))), \n\tFOREIGN KEY(fund_id) REFERENCES fund.fund (id)\n)"
    )
    op.execute(
        "CREATE INDEX ix_fcr_pit ON fund.fund_classification_revision (fund_id, scheme, available_at, version)"
    )
    op.execute(
        "CREATE TABLE fund.fund_classification_review_case (\n\tid BIGSERIAL NOT NULL, \n\tfund_id BIGINT NOT NULL, \n\trevision_id BIGINT NOT NULL, \n\tissue_key VARCHAR(128) NOT NULL, \n\tissue_type VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tdetails JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tresolved_at TIMESTAMP WITH TIME ZONE, \n\tresult_revision_id BIGINT, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_fcrc_issue UNIQUE (fund_id, revision_id, issue_key), \n\tCONSTRAINT ck_fcrc_status CHECK (status IN ('PENDING', 'RESOLVED', 'SUPERSEDED')), \n\tFOREIGN KEY(fund_id) REFERENCES fund.fund (id), \n\tFOREIGN KEY(revision_id) REFERENCES fund.fund_classification_revision (id), \n\tFOREIGN KEY(result_revision_id) REFERENCES fund.fund_classification_revision (id)\n)"
    )
    op.execute(
        "ALTER TABLE fund.fund_classification_history ADD COLUMN revision_id BIGINT REFERENCES fund.fund_classification_revision(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE fund.fund_classification_history ADD COLUMN classification_result JSONB"
    )
    op.execute("ALTER TABLE fund.fund_classification_history ADD COLUMN trading_eligibility JSONB")
    op.execute("DROP INDEX fund.uq_fch_open_interval")
    op.execute(
        "CREATE UNIQUE INDEX uq_fch_open_interval ON fund.fund_classification_history (fund_id, classification_scheme) WHERE valid_to IS NULL AND revision_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_fch_revision_open ON fund.fund_classification_history (revision_id) WHERE valid_to IS NULL AND revision_id IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE fund.fund_classification_history ADD CONSTRAINT ex_fch_revision_intervals EXCLUDE USING gist (revision_id WITH =, daterange(valid_from, valid_to, '[)') WITH &&)"
    )
    op.execute(
        "ALTER TABLE fund.fund_classification_history ADD CONSTRAINT ck_fch_revision_result CHECK (revision_id IS NULL OR classification_result IS NOT NULL)"
    )


def downgrade() -> None:
    # Only an empty new schema may be removed. Never discard revisions/reviews in production.
    connection = op.get_bind()
    for table in ("fund_classification_revision", "fund_classification_review_case"):
        if connection.scalar(sa.text(f"SELECT count(*) FROM fund.{table}")):
            raise RuntimeError(
                "Classification history contains audit records; restore a verified backup"
            )
    op.drop_constraint("ex_fch_revision_intervals", "fund_classification_history", schema="fund")
    op.drop_constraint("ck_fch_revision_result", "fund_classification_history", schema="fund")
    op.drop_index("uq_fch_revision_open", table_name="fund_classification_history", schema="fund")
    op.drop_index("uq_fch_open_interval", table_name="fund_classification_history", schema="fund")
    op.drop_column("fund_classification_history", "trading_eligibility", schema="fund")
    op.drop_column("fund_classification_history", "classification_result", schema="fund")
    op.drop_column("fund_classification_history", "revision_id", schema="fund")
    op.create_index(
        "uq_fch_open_interval",
        "fund_classification_history",
        ["fund_id", "classification_scheme"],
        unique=True,
        schema="fund",
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.drop_table("fund_classification_review_case", schema="fund")
    op.drop_table("fund_classification_revision", schema="fund")
