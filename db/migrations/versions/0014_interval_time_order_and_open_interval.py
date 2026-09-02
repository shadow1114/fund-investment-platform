"""区间表时序约束放宽、anchor 转换钉定 UTC、provider 标识补开放区间唯一索引

Task 19 fix round 2，item 1 / item 2（Critical）/ item 3（Critical）。

1）区间型状态表（anchor 语义是「区间起点」而非「事实成立日」）去掉
   clause 1（published_at >= valid_from）与 clause 4（available_at >=
   valid_from）。费率调整、申赎状态变更、基金分类转型、Provider 标识重指派
   在现实中几乎总是【提前公告】：公告日 8-25、生效日 9-01。原约束把这类
   合法且常见的事实直接拒收，把「知悉时点」和「生效时点」混为一谈。
   防前视偏差的不变式是 available_at 与 published_at /
   provider_available_at / ingested_at 之间的关系（clause 2、clause 3 与
   quality_source），它们与 valid_from 无关，原样保留。
   六张区间表当前【全部为空】（升级前已逐表确认 0 行），放宽约束不需要
   校验既有行，也没有任何行会因此变得不合规。

2）仍保留 anchor 比较的表（版本化事实表）把 DATE→TIMESTAMPTZ 的转换显式
   钉在 UTC：`effective_at::timestamp AT TIME ZONE 'UTC'`。裸比较走的是
   STABLE 的隐式转换，结果依赖会话 TimeZone —— 同一行在不同机器上可以一次
   合法一次非法，pg_restore / VALIDATE CONSTRAINT 因此可能拒绝已存在的行。
   钉定后约束与会话时区无关。本迁移不改任何写入代码。

3）fund.provider_fund_identity 补部分唯一索引 uq_pfi_open_interval：
   现唯一键 (provider_id, provider_fund_id, valid_from) 允许两条
   valid_to IS NULL 但 valid_from 不同的行共存，此时 cli._resolve 的
   `ORDER BY valid_from DESC LIMIT 1` 会静默挑一条。应用层的
   read-then-write 守卫不是数据库不变式。

本迁移只动约束与索引，不动任何列、不动任何数据（C-12：不回填、不伪造
任何时间戳）。

Revision ID: 0014
Revises: 0013
"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

# 区间型状态表：本轮改为两子句（clause 2 + clause 3）。
# governance.interval_probe 是 0004 建的纯 SQL 约束探针表（没有 ORM model，
# 见 db/migrations/env.py 的 include_object 排除清单），它与业务区间表用的是
# 同一套生成器，必须同步改，否则探针会继续验证一套已经不存在的语义。
_INTERVAL_TABLES: tuple[tuple[str, str], ...] = (
    ("governance", "interval_probe"),
    ("fund", "provider_fund_identity"),
    ("fund", "fund_manager_assignment"),
    ("fund", "fund_classification_history"),
    ("fund", "fund_status_history"),
    ("fund", "fund_fee"),
)

# 版本化事实表：四子句保持不变，只把 anchor 的转换钉到 UTC。
# market.fund_nav 是声明式分区表，约束加在父表上会递归到 31 张分区子表，
# DROP 同理 —— 因此这里【只】操作父表，不逐个 ALTER 子表。
_VERSIONED_TABLES: tuple[tuple[str, str], ...] = (
    ("governance", "mixin_probe"),
    ("market", "fund_nav"),
    ("market", "fund_distribution"),
    ("market", "risk_free_rate"),
    ("fund", "investment_eligibility"),
)

# --- 本迁移【产出】的定义（0014 时点的字面量，逐字固化，不得从 mixins 取）---
# fix round 3 item 2：本迁移原先从 fip.platform.db.mixins 直接 import 两个
# 时序常量 —— 正是它自己为 0002–0013 消除掉的那个模式。mixins 是活代码：
# 0015 给两类表都补了第五条子句（available_at >= COALESCE(
# provider_available_at, published_at)），若本迁移仍从 mixins 取值，它的
# upgrade() 会被【追溯性改写】成产出五子句，而 downgrade() 是固化字面量、
# 仍还原成四子句 —— 往返立刻不对称，从空库 upgrade 到 0014 也会得到一个
# 0014 当时根本不存在的形态。
# 下面两个常量是 0014 【当时】实际产出的字面量，含 mixins 的换行拼接在
# " OR provider_available_at" 前留下的那个多余空格，逐字保留。
_NEW_VERSIONED_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= "
    "(effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= (effective_at::timestamp AT TIME ZONE 'UTC'))"
)
_NEW_INTERVAL_TIME_ORDER_SQL = (
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at))"
)

# --- downgrade 用的旧定义（0013 时点的字面量，逐字固化，不得再从 mixins 取）---
_OLD_VERSIONED_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= effective_at) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= effective_at)"
)
_OLD_INTERVAL_TIME_ORDER_SQL = _OLD_VERSIONED_TIME_ORDER_SQL.replace(
    "effective_at", "valid_from"
)


def _replace_time_order(schema: str, table: str, sql: str) -> None:
    """原地替换 ck_<table>_time_order。

    先 DROP 再 ADD 而不是 ALTER：PostgreSQL 没有「修改 CHECK 表达式」的 DDL。
    两步在同一个事务里（Alembic 的事务性 DDL），不存在约束短暂缺失的窗口。
    """
    op.execute(f"ALTER TABLE {schema}.{table} DROP CONSTRAINT ck_{table}_time_order")
    op.execute(
        f"ALTER TABLE {schema}.{table} "
        f"ADD CONSTRAINT ck_{table}_time_order CHECK ({sql})"
    )


def upgrade() -> None:
    for schema, table in _INTERVAL_TABLES:
        _replace_time_order(schema, table, _NEW_INTERVAL_TIME_ORDER_SQL)
    for schema, table in _VERSIONED_TABLES:
        _replace_time_order(schema, table, _NEW_VERSIONED_TIME_ORDER_SQL)

    op.execute(
        "CREATE UNIQUE INDEX uq_pfi_open_interval "
        "ON fund.provider_fund_identity (provider_id, provider_fund_id) "
        "WHERE valid_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX fund.uq_pfi_open_interval")

    for schema, table in _VERSIONED_TABLES:
        _replace_time_order(schema, table, _OLD_VERSIONED_TIME_ORDER_SQL)
    for schema, table in _INTERVAL_TABLES:
        _replace_time_order(schema, table, _OLD_INTERVAL_TIME_ORDER_SQL)
