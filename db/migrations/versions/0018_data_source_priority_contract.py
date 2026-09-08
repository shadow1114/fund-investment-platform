"""Make each versioned disclosure-lag rule unambiguous.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_data_provider_dataset_code",
        "data_provider_dataset",
        ["provider_id", "dataset_code"],
        schema="governance",
    )
    op.create_unique_constraint(
        "uq_data_source_priority_rule",
        "data_source_priority",
        ["dataset_id", "field_name", "rule_version"],
        schema="governance",
    )
    # 冻结 Plan-2 v1 的可执行披露时滞。生产工厂仍然坚持“缺失即失败”；
    # 这里负责让新部署在迁移后具备完整规则，不依赖手工 SQL 或代码默认值。
    op.execute(sa.text("""
        INSERT INTO governance.data_provider (provider_code, display_name)
        VALUES ('AKSHARE', 'AKShare')
        ON CONFLICT (provider_code) DO NOTHING
    """))
    op.execute(sa.text("""
        INSERT INTO governance.data_provider_dataset
            (provider_id, dataset_code, adapter_version, library_version)
        SELECT p.id, seed.dataset_code, '1', '1.18.94'
        FROM governance.data_provider AS p
        CROSS JOIN (
            VALUES ('fund_nav'), ('fund_distribution'), ('fund_split')
        ) AS seed(dataset_code)
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
          AND d.dataset_code IN ('fund_nav', 'fund_distribution', 'fund_split')
        ON CONFLICT (dataset_id, field_name, rule_version) DO NOTHING
    """))


def downgrade() -> None:
    # 配置行和 provider/dataset 维度行可能已经被运行数据引用，或在升级前
    # 已由运维登记；降级只撤销结构约束，不猜测、更不删除这些持久化事实。
    op.drop_constraint(
        "uq_data_source_priority_rule",
        "data_source_priority",
        schema="governance",
        type_="unique",
    )
    op.drop_constraint(
        "uq_data_provider_dataset_code",
        "data_provider_dataset",
        schema="governance",
        type_="unique",
    )
