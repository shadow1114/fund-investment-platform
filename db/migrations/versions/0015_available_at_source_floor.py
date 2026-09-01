"""时序约束补 clause 5：available_at 不得早于它自己声明的来源

Task 19 fix round 3，item 1（Critical）。

── 洞在哪里 ──

fix round 2（迁移 0014）为区间型状态表去掉了 clause 1 与 clause 4，理由
（提前公告是合法的）成立；但 0014 的说明里还写了一句错话：「防前视偏差的
不变式是 available_at 与 published_at / provider_available_at /
ingested_at 之间的关系（clause 2、clause 3 与 quality_source）」。
**这句话是错的。** clause 2 是 `provider_available_at >= published_at`，
clause 3 是 `ingested_at >= COALESCE(...)` —— 两条都【没有提到
available_at】。于是删掉 clause 4 之后，区间表上的 available_at 不再被
任何 CHECK 触及，已在 governance.interval_probe 上实测：

    available_at = 1900-01-01，published_at = 2026-01-02（EXACT，
    provider_available_at = 2026-01-03）

这样一条「声称我们在公告前 126 年就知道了」的纯前视偏差被原样收下。

同一个洞在【版本化事实表】上更老、一直都在：clause 4 只把 available_at
钉在 effective_at 之后，从未把它与三个来源关联过。effective_at=01-02、
published_at=01-02T18:00、available_at=01-02T10:00 满足原有全部四条
clause，却声称我们比公告早 8 小时就知道了。

── 补的是哪一条 ──

    clause 5   available_at >= COALESCE(provider_available_at, published_at)

与 anchor 无关，因此【两类表都加】：

  · EXACT    ：available_at == provider_available_at，取等号通过；
  · DERIVED  ：provider_available_at 为 NULL，COALESCE 落到 published_at，
               available_at == published_at，取等号通过；
  · INFERRED ：两者皆 NULL，COALESCE 为 NULL，比较结果为 NULL →
               CHECK 真空满足。这正是 declared_lag_availability（净值灌数
               唯一走的路径）所在，一行都不会被拒。

也就是说 clause 5 拒不掉任何合法行，只挡住「声称比来源更早知道」。

刻意【不】加对称的 `available_at <= ingested_at`：INFERRED 路径下
available_at = effective_at + 声明时滞 可以晚于 ingested_at（当天灌当天的
数据就会触发），那会拒掉合法行。

── 覆盖面 ──

11 张表：6 张区间型（含 governance.interval_probe 探针）+ 5 张版本化
（含 governance.mixin_probe 探针）。market.fund_nav 是声明式分区表，
约束加在父表上会递归到 31 张分区子表，DROP 同理 —— 照 0014 的既有做法
【只】操作父表。

本迁移只动约束，不动任何列、不动任何数据（C-12：不回填、不伪造任何
时间戳）。升级前已确认 11 张表的既有行全部满足 clause 5：fip_dev 的
5997 行净值全部是 INFERRED（两个来源皆 NULL），走真空满足那条路径。

Revision ID: 0015
Revises: 0014
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# 区间型状态表：本轮由两子句（clause 2 + 3）改为三子句（+ clause 5）。
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

# 版本化事实表：本轮由四子句改为五子句（+ clause 5）。
_VERSIONED_TABLES: tuple[tuple[str, str], ...] = (
    ("governance", "mixin_probe"),
    ("market", "fund_nav"),
    ("market", "fund_distribution"),
    ("market", "risk_free_rate"),
    ("fund", "investment_eligibility"),
)

# --- 本迁移【产出】的定义（0015 时点的字面量，逐字固化，不得从 mixins 取）---
# 迁移是历史记录，mixins 是活代码：一旦从 mixins import，下一轮改 mixins 会
# 【追溯性改写】本迁移的 upgrade()，而 downgrade() 的固化字面量不会跟着变，
# 往返立刻不对称（0014 就踩过，见该文件顶部的 fix round 3 item 2 说明）。
# 空格与括号与 mixins 的拼接结果逐字一致（含
# " OR provider_available_at" 前那个来自换行拼接的多余空格）。
_NEW_VERSIONED_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= "
    "(effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= (effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(available_at >= COALESCE(provider_available_at, published_at))"
)
_NEW_INTERVAL_TIME_ORDER_SQL = (
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= COALESCE(provider_available_at, published_at))"
)

# --- downgrade 用的旧定义（0014 时点的字面量，逐字固化）---
# 与 0014 的 _NEW_* 两个常量逐字相同 —— 但【刻意复制而非 import】：迁移之间
# 互相 import 会让上游迁移变成下游迁移的活依赖，重演同一个追溯性改写问题。
_OLD_VERSIONED_TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= "
    "(effective_at::timestamp AT TIME ZONE 'UTC')) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at)) AND "
    "(available_at >= (effective_at::timestamp AT TIME ZONE 'UTC'))"
)
_OLD_INTERVAL_TIME_ORDER_SQL = (
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at))"
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


def downgrade() -> None:
    for schema, table in _VERSIONED_TABLES:
        _replace_time_order(schema, table, _OLD_VERSIONED_TIME_ORDER_SQL)
    for schema, table in _INTERVAL_TABLES:
        _replace_time_order(schema, table, _OLD_INTERVAL_TIME_ORDER_SQL)
