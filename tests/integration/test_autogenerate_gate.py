"""G-16 的自动化闸门：Base.metadata 与真实数据库之间不得有差异。

与黄金快照（test_temporal_constraints.py 的 CHECK 快照）互补，两者都需要：

  黄金快照  管 CHECK 表达式 —— autogenerate 对 CHECK 完全失明
            （实测把 fund_nav 的时序 CHECK 换成 1=1，autogenerate 照报零操作）
  本测试    管表 / 列 / 索引 / 唯一键 —— 快照的 SQL 只查 contype='c'，看不见索引

单靠任何一个都留着一半的门开着。
"""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ExcludeConstraint

# db/migrations/env.py 与本测试共用同一份 include_object。它住在
# fip.platform.db.autogenerate 而不是 env.py 里，是因为 env.py 是 Alembic 的
# 入口脚本、模块级就调用 context.config，在 Alembic 之外 import 会直接抛
# AttributeError —— 唯一的替代方案是在这里复制一份规则，而两份规则一旦漂移，
# 本闸门就会对分区子表/探针表报假差异，接着被人加 xfail 关掉，比没有测试更糟。
from fip.platform.db.autogenerate import include_object
from fip.platform.db.base import Base

# Base.metadata 的注册点必须与 env.py 一致：没被 import 的 model 模块不会
# 出现在 metadata 里，本测试会对那张表【失明】（库里有、metadata 里没有，
# 但 compare_metadata 只在双方都被看见时才比对得出差异）。这份清单由
# tests/fitness/test_architecture.py::test_every_orm_model_module_is_registered_in_env
# 守住与 env.py 同步。
from fip.platform.jobs import models as _jobs_models  # noqa: F401
from fip.services.data_service.models import fund as _fund  # noqa: F401
from fip.services.data_service.models import benchmark as _benchmark  # noqa: F401
from fip.services.data_service.models import governance as _governance  # noqa: F401
from fip.services.data_service.models import market as _market  # noqa: F401
from fip.services.data_service.models import raw as _raw  # noqa: F401
from fip.services.fund_service import models as _fund_service_models  # noqa: F401

pytestmark = pytest.mark.integration


def test_the_metadata_under_test_is_not_empty():
    """守卫：Base.metadata 为空时 compare_metadata 会返回空 diff 而恒绿。

    本仓库抓到过 `_py_files` 对不存在目录返回 [] 导致 `assert not []` 恒真
    的案例；这条闸门的断言形状是 `assert not diff`，同一个陷阱，先证明
    被比较的一侧确实装着东西。
    """
    assert len(Base.metadata.tables) >= 15


def test_orm_metadata_matches_the_migrated_database(db_session):
    """等价于手工跑 `alembic revision --autogenerate` 并检查它报告零操作。

    db_session 的库由 conftest 跑真实 `alembic upgrade head` 建起，所以
    比较的是【迁移的产出】与【ORM 声明】，而不是 ORM 与它自己。

    include_object 必须与 db/migrations/env.py 用同一份 —— 否则本测试会
    对 alembic 版本表、探针表之类报差异，然后被人加 xfail 关掉，
    比没有测试更糟。
    """
    ctx = MigrationContext.configure(
        db_session.connection(),
        opts={
            "compare_type": True,
            "include_object": include_object,
            "include_schemas": True,
        },
    )
    diff = compare_metadata(ctx, Base.metadata)
    assert not diff, (
        "ORM metadata 与迁移建出的数据库不一致 —— `alembic revision "
        f"--autogenerate` 会生成非空迁移：{diff}\n"
        "常见原因：迁移里 CREATE 了索引/约束但 ORM __table_args__ 没声明"
        "（下一次 autogenerate 会把它误判成待删除对象），或反过来。"
    )


# --------------------------------------------------------------------------
# EXCLUDE 约束：compare_metadata 对它【也】失明（实测）
# --------------------------------------------------------------------------
# 上面那条闸门抓得住表 / 列 / 索引 / 唯一键，但实测把
# FundManagerAssignment 的 ExcludeConstraint 从 ORM 里整段删掉之后，
# compare_metadata 仍然返回空 diff —— Alembic 不比较 EXCLUDE 约束。
# 于是 ex_fma_no_overlap 落在三道防线之间的缝里：
#   · CHECK 黄金快照只查 contype='c'（EXCLUDE 是 'x'）；
#   · autogenerate 闸门看不见它；
#   · 迁移 0016 的行为测试只证明【数据库里】有约束，不证明 ORM 声明了它。
# 而「库里有、ORM 里没有」正是本仓库咬出过三次误删迁移的那个形状，
# 只不过换成了 autogenerate 沉默的版本。下面这条把缺口补上。

_DB_EXCLUDE_CONSTRAINTS = text("""
    SELECT n.nspname, t.relname, c.conname
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE c.contype = 'x'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
""")


def _metadata_exclude_constraints() -> set[tuple[str, str, str]]:
    return {
        (table.schema or "public", table.name, constraint.name)
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, ExcludeConstraint) and constraint.name
    }


def test_exclude_constraints_are_declared_on_both_sides(db_session):
    """库里的 EXCLUDE 与 ORM 声明的 EXCLUDE 必须一一对应（G-16）。

    什么情况下它会红：迁移建了一条 EXCLUDE 而 ORM 没声明（或反过来）。
    证伪记录见任务报告 —— 把 ex_fma_no_overlap 从 ORM 删掉后本条转红，
    而上面那条 compare_metadata 闸门对同一次删除保持沉默。
    """
    in_db = {tuple(row) for row in db_session.execute(_DB_EXCLUDE_CONSTRAINTS).all()}
    in_orm = _metadata_exclude_constraints()
    assert in_db, "库里一条 EXCLUDE 都没有 —— 本断言会在空集合上恒真，先查迁移"
    assert in_db == in_orm, (
        f"EXCLUDE 约束两侧不一致。只在库里：{sorted(in_db - in_orm)}；"
        f"只在 ORM 里：{sorted(in_orm - in_db)}"
    )
