"""autogenerate 的对象过滤清单 —— db/migrations/env.py 与 G-16 闸门的唯一权威。

为什么单独成一个模块（P2-10）：这份 include_object 原先住在
db/migrations/env.py 里。env.py 是 Alembic 的入口脚本，模块级就调用
`context.config`，在 Alembic 之外 import 它会直接抛
`AttributeError: module 'alembic.context' has no attribute 'config'`。
于是 tests/integration/test_autogenerate_gate.py 若想用「与 env.py 同一份」
过滤规则，就只剩下复制一份这一条路 —— 而两份规则一旦漂移，闸门就会开始
对分区子表/探针表报假差异，接着被人加 xfail 关掉，比没有测试更糟。
把规则搬到这里，env.py 与闸门测试各 import 一次，永远是同一份。
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# autogenerate 需要一份显式、最小化的排除清单，而不是一条宽松的「忽略未建模
# 对象」规则 —— 宽松规则会连真实的 schema drift 也一并吞掉，这正是本清单
# 要防止的失效模式。清单里的每一项都必须能单独解释「为什么被排除」。
#
# 1) market.fund_nav_<年份> 分区子表：PostgreSQL 声明式分区下，
#    `CREATE TABLE ... PARTITION OF` 产生的物理子表是父表 DDL 的派生物，
#    SQLAlchemy 没有对应的 ORM 概念可以声明它们（parent table 本身已经
#    通过 FundNav 声明，子表继承其列与约束）。不排除的话，autogenerate
#    会把 31 张分区子表全部当成「Base.metadata 里没有、数据库里多出来」
#    的表，提议逐一 DROP —— 一旦真的被误执行，丢的是全部历史净值。
#    用命名模式而非表名枚举来匹配，因为分区范围会随 FIRST_YEAR/LAST_YEAR
#    调整（见 0008 迁移），排除规则不应该每次跟着改。
# 2) governance.mixin_probe / governance.interval_probe：0002 / 0004 迁移
#    引入的纯 SQL 约束测试夹具，按设计没有 ORM model（校验的是 mixin 生成的
#    CHECK 约束本身，不是业务表）。它们的存在性由 tests/fitness 里对应的
#    18 个约束测试覆盖，不依赖 autogenerate 能看见它们 —— 所以就算被真的
#    删除，autogenerate 保持沉默也不会丢失覆盖。这是本清单里唯一一类
#    「明知道 autogenerate 看不见其消失」的例外，写在这里防止将来有人
#    收紧排除规则（导致这两张表重新产生噪音）或不明就里地放宽排除规则
#    （导致这条注释失去意义、掩盖真实 drift）。
_PARTITION_CHILD_RE = re.compile(r"^fund_nav_\d{4}$")
_EXCLUDED_GOVERNANCE_TABLES = {"mixin_probe", "interval_probe"}


def include_object(
    object: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    if type_ == "table" and reflected and compare_to is None:
        if object.schema == "market" and _PARTITION_CHILD_RE.match(name or ""):
            return False
        if object.schema == "governance" and name in _EXCLUDED_GOVERNANCE_TABLES:
            return False
    return True
