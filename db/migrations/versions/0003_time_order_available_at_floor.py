"""time_order 约束补第 4 子句：available_at >= effective_at

修复：Task 3 fix round 1 —— 原三子句约束存在两处真空满足（vacuous
satisfaction）漏洞：

1. EXACT，published_at 为 NULL 时，clause 2 真空满足，provider_available_at
   （EXACT 分支下 available_at 的来源）可以早于 effective_at 而不被拦下。
2. INFERRED，两个来源均为 NULL 时，clause 3 退化为 ingested_at 与自身比较
   （COALESCE(NULL, NULL, ingested_at) = ingested_at），恒真，ingested_at
   （INFERRED 分支下 available_at 的来源）可以早于 effective_at 而不被拦下。

两者本质都是同一个不变式的缺失：available_at 不能早于 effective_at ——
不能在事实生效前就“看到”它。新增 clause 4 直接对 available_at 本身设限，
一次性堵住两个来源分支上的漏洞。

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# 【已冻结的字面量】迁移是不可编辑的历史，它产出的 DDL 必须与当初执行时
# 逐字相同。此前这里 import 的是 mixins.py 里的共享常量/生成器，于是
# fix round 2 修改 mixins 时，这支【旧】迁移在一次全新的 upgrade 里会产出
# 【新】定义 —— 迁移历史被追溯性地改写，downgrade 也再无法还原当初的形状。
# 因此把当时的 SQL 原样固化在这里；今后的语义变更一律由新迁移承担。

_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= effective_at) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= effective_at)"
)

# 旧的三子句定义，供 downgrade() 还原。
_OLD_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= effective_at) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at))"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_mixin_probe_time_order", "mixin_probe", schema="governance", type_="check"
    )
    op.create_check_constraint(
        "ck_mixin_probe_time_order",
        "mixin_probe",
        _TIME_ORDER_SQL,
        schema="governance",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_mixin_probe_time_order", "mixin_probe", schema="governance", type_="check"
    )
    op.create_check_constraint(
        "ck_mixin_probe_time_order",
        "mixin_probe",
        _OLD_TIME_ORDER_SQL,
        schema="governance",
    )
