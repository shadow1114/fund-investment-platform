"""Register the AKShare risk-free yield curve dataset and its disclosure lag.

Revision ID: 0041
Revises: 0040
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 与 0018 同一口径：中债曲线在 T 日收盘后发布，按 1 天披露时滞推导 available_at。
    op.execute(sa.text("""
        INSERT INTO governance.data_provider (provider_code, display_name)
        VALUES ('AKSHARE', 'AKShare')
        ON CONFLICT (provider_code) DO NOTHING
    """))
    op.execute(sa.text("""
        INSERT INTO governance.data_provider_dataset
            (provider_id, dataset_code, adapter_version, library_version)
        SELECT p.id, 'risk_free_rate', '1', '1.18.94'
        FROM governance.data_provider AS p
        WHERE p.provider_code = 'AKSHARE'
        ON CONFLICT (provider_id, dataset_code) DO NOTHING
    """))
    op.execute(sa.text("""
        INSERT INTO governance.data_source_priority
            (dataset_id, field_name, priority, disclosure_lag_days, rule_version)
        SELECT d.id, 'available_at', 1, 1, 'v1'
        FROM governance.data_provider_dataset AS d
        JOIN governance.data_provider AS p ON p.id = d.provider_id
        WHERE p.provider_code = 'AKSHARE'
          AND d.dataset_code = 'risk_free_rate'
        ON CONFLICT (dataset_id, field_name, rule_version) DO NOTHING
    """))


def downgrade() -> None:
    # 与 0018 一致：规则行可能已被运行数据引用，降级不删除持久化事实。
    pass
