"""H-2：强制「凡继承 IntervalMixin 的表必须用 interval 生成器，反之亦然」。

platform/db/mixins.py 有两个时序约束生成器 —— temporal_check_constraints
（版本化事实表，五子句）与 interval_temporal_check_constraints（区间型状态表，
三子句）。选哪个此前【完全靠作者手工】，当前 11 张表全部选对。

失败场景（Plan-1 交接项 H-2）：Plan-2 新增区间表时复制粘贴抓了版本化的那个，
于是所有【提前公告】的行（公告 8-25、生效 9-01）在写入时被 clause 1 / clause 4
直接拒收 —— 而那正是 Plan-1 花了一整轮（迁移 0014）修掉的问题。

黄金快照抓不到它：新表本来就应该新增约束，快照给出的是一条完全正常的信号。
"""

import pytest
from sqlalchemy import CheckConstraint

from fip.platform.db.base import Base
from fip.platform.db.mixins import (
    INTERVAL_TIME_ORDER_SQL,
    TIME_ORDER_SQL,
    IntervalMixin,
    VersionedMixin,
)

# Base.metadata 的注册点与 db/migrations/env.py 保持一致：只有被 import 过的
# 模块才会出现在 registry 里。少 import 一个模块会让本测试对那张表【失明】，
# 因此这份清单必须与 env.py 的清单同步（后者由 test_architecture.py::
# test_every_orm_model_module_is_registered_in_env 守住）。
from fip.platform.jobs import models as _jobs_models  # noqa: F401
from fip.services.data_service.models import fund as _fund  # noqa: F401
from fip.services.data_service.models import governance as _governance  # noqa: F401
from fip.services.data_service.models import market as _market  # noqa: F401
from fip.services.data_service.models import raw as _raw  # noqa: F401


def _time_order_sql(cls) -> str | None:
    """返回该 model 的 ck_<表名>_time_order 约束的 SQL 文本；没有则 None。"""
    wanted = f"ck_{cls.__tablename__}_time_order"
    for constraint in cls.__table__.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == wanted:
            return str(constraint.sqltext)
    return None


def _mapped_classes() -> list[type]:
    return [mapper.class_ for mapper in Base.registry.mappers]


def _interval_models() -> list[type]:
    return [c for c in _mapped_classes() if issubclass(c, IntervalMixin)]


def _versioned_models() -> list[type]:
    return [c for c in _mapped_classes() if issubclass(c, VersionedMixin)]


def test_the_two_mixins_are_disjoint():
    """守卫：若哪天有人让 VersionedMixin 继承 IntervalMixin，下面两条会互相矛盾。"""
    overlap = set(_interval_models()) & set(_versioned_models())
    assert not overlap, f"同时被判定为区间型与版本化的 model：{overlap}"


def test_the_scan_is_not_vacuous():
    """守卫：漏 import model 模块会让本文件的断言在空集合上恒真。

    当前实际数量：区间型 5 张（provider_fund_identity / fund_manager_assignment
    / fund_classification_history / fund_status_history / fund_fee），
    版本化 4 张（fund_nav / fund_distribution / risk_free_rate /
    investment_eligibility）。新增表只会让数量变大，不会变小。
    """
    assert len(_interval_models()) >= 5
    assert len(_versioned_models()) >= 4


@pytest.mark.parametrize(
    "model", _interval_models(), ids=lambda c: c.__tablename__
)
def test_interval_tables_use_the_interval_generator(model):
    """继承 IntervalMixin ⇒ 必须是三子句（clause 2 / 3 / 5）。

    用错生成器不会有任何静态错误，只会在写入【提前公告】的行时被数据库拒收。
    """
    actual = _time_order_sql(model)
    assert actual is not None, (
        f"{model.__tablename__} 继承 IntervalMixin 却没有 ck_*_time_order 约束"
    )
    assert actual == INTERVAL_TIME_ORDER_SQL, (
        f"{model.__tablename__} 是区间型状态表，必须用 "
        "interval_temporal_check_constraints（三子句）。当前用的是版本化表的"
        "五子句生成器，clause 1 / clause 4 会拒收所有提前公告的行"
    )


@pytest.mark.parametrize(
    "model", _versioned_models(), ids=lambda c: c.__tablename__
)
def test_versioned_tables_use_the_versioned_generator(model):
    """反之亦然：不继承 IntervalMixin 的事实表必须是五子句。

    反向也必须断言：只查一个方向的话，把版本化表误接成三子句生成器会静默
    删掉 clause 1 / clause 4 —— 那是版本化表上真正的前视偏差防线。
    """
    actual = _time_order_sql(model)
    assert actual is not None, (
        f"{model.__tablename__} 继承 VersionedMixin 却没有 ck_*_time_order 约束"
    )
    assert actual == TIME_ORDER_SQL, (
        f"{model.__tablename__} 是版本化事实表，必须用 temporal_check_constraints"
        "（五子句）。当前用的是区间型的三子句生成器，clause 1 / clause 4 缺失，"
        "净值可以声称比它自己的生效日更早就已知"
    )
