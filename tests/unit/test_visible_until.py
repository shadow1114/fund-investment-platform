"""`decision_at → visible_until` 的唯一翻译规则（Plan-1 交接项 H-1）。

这条规则是全平台唯一可见性规则 `available_at <= decision_at` 的落地形式。
Plan-1 结束时它以逐字拷贝的形式住在 repositories/nav.py 与
normalization/backfill.py 两处，没有共同归属、没有任何测试断言两者相等 ——
第三份拷贝写成 dt.time.min 时，回测与实盘会对同一个 decision_at 解析出不同
的可见集合，不报错、不告警。
"""

import ast
import datetime as dt
import pathlib

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import (
    PitDataContext,
    resolve_visible_until,
    visible_until_for,
)

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
RULE_HOME = SRC / "platform" / "decision_data" / "pit.py"


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-VU",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def test_rule_resolves_to_utc_end_of_decision_day():
    """decision_at 是业务日期，可见性判定取该日【终了】时刻，钉在 UTC。"""
    assert resolve_visible_until(dt.date(2026, 8, 31)) == dt.datetime(
        2026, 8, 31, 23, 59, 59, 999999, tzinfo=dt.UTC
    )


def test_plan2_public_name_resolves_to_utc_end_of_decision_day():
    assert visible_until_for(dt.date(2026, 9, 8)) == dt.datetime.combine(
        dt.date(2026, 9, 8), dt.time.max, tzinfo=dt.UTC
    )


def test_rule_is_end_of_day_not_start_of_day():
    """反向断言：写成 dt.time.min 会让整整一天的披露对当日决策不可见。

    这条测试存在的理由就是 H-1 描述的失败场景本身 —— 第三份拷贝写成
    time.min 不会报错，只会让两条路径解析出不同的可见集合。
    """
    day_start = dt.datetime(2026, 8, 31, tzinfo=dt.UTC)
    assert resolve_visible_until(dt.date(2026, 8, 31)) != day_start


def test_context_property_delegates_to_the_same_rule():
    """PitDataContext 是 decision_at 的唯一构造入口，属性必须与规则一致。"""
    ctx = PitDataContext(context=_ctx(dt.date(2026, 8, 31)), session=object())
    assert ctx.visible_until == resolve_visible_until(dt.date(2026, 8, 31))


@pytest.mark.parametrize(
    "decision_at",
    [dt.date(1999, 12, 31), dt.date(2020, 2, 29), dt.date(2026, 8, 31)],
)
def test_property_and_function_agree_on_every_date(decision_at):
    ctx = PitDataContext(context=_ctx(decision_at), session=object())
    assert ctx.visible_until == resolve_visible_until(decision_at)


def _files_mentioning_time_max() -> set[pathlib.Path]:
    """AST 扫描 src/fip 下全部 .py，找出出现 `<something>.time.max` 的文件。

    用 AST 而非正则：正则会把注释和 docstring 里的说明文字也算进来，
    而这条检查必须能被注释准确描述而不被自己绊倒。
    """
    hits: set[pathlib.Path] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "max"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "time"
            ):
                hits.add(path)
    return hits


def test_the_scan_actually_sees_source_files():
    """守卫：SRC 路径写错时 rglob 返回空，上面那条断言会在空集合上恒真。

    本仓库抓到过 `_py_files` 对不存在目录返回 [] 导致 `assert not []` 恒真
    的案例，因此这条扫描必须先证明它确实看见了源码树。
    """
    assert SRC.is_dir()
    assert len(list(SRC.rglob("*.py"))) > 20
    assert RULE_HOME.is_file()


def test_the_rule_has_exactly_one_home_in_the_whole_source_tree():
    """`dt.time.max` 只允许出现在规则本身所在的那一个文件里。

    什么情况下它会红：任何人在第二个文件里再写一次
    `dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)`。
    这正是 Plan-1 结束时的状态（nav.py 与 backfill.py 各一份），所以本测试
    在修复前【必定】失败 —— 它不是恒真的 oracle。
    """
    assert _files_mentioning_time_max() == {RULE_HOME}
