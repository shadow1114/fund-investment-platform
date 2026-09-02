### Task 1: Plan-1 交接 H-1 + H-2 —— `visible_until` 归位 + IntervalMixin 生成器配对的适应度测试

**Files:**
- Modify: `src/fip/platform/decision_data/pit.py:1-64`（新增 `resolve_visible_until`、
  `PitDataContext.visible_until` 属性、改 `navs()` 的装配）
- Modify: `src/fip/services/data_service/repositories/nav.py:86-121`
  （构造期改收 `visible_until`，删掉第 113-116 行那份逐字拷贝）
- Modify: `src/fip/services/data_service/normalization/backfill.py:16-29,121`
  （第 121 行的第二份逐字拷贝改为调用唯一规则）
- Test: `tests/unit/test_visible_until.py`（新建）
- Test: `tests/fitness/test_temporal_mixin_pairing.py`（新建，H-2）

**Interfaces:**
- Consumes: 无（本任务是 Plan-2 的第一个任务）
- Produces:
  - `fip.platform.decision_data.pit.resolve_visible_until(decision_at: dt.date) -> dt.datetime`
    —— 全平台 `decision_at → available_at <= ?` 的**唯一**翻译规则实现
  - `PitDataContext.visible_until -> dt.datetime`（property，只读）
  - `SqlNavPitRepository.__init__(session: Session, visible_until: dt.datetime)`
    —— 构造签名从 `decision_at: dt.date` 改为 `visible_until: dt.datetime`；
    Task 2 在此基础上继续改 `adjusted_nav_series` 的返回类型
  - `fip.platform.db.mixins.INTERVAL_TIME_ORDER_SQL` / `TIME_ORDER_SQL` 成为
    「哪张表用哪个生成器」的机器可判定依据（Task 5 新增区间表写入时受其保护）

---

- [ ] **Step 1: 写失败的测试（H-1 —— 规则归位 + 全仓唯一）**

新建 `tests/unit/test_visible_until.py`：

```python
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
from fip.platform.decision_data.pit import PitDataContext, resolve_visible_until

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


def test_the_rule_has_exactly_one_home_in_the_whole_source_tree():
    """`dt.time.max` 只允许出现在规则本身所在的那一个文件里。

    什么情况下它会红：任何人在第二个文件里再写一次
    `dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)`。
    这正是 Plan-1 结束时的状态（nav.py 与 backfill.py 各一份），所以本测试
    在修复前【必定】失败 —— 它不是恒真的 oracle。
    """
    assert _files_mentioning_time_max() == {RULE_HOME}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_visible_until.py -v`

Expected: FAIL —— 收集阶段即 `ImportError: cannot import name 'resolve_visible_until'
from 'fip.platform.decision_data.pit'`。临时把该 import 注释掉再跑
`-k the_rule_has_exactly_one_home`，会看到
`AssertionError: assert {.../repositories/nav.py, .../normalization/backfill.py} == {.../pit.py}`
—— 两份逐字拷贝被如实点名。把失败输出原样写进报告（G-18）。

- [ ] **Step 3: 最小实现**

`src/fip/platform/decision_data/pit.py` —— 在 `NavPoint` 之前插入规则函数，
并给 `PitDataContext` 加属性、改 `navs()` 的装配：

```python
def resolve_visible_until(decision_at: dt.date) -> dt.datetime:
    """把 decision_at（业务日期）翻译成 `available_at <= ?` 的时间戳上界。

    这是全平台唯一可见性规则 `available_at <= decision_at`（G-1）的**唯一**
    落地形式，本函数是它在代码中的唯一归属。

    ── 为什么必须只有一份（Plan-1 交接项 H-1）──

    Plan-1 结束时同一行 `dt.datetime.combine(decision_at, dt.time.max,
    tzinfo=dt.UTC)` 逐字住在 repositories/nav.py 与 normalization/backfill.py
    两个不同的层，没有共同归属、没有任何测试断言两者相等。Plan-2 要为
    risk_free_rate / fund_classification_history 写第二、第三个 PIT 读取路径，
    第三份拷贝只要写成 `dt.time.min`，两条路径就会对同一个 decision_at 解析出
    不同的可见集合 —— 不报错、不告警，回测和实盘看到不同的数据。

    ── 取日终而不是日初 ──

    decision_at 是【业务日期】，available_at 是【时间戳】。「当日可见」意味着
    当日任意时刻的披露都算数，因此上界取该日终了时刻。取日初会让整整一天的
    披露对当日决策不可见（信息偏少的方向也是错的：它会让因子在披露日当天
    静默变成 UNAVAILABLE）。

    ── 已知边界（Plan-1 交接项二.4，如实登记，本任务不修）──

    日终钉在 UTC。若披露时刻按 UTC+8 记，本规则相当于允许 decision_at 当天
    看到最多 8 小时【之后】的披露。这是 Plan-1 的既有约定，不是现算改造引入的；
    真正的修法是给 available_at 引入交易日历与市场时区，属后续项。
    """
    return dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)
```

`PitDataContext` 内（紧跟 `decision_at` 属性之后）：

```python
    @property
    def visible_until(self) -> dt.datetime:
        """本次决策的可见性上界：`available_at <= visible_until`。

        PitDataContext 是 decision_at 的唯一构造入口，因此这条翻译规则的
        唯一对外出口就在这里。任何 PIT 读取实现都应当接收本属性的值，
        而不是自己再翻译一次 decision_at（H-1）。
        """
        return resolve_visible_until(self.decision_at)
```

`navs()` 的装配改为传上界而不是日期：

```python
        return SqlNavPitRepository(
            session=self._session, visible_until=self.visible_until
        )
```

`src/fip/services/data_service/repositories/nav.py` —— 构造期改收上界，
删掉方法体内那三行拷贝（原第 113-116 行）：

```python
    def __init__(self, session: Session, visible_until: dt.datetime) -> None:
        """visible_until 由 PitDataContext.visible_until 注入。

        本类【不再】自己把 decision_at 翻译成时间戳上界：那条规则的唯一
        归属是 fip.platform.decision_data.pit.resolve_visible_until（H-1）。
        构造期注入上界与注入 decision_at 在 PIT-A2 上是等价的 —— 时点仍然
        不出现在任何方法签名里，调用方仍然无法省略它、无法绕过它取未来数据。
        """
        self._session = session
        self._visible_until = visible_until
```

`adjusted_nav_series` 方法体开头的三行替换为一行：

```python
        params = {
            "share_class_id": share_class_id,
            "visible_until": self._visible_until,
            "date_to": date_to,
        }
```

`src/fip/services/data_service/normalization/backfill.py` —— 顶部加 import，
第 121 行改为调用唯一规则：

```python
from fip.platform.decision_data.pit import resolve_visible_until
```

```python
    visible_until = resolve_visible_until(decision_at)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_visible_until.py -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: `tests/unit/test_visible_until.py` 6 passed；既有 281 条不减。

- [ ] **Step 5: 写失败的测试（H-2 —— 两个生成器与两个 Mixin 必须配对）**

新建 `tests/fitness/test_temporal_mixin_pairing.py`：

```python
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
```

- [ ] **Step 6: 跑测试确认失败（H-2 必须【人为制造】红灯才算证伪）**

当前 11 张表全部选对，因此本测试一写出来就是绿的。绿灯不是证据 —— 按交接项
六.1「证伪是唯一的验收方式」，必须先制造一次真实的红灯：

Run:
```bash
.venv/bin/python - <<'PY'
import pathlib
p = pathlib.Path("src/fip/services/data_service/models/fund.py")
s = p.read_text(encoding="utf-8")
p.write_text(s.replace(
    '*interval_temporal_check_constraints("fund_fee")',
    '*temporal_check_constraints("fund_fee")', 1), encoding="utf-8")
PY
.venv/bin/python - <<'PY'
import pathlib
p = pathlib.Path("src/fip/services/data_service/models/fund.py")
s = p.read_text(encoding="utf-8")
assert "temporal_check_constraints,\n" in s or True
p.write_text(s.replace(
    "    IntervalMixin,\n",
    "    IntervalMixin,\n", 1), encoding="utf-8")
PY
grep -n "temporal_check_constraints" src/fip/services/data_service/models/fund.py | head -5
.venv/bin/pytest tests/fitness/test_temporal_mixin_pairing.py -v
```

Expected: FAIL with
`test_interval_tables_use_the_interval_generator[fund_fee] ... AssertionError:
fund_fee 是区间型状态表，必须用 interval_temporal_check_constraints（三子句）`
（若 `temporal_check_constraints` 尚未在该文件 import，先在 import 块里补上再制造，
制造完连同 import 一起还原）。把这段红灯输出写进报告，然后还原：

Run: `git checkout -- src/fip/services/data_service/models/fund.py`
Run: `.venv/bin/pytest tests/fitness/test_temporal_mixin_pairing.py -v`
Expected: 11 passed（9 张表 + 2 条守卫）。

- [ ] **Step 7: 提交**

```bash
git add tests/unit/test_visible_until.py tests/fitness/test_temporal_mixin_pairing.py
git commit --only \
  src/fip/platform/decision_data/pit.py \
  src/fip/services/data_service/repositories/nav.py \
  src/fip/services/data_service/normalization/backfill.py \
  tests/unit/test_visible_until.py \
  tests/fitness/test_temporal_mixin_pairing.py \
  -m "fix(pit): H-1/H-2 —— visible_until 归位到唯一规则，并强制 Mixin 与约束生成器配对

H-1：decision_at → available_at 上界的翻译规则此前逐字拷贝在
repositories/nav.py 与 normalization/backfill.py 两层，无共同归属、无一致性
测试。提到 resolve_visible_until + PitDataContext.visible_until，两个消费方
改为取它；并加一条 AST 扫描断言 dt.time.max 全仓只有一处。

H-2：新增适应度测试，遍历 Base.registry 的全部 model，断言继承 IntervalMixin
的必须用三子句生成器、继承 VersionedMixin 的必须用五子句生成器，双向断言。
证伪记录：把 fund_fee 临时改用版本化生成器后测试转红。"
```

---

### Task 2: 收紧 PIT 数据契约 —— `NavPoint.adjusted_nav` 类型收窄 + 链路 quality 聚合

**Files:**
- Modify: `src/fip/platform/source/availability.py:1-8`（新增质量强弱序与 `weakest_quality`）
- Modify: `src/fip/platform/decision_data/pit.py:9-32`
  （`NavPoint.adjusted_nav` 收窄；新增 `NavSeries`；`NavPitRepository` Protocol 返回类型改为 `NavSeries`）
- Modify: `src/fip/services/data_service/repositories/nav.py:90-149`
  （聚合链路 quality，返回 `NavSeries`）
- Modify: `src/fip/platform/cli.py:186-212`（`cmd_pit_nav` 改取 `series.points`，并打印 `chain_quality`）
- Modify: `tests/integration/test_pit_nav_repository.py:69-71`（`_series` 辅助函数）
- Modify: `tests/integration/test_ingest_service.py:141-145`
- Test: `tests/unit/test_pit_contract.py`（新建）
- Test: `tests/integration/test_chain_quality.py`（新建）

**Interfaces:**
- Consumes（Task 1 产出）：
  - `SqlNavPitRepository.__init__(session: Session, visible_until: dt.datetime)`
  - `PitDataContext.visible_until -> dt.datetime`
- Produces（Task 9 的 `FactorInput` 与 Task 12/13 消费）：
  - `fip.platform.source.availability.weakest_quality(qualities: Iterable[str | AvailabilityQuality]) -> AvailabilityQuality`
  - `fip.platform.decision_data.pit.NavPoint`，其 `adjusted_nav: Decimal`（不再是 `Decimal | None`）
  - `fip.platform.decision_data.pit.NavSeries`：
    `points: tuple[NavPoint, ...]`、`chain_quality: str | None`
  - `NavPitRepository.adjusted_nav_series(share_class_id: int, date_from: dt.date,
    date_to: dt.date) -> NavSeries`
  - `NavSeries.chain_quality` 即接口契约里 `FactorInput.chain_quality` 的**唯一**来源；
    D-10 的 `WARNING` 第二条触发条件（链路含 `INFERRED`）据此判定

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/unit/test_pit_contract.py`：

```python
"""PIT 数据契约的形状本身（Plan-1 交接项二.1 / 二.2）。

这些断言不需要数据库：它们锁的是 dataclass 与 Protocol 的**类型契约**，
而类型契约一旦松掉，下游会长出永远不会被执行的 None 分支，或把逐行 quality
误当成链路 quality 使用。
"""

import datetime as dt
import typing
from decimal import Decimal

import pytest

from fip.platform.decision_data.pit import NavPitRepository, NavPoint, NavSeries
from fip.platform.source.availability import AvailabilityQuality, weakest_quality


def test_adjusted_nav_is_not_optional():
    """现算路径要么全有值、要么抛 AdjustedNavUnavailable，绝无 None。

    留着 `Decimal | None` 的后果不是「多一点保险」：它让下游每个消费方都
    必须写一个永远不会被执行的 `is None` 分支，而那个分支里最自然的写法
    恰恰是填 0 或沿用上期 —— 正是 C-6 / G-3 禁止的两件事。
    """
    hints = typing.get_type_hints(NavPoint)
    assert hints["adjusted_nav"] is Decimal


def test_nav_point_keeps_its_own_row_quality():
    """逐行 quality 保留：它是那一行自己的事实，不是链路的结论。"""
    hints = typing.get_type_hints(NavPoint)
    assert hints["availability_quality"] is str


def test_repository_returns_a_series_not_a_bare_list():
    """链路 quality 无处安放是 Plan-1 的结构性缺口，返回类型必须能装下它。"""
    hints = typing.get_type_hints(NavPitRepository.adjusted_nav_series)
    assert hints["return"] is NavSeries


def _point(day: int, quality: str) -> NavPoint:
    return NavPoint(
        effective_at=dt.date(2020, 1, day),
        adjusted_nav=Decimal("1.00000000"),
        unit_nav=Decimal("1.00000000"),
        version=1,
        availability_quality=quality,
    )


def test_empty_series_has_no_chain_quality():
    """没有任何行就没有链路 —— 不得凭空造一个 quality 值出来（G-3）。"""
    series = NavSeries(points=(), chain_quality=None)
    assert series.chain_quality is None


def test_non_empty_series_must_carry_a_chain_quality():
    """反向不变式：有点却没有链路结论，是把 quality 悄悄丢掉。"""
    with pytest.raises(ValueError, match="chain_quality"):
        NavSeries(points=(_point(2, "EXACT"),), chain_quality=None)


def test_empty_series_must_not_carry_a_chain_quality():
    with pytest.raises(ValueError, match="chain_quality"):
        NavSeries(points=(), chain_quality="EXACT")


@pytest.mark.parametrize(
    ("qualities", "expected"),
    [
        (["EXACT"], AvailabilityQuality.EXACT),
        (["EXACT", "EXACT"], AvailabilityQuality.EXACT),
        (["EXACT", "DERIVED"], AvailabilityQuality.DERIVED),
        (["DERIVED", "EXACT"], AvailabilityQuality.DERIVED),
        (["EXACT", "DERIVED", "INFERRED"], AvailabilityQuality.INFERRED),
        (["INFERRED", "EXACT"], AvailabilityQuality.INFERRED),
        (["DERIVED", "DERIVED"], AvailabilityQuality.DERIVED),
        ([AvailabilityQuality.EXACT, "INFERRED"], AvailabilityQuality.INFERRED),
    ],
)
def test_weakest_quality_is_min_over_chain(qualities, expected):
    """EXACT > DERIVED > INFERRED，取最弱者（min-over-chain）。

    方向必须是「取最弱」而不是「取多数」或「取最后一行」：复权值是整条
    累乘链路的函数，链路上任何一行不可靠，产出的值就不可靠。
    """
    assert weakest_quality(qualities) is expected


def test_weakest_quality_rejects_an_empty_chain():
    """空链路没有结论 —— 返回一个默认值就是凭空发明可靠性。"""
    with pytest.raises(ValueError):
        weakest_quality([])


def test_weakest_quality_rejects_unknown_labels():
    with pytest.raises(ValueError):
        weakest_quality(["VERIFIED"])
```

新建 `tests/integration/test_chain_quality.py`：

```python
"""链路 quality 聚合：复权值依赖调用方在返回值里【根本看不到】的行。

Plan-1 交接项二.1：现算后一个点的复权值依赖 date_from 之前的全部历史。
逐行 quality 因此比以前更容易误导 —— 调用方看到窗口内每一行都是 EXACT，
却不知道窗口之前有一行是 INFERRED，而那一行参与了整条累乘链路。
"""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundDistribution, FundNav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-CQ", product_name="链路质量测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A",
                        display_name="链路质量测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _utc(y, m, d, hour=0):
    return dt.datetime(y, m, d, hour, tzinfo=dt.UTC)


def _add_nav(session, sc, day, value, quality, published_at=None,
             provider_available_at=None):
    """按 quality 如实填三个来源列 —— quality_source CHECK 会替我们把关。"""
    if quality == "EXACT":
        available_at = provider_available_at or _utc(day.year, day.month, day.day, 12)
        provider_available_at = available_at
        published_at = published_at or _utc(day.year, day.month, day.day, 9)
    elif quality == "DERIVED":
        published_at = published_at or _utc(day.year, day.month, day.day, 9)
        available_at = published_at
        provider_available_at = None
    else:
        available_at = _utc(day.year, day.month, day.day) + dt.timedelta(days=1)
        published_at = None
        provider_available_at = None
    session.add(FundNav(
        share_class_id=sc.id, effective_at=day, version=1,
        unit_nav=Decimal(value), available_at=available_at,
        availability_quality=quality, published_at=published_at,
        provider_available_at=provider_available_at,
        ingested_at=_utc(2026, 8, 31),
    ))


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-CQ", decision_at=decision_at, data_as_of=decision_at,
        strategy_version="sv-1", policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def _series(db_session, sc, decision_at, date_from, date_to):
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to)


def test_chain_quality_reflects_rows_outside_the_requested_window(db_session, share_class):
    """窗口外的 INFERRED 行必须把整条链路的结论拉到 INFERRED。

    什么情况下它会红：如果实现只聚合【切片后】返回的那些点的 quality，
    窗口内两行都是 EXACT，结论会是 EXACT —— 而 2020-01-02 那行 INFERRED
    参与了每一个后续点的累乘。这正是本任务要堵的那个洞。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "INFERRED")
    _add_nav(db_session, share_class, dt.date(2020, 3, 2), "1.1", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 3, 3), "1.2", "EXACT")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 3, 1), dt.date(2020, 3, 31))

    assert [p.effective_at for p in series.points] == [
        dt.date(2020, 3, 2), dt.date(2020, 3, 3)
    ]
    assert {p.availability_quality for p in series.points} == {"EXACT"}
    assert series.chain_quality == "INFERRED"


def test_chain_quality_is_exact_when_every_row_on_the_chain_is_exact(
    db_session, share_class
):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.1", "EXACT")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert series.chain_quality == "EXACT"


def test_distribution_rows_are_part_of_the_chain(db_session, share_class):
    """分红/拆分行同样参与累乘 —— 它们的 quality 必须计入链路。

    什么情况下它会红：只聚合 fund_nav 而漏掉 fund_distribution。
    一条 INFERRED 的分红事件会改变每一个后续点的复权值，漏算它会让链路
    结论比事实更乐观。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.0", "EXACT")
    db_session.add(FundDistribution(
        share_class_id=share_class.id, effective_at=dt.date(2020, 1, 3), version=1,
        dividend_per_unit=Decimal("0.1"), split_ratio=Decimal("1"),
        available_at=_utc(2020, 1, 4), availability_quality="INFERRED",
        published_at=None, provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert {p.availability_quality for p in series.points} == {"EXACT"}
    assert series.chain_quality == "INFERRED"


def test_empty_result_has_no_chain_quality(db_session, share_class):
    """没有任何可见行时不得凭空给出一个 quality（G-3）。"""
    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert series.points == ()
    assert series.chain_quality is None


def test_rows_after_date_to_do_not_join_the_chain(db_session, share_class):
    """上界之后的行对区间内的值毫无贡献，也就不该影响链路结论。

    与 _NAV_SQL 的「只设上界、不设下界」是同一条理由的两面：链路是
    effective_at <= t 的前向累乘，date_to 之后的行不在任何一条链路上。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2021, 6, 1), "1.5", "INFERRED")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert series.chain_quality == "EXACT"


_STORED = text("""
    SELECT effective_at, adjusted_nav FROM market.fund_nav
    WHERE share_class_id = :share_class_id ORDER BY effective_at
""")


def test_points_are_still_the_quantized_recomputed_values(db_session, share_class):
    """回归：包装成 NavSeries 之后，点本身的精度契约与值都不许变。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0", "EXACT")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.1", "EXACT")
    db_session.flush()

    series = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.adjusted_nav for p in series.points] == [
        Decimal("1.00000000"), Decimal("1.10000000")
    ]
    assert all(-p.adjusted_nav.as_tuple().exponent == 8 for p in series.points)
```

> 本文件里所有断言的对象都是**现算值**，不是 `market.fund_nav.adjusted_nav`
> 那个运维物化列 —— 后者自 Plan-1 Task 15 fix round 3 起已降级为运维物化值，
> 任何决策链路都不得读它。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_pit_contract.py -v`
Expected: FAIL —— `ImportError: cannot import name 'NavSeries' from
'fip.platform.decision_data.pit'`（同时 `weakest_quality` 也不存在）。
把 import 拆开逐条确认后，`test_adjusted_nav_is_not_optional` 的失败输出为
`assert typing.Optional[decimal.Decimal] is Decimal`。

Run: `.venv/bin/pytest tests/integration/test_chain_quality.py -v -m integration`
Expected: FAIL with `AttributeError: 'list' object has no attribute 'points'`。

- [ ] **Step 3: 最小实现**

`src/fip/platform/source/availability.py` —— 在 `AvailabilityQuality` 之后追加：

```python
# EXACT > DERIVED > INFERRED。数值只用于比较强弱，不落库、不进任何输出。
_QUALITY_STRENGTH: dict[AvailabilityQuality, int] = {
    AvailabilityQuality.EXACT: 3,
    AvailabilityQuality.DERIVED: 2,
    AvailabilityQuality.INFERRED: 1,
}


def weakest_quality(
    qualities: Iterable[str | AvailabilityQuality],
) -> AvailabilityQuality:
    """取一条链路上最弱的 availability_quality（min-over-chain）。

    ── 为什么是「最弱」──

    复权净值不是某一行的属性，而是整条前向累乘链路的函数：adj_t 依赖
    effective_at <= t 的【全部】净值行与分红/拆分行。链路上任何一行的
    available_at 是猜出来的（INFERRED），adj_t 的可见时点就同样是猜出来的。
    取平均、取多数、取最后一行都会让一条含 INFERRED 的链路对外呈现得比事实
    更可靠 —— 那是把不确定性藏起来，不是度量它。

    空链路【必须】抛错而不是返回一个默认值：没有行就没有结论，返回
    INFERRED 会让「一条都没有」与「有行但都靠猜」变得无法区分 —— 这正是
    Plan-1 在 grouping_status 上反复吃过亏的那一条（「没识别出」≠「确认没有」）。
    """
    strengths = []
    for quality in qualities:
        parsed = AvailabilityQuality(quality)  # 未知标签在此抛 ValueError
        strengths.append((_QUALITY_STRENGTH[parsed], parsed))
    if not strengths:
        raise ValueError("空链路没有 availability_quality 结论，不得返回默认值")
    return min(strengths, key=lambda pair: pair[0])[1]
```

顶部 import 补 `from collections.abc import Iterable`。

`src/fip/platform/decision_data/pit.py` —— `NavPoint` 收窄并加 `NavSeries`：

```python
@dataclass(frozen=True, slots=True)
class NavPoint:
    """PIT 解析出的单个净值点。

    adjusted_nav 是 Decimal 而【不是】Decimal | None：现算路径要么整条序列
    都有值、要么抛 AdjustedNavUnavailable（C-6 的 fail-closed 粒度已由
    Plan-1 提到整条序列）。留着 Optional 会让每个消费方都写一个永远不执行的
    None 分支，而那个分支里最自然的写法恰是填 0 或沿用上期。

    availability_quality 是【这一行自己】的质量，不是复权值的质量 ——
    后者看 NavSeries.chain_quality。两者容易混淆，且混淆的方向是危险的：
    逐行 EXACT 完全可能对应一条含 INFERRED 的链路。
    """

    effective_at: dt.date
    adjusted_nav: Decimal
    unit_nav: Decimal
    version: int
    availability_quality: str


@dataclass(frozen=True, slots=True)
class NavSeries:
    """一次 PIT 复权净值查询的完整结果：点 + 链路结论。

    chain_quality 是 points 之外【必须】随行的第二个事实：现算 adj_t 依赖
    date_from 之前的全部历史，那些行调用方在 points 里根本看不到
    （Plan-1 交接项二.1）。把它们的 availability_quality 按 min-over-chain
    聚合成一个值，是 Task 9 的 FactorInput.chain_quality 的唯一来源，
    也是 D-10 中 FactorStatus = WARNING 第二条触发条件的判定依据。

    不变式：points 为空 ⟺ chain_quality 为 None。没有行就没有链路结论，
    有行却没有结论则说明聚合被漏掉了 —— 两个方向都在构造期拒绝。
    """

    points: tuple[NavPoint, ...]
    chain_quality: str | None

    def __post_init__(self) -> None:
        if bool(self.points) != (self.chain_quality is not None):
            raise ValueError(
                f"NavSeries 不变式被破坏：points={len(self.points)} 条，"
                f"chain_quality={self.chain_quality!r}。"
                "空序列不得携带 chain_quality，非空序列不得缺 chain_quality"
            )
```

`NavPitRepository` 的方法签名改返回类型：

```python
    def adjusted_nav_series(
        self,
        share_class_id: int,
        date_from: dt.date,
        date_to: dt.date,
    ) -> NavSeries: ...
```

`src/fip/services/data_service/repositories/nav.py` —— 两条 SQL 各补一列
`availability_quality`（`_NAV_SQL` 已有；`_EVENT_SQL` 需新增），方法末尾改为：

```python
_EVENT_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, dividend_per_unit, split_ratio, availability_quality
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at <= :date_to
    ORDER BY effective_at, version DESC
""")
```

```python
        nav_rows = self._session.execute(_NAV_SQL, params).mappings().all()
        if not nav_rows:
            # 没有任何可见行 —— 没有链路，因此没有链路结论（不得填默认值）。
            return NavSeries(points=(), chain_quality=None)
        event_rows = self._session.execute(_EVENT_SQL, params).mappings().all()

        points = compute_adjusted_nav(...)   # 原样不动
        adjusted = {p.effective_at: _quantize_nav(p.adjusted_nav) for p in points}

        # 链路 = 参与累乘的【全部】行，而不是切片后返回的那些。
        # 两条 SQL 都只设上界不设下界，取回的正好就是整条链路（见文件顶部
        # 对「只设上界」的说明），所以这里直接对取回的全部行聚合。
        chain_quality = weakest_quality(
            [row["availability_quality"] for row in nav_rows]
            + [row["availability_quality"] for row in event_rows]
        ).value

        return NavSeries(
            points=tuple(
                NavPoint(
                    effective_at=row["effective_at"],
                    adjusted_nav=adjusted[row["effective_at"]],
                    unit_nav=row["unit_nav"],
                    version=row["version"],
                    availability_quality=row["availability_quality"],
                )
                for row in nav_rows
                if date_from <= row["effective_at"] <= date_to
            ),
            chain_quality=chain_quality,
        )
```

> ⚠️ 切片后 points 可能为空而 nav_rows 非空（请求窗口落在数据之前）。此时
> `NavSeries` 的不变式会拒绝 `points=() + chain_quality="..."`。这不是理论
> 情形：`test_rows_after_date_to_do_not_join_the_chain` 的镜像用例就会命中。
> 因此把不变式写成「chain_quality 随 **nav_rows** 而非 points」是错的 —— 正确
> 做法是切片为空时同样返回 `NavSeries(points=(), chain_quality=None)`：窗口内
> 没有任何点，调用方拿不到任何值，也就不需要（也不该拿到）链路结论。在
> `return` 之前先算出切片：

```python
        sliced = tuple(
            NavPoint(...)  # 同上
            for row in nav_rows
            if date_from <= row["effective_at"] <= date_to
        )
        if not sliced:
            return NavSeries(points=(), chain_quality=None)
        return NavSeries(points=sliced, chain_quality=chain_quality)
```

顶部 import 补：

```python
from fip.platform.decision_data.pit import NavPoint, NavSeries
from fip.platform.source.availability import weakest_quality
```

`src/fip/platform/cli.py` 的 `cmd_pit_nav`（第 186-212 行）：

```python
            series = PitDataContext(
                context=context, session=session
            ).navs().adjusted_nav_series(
                share_class.id,
                dt.date.fromisoformat(args.date_from),
                dt.date.fromisoformat(args.date_to),
            )
```

```python
    print(f"{share_class.display_name} @ decision_at={decision_at}  "
          f"共 {len(series.points)} 条  链路质量={series.chain_quality}")
    for point in series.points[:10]:
        print(f"  {point.effective_at}  unit={point.unit_nav}  "
              f"adj={point.adjusted_nav}  v{point.version}  {point.availability_quality}")
```

`tests/integration/test_pit_nav_repository.py` 的 `_series`（第 69-71 行）改为
返回点序列，18 处既有调用点不动：

```python
def _series(db_session, sc, decision_at, date_from, date_to):
    """既有用例断言的都是【点】；链路 quality 由 test_chain_quality.py 覆盖。"""
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to).points
```

`tests/integration/test_ingest_service.py:141-145`：

```python
    series = PitDataContext(context=ctx, session=db_session).navs().adjusted_nav_series(
        sc.id, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )
    # 1.10 → 除息 0.10 后 1.00：复权后收益为 0
    assert [p.adjusted_nav for p in series.points] == [Decimal("1.1"), Decimal("1.1")]
    # AKShare 链路恒 INFERRED（G-15），这里顺带钉住它
    assert series.chain_quality == "INFERRED"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_pit_contract.py -v`
Run: `.venv/bin/pytest tests/integration/test_chain_quality.py -v -m integration`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 17 条全绿；既有 281 条全绿（`_series` 与 `test_ingest_service`
的两处适配是唯一改动点）。`make typecheck` 必须干净 —— 类型收窄之后 mypy
会对任何残留的 `NavPoint.adjusted_nav is None` 分支报 unreachable 之外的错误；
当前 src 下没有这类分支（已确认），若有则一并删除，**不得**改成 `# type: ignore`。

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_pit_contract.py tests/integration/test_chain_quality.py
git commit --only \
  src/fip/platform/source/availability.py \
  src/fip/platform/decision_data/pit.py \
  src/fip/services/data_service/repositories/nav.py \
  src/fip/platform/cli.py \
  tests/unit/test_pit_contract.py \
  tests/integration/test_chain_quality.py \
  tests/integration/test_pit_nav_repository.py \
  tests/integration/test_ingest_service.py \
  -m "feat(pit): 收紧 PIT 数据契约 —— adjusted_nav 去 Optional，新增链路 quality 聚合

Plan-1 交接项二.1 / 二.2（打包项，改的是同一个 dataclass）：

· NavPoint.adjusted_nav 由 Decimal | None 收窄为 Decimal。现算路径要么全有值
  要么抛 AdjustedNavUnavailable，下游的 is None 分支是死代码，而那个分支里最
  自然的写法恰是 C-6 禁止的填 0 / 沿用上期。
· 新增 NavSeries(points, chain_quality)。现算 adj_t 依赖 date_from 之前的全部
  历史，调用方在 points 里看不到那些行；把链路上全部净值行与分红/拆分行的
  availability_quality 按 min-over-chain（EXACT > DERIVED > INFERRED）聚合成
  一个值随序列返回，作为 FactorInput.chain_quality 的唯一来源。
· 空链路不得返回默认 quality：weakest_quality([]) 抛错，NavSeries 用
  __post_init__ 双向锁死「空序列 ⟺ 无链路结论」。"
```

---

### Task 3: `libs/quant_engine` —— 7 个数值函数 + QE-1 适应度测试

**Files:**
- Create: `src/fip/libs/__init__.py`
- Create: `src/fip/libs/quant_engine/__init__.py`（由 `src/fip/quant_engine/__init__.py` git mv 而来）
- Create: `src/fip/libs/quant_engine/precision.py`
- Create: `src/fip/libs/quant_engine/errors.py`
- Create: `src/fip/libs/quant_engine/stats.py`
- Create: `src/fip/libs/quant_engine/series.py`
- Create: `src/fip/libs/quant_engine/correlation.py`
- Modify: `src/fip/strategy_library/__init__.py` → `src/fip/libs/strategy_library/__init__.py`
  （D-3 的落位一次做完；Task 4 在此基础上往里填内容）
- Modify: `tests/unit/test_package_layout.py:22-37`（`test_all_layer_packages_importable` 的清单）
- Modify: `tests/fitness/test_architecture.py:154-170,204-231,331-336`
  （两条 I/O 纯净性检查、runtime_mode 检查、`GUARDED_ROOTS` 三处的扫描根路径）
- Test: `tests/unit/test_quant_engine.py`（新建）
- Test: `tests/fitness/test_architecture.py`（新增 QE-1 两条）

**Interfaces:**
- Consumes: 无（本任务不依赖 Task 1/2）
- Produces（跨任务接口契约原文，Task 9 / 12 / 13 消费）：
  - `fip.libs.quant_engine.returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]`
  - `fip.libs.quant_engine.stdev(xs: Sequence[Decimal], ddof: int) -> Decimal`
  - `fip.libs.quant_engine.mean(xs: Sequence[Decimal]) -> Decimal`
  - `fip.libs.quant_engine.median(xs: Sequence[Decimal]) -> Decimal`
  - `fip.libs.quant_engine.running_max(xs: Sequence[Decimal]) -> list[Decimal]`
  - `fip.libs.quant_engine.rolling_windows(xs: Sequence[Decimal], window: int, step: int) -> list[list[Decimal]]`
  - `fip.libs.quant_engine.spearman(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> Decimal`
  - 异常：`QuantEngineError`（基类，`ValueError` 的子类）、`InsufficientObservations`、
    `UndefinedResult`、`UnsupportedBasis` —— Task 9 据此把 `FactorStatus` 置为
    `UNAVAILABLE`（观测不足）或 `INVALID`（数学上无意义）
  - 精度契约常量：`QE_PRECISION = 60`、`QE_GUARD_DIGITS = 60`
  - 收益率口径字面量：`SIMPLE = "SIMPLE"`

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/unit/test_quant_engine.py`：

```python
"""L1 数值层：无业务语义，全部 Decimal，精度契约显式（G-2 容差 1e-10）。

本文件的每一条断言都只关心【数值】。任何需要「因为它是净值 / 因为它是
Sharpe」才成立的性质都不属于这一层，属 strategy_library。
"""

from decimal import Decimal as D

import pytest

from fip.libs.quant_engine import (
    QE_GUARD_DIGITS,
    QE_PRECISION,
    SIMPLE,
    InsufficientObservations,
    UndefinedResult,
    UnsupportedBasis,
    mean,
    median,
    returns,
    rolling_windows,
    running_max,
    spearman,
    stdev,
)


# --- returns -----------------------------------------------------------

def test_returns_are_simple_and_one_shorter_than_the_input():
    assert returns([D("1.0"), D("1.1"), D("1.21")], SIMPLE) == [D("0.1"), D("0.1")]


def test_returns_of_a_single_price_is_empty_not_zero():
    """一个价格没有收益率 —— 返回 [0] 会凭空造出一个观测（G-3）。"""
    assert returns([D("1.0")], SIMPLE) == []
    assert returns([], SIMPLE) == []


def test_returns_rejects_an_unsupported_basis():
    """LOG 口径在 M1 明确不支持（D-9：return_basis = SIMPLE, PROVISIONAL）。

    静默按 SIMPLE 处理会让「配置里写了 LOG」这件事完全没有后果。
    """
    with pytest.raises(UnsupportedBasis):
        returns([D("1.0"), D("1.1")], "LOG")


@pytest.mark.parametrize("bad", [D("0"), D("-1.0")])
def test_returns_rejects_non_positive_denominator(bad):
    """价格为 0 / 负数时收益率无定义 —— 不得返回 inf 或 0。"""
    with pytest.raises(UndefinedResult):
        returns([bad, D("1.0")], SIMPLE)


def test_returns_are_exact_for_values_representable_in_decimal():
    """用 Decimal 而非 float 的理由：0.1 在二进制下不可精确表示。"""
    assert returns([D("1"), D("1.1")], SIMPLE)[0] == D("0.1")


# --- stats -------------------------------------------------------------

def test_mean_of_empty_raises_rather_than_returning_zero():
    with pytest.raises(InsufficientObservations):
        mean([])


def test_mean_is_exact_on_a_terminating_quotient():
    assert mean([D("1"), D("2"), D("3")]) == D("2")


def test_median_odd_and_even():
    assert median([D("3"), D("1"), D("2")]) == D("2")
    assert median([D("4"), D("1"), D("3"), D("2")]) == D("2.5")


def test_median_of_empty_raises():
    with pytest.raises(InsufficientObservations):
        median([])


def test_stdev_sample_matches_the_hand_computed_value():
    """[1,2,3,4]：均值 2.5，偏差平方和 5，ddof=1 → sqrt(5/3)。"""
    expected = (D(5) / D(3)).sqrt()
    actual = stdev([D(1), D(2), D(3), D(4)], ddof=1)
    assert abs(actual - expected) < D("1e-40")


def test_stdev_population_differs_from_sample():
    """ddof 是【必填参数】而不是默认值：样本与总体在 n 小时差异不可忽略
    （D-9：volatility.ddof = 1，PROVISIONAL）。给默认值会让口径选择静默发生。
    """
    assert stdev([D(1), D(2), D(3), D(4)], ddof=0) != stdev(
        [D(1), D(2), D(3), D(4)], ddof=1
    )


def test_stdev_of_a_constant_series_is_zero():
    assert stdev([D(2), D(2), D(2)], ddof=1) == 0


def test_stdev_requires_more_observations_than_ddof():
    """n == ddof 时分母为 0 —— 抛错，不返回 0，也不返回 inf。

    返回 0 是这里最危险的错法：Sharpe = 超额收益 / 0 会变成除零，
    而返回 0 波动率的基金在任何排序里都是「零风险」。
    """
    with pytest.raises(InsufficientObservations):
        stdev([D(1)], ddof=1)
    with pytest.raises(InsufficientObservations):
        stdev([], ddof=0)


def test_stdev_rejects_negative_ddof():
    with pytest.raises(ValueError):
        stdev([D(1), D(2)], ddof=-1)


# --- series ------------------------------------------------------------

def test_running_max_is_non_decreasing_and_same_length():
    xs = [D(1), D(3), D(2), D(5), D(4)]
    out = running_max(xs)
    assert out == [D(1), D(3), D(3), D(5), D(5)]
    assert len(out) == len(xs)
    assert all(b >= a for a, b in zip(out, out[1:], strict=True))


def test_running_max_of_empty_is_empty():
    assert running_max([]) == []


def test_rolling_windows_are_full_windows_only():
    xs = [D(i) for i in range(10)]
    out = rolling_windows(xs, window=4, step=3)
    assert out == [xs[0:4], xs[3:7], xs[6:10]]
    assert all(len(w) == 4 for w in out)


def test_rolling_windows_returns_empty_when_the_input_is_shorter_than_the_window():
    """不得返回一个残缺窗口 —— 那会让 min_obs 的判定被悄悄绕过。"""
    assert rolling_windows([D(1), D(2)], window=4, step=1) == []


def test_rolling_windows_rejects_non_positive_window_or_step():
    with pytest.raises(ValueError):
        rolling_windows([D(1)], window=0, step=1)
    with pytest.raises(ValueError):
        rolling_windows([D(1)], window=1, step=0)


# --- correlation -------------------------------------------------------

def test_spearman_is_one_for_a_strictly_increasing_relation():
    xs = [D(1), D(2), D(3), D(4)]
    ys = [D(10), D(20), D(30), D(40)]
    assert spearman(xs, ys) == 1


def test_spearman_is_minus_one_for_a_strictly_decreasing_relation():
    xs = [D(1), D(2), D(3), D(4)]
    ys = [D(40), D(30), D(20), D(10)]
    assert spearman(xs, ys) == -1


def test_spearman_is_rank_based_not_value_based():
    """单调非线性变换不改变 Spearman —— 这正是 IC 选它而非 Pearson 的理由。"""
    xs = [D(1), D(2), D(3), D(4)]
    linear = [D(1), D(2), D(3), D(4)]
    convex = [D(1), D(4), D(9), D(16)]
    assert spearman(xs, linear) == spearman(xs, convex)


def test_spearman_uses_average_ranks_for_ties():
    """并列取【平均秩】，这是 Spearman 的标准并列处理。

    ⚠️ 这与 D-20 为基金排名裁定的 COMPETITION_RANK 【不是】同一件事：
    COMPETITION_RANK 用于对外呈现的名次（并列占用相同名次、后续跳号），
    平均秩用于相关系数的内部计算（跳号会让相关系数产生系统性偏差）。
    两者服务于不同目的，不得互相替换。
    [1,1,2] 的平均秩是 [1.5, 1.5, 3]。
    """
    assert spearman([D(1), D(1), D(2)], [D(5), D(5), D(9)]) == 1


def test_spearman_rejects_length_mismatch():
    with pytest.raises(ValueError):
        spearman([D(1), D(2)], [D(1)])


def test_spearman_needs_at_least_two_observations():
    with pytest.raises(InsufficientObservations):
        spearman([D(1)], [D(2)])


def test_spearman_is_undefined_when_one_side_is_all_ties():
    """全并列一侧的秩方差为 0 —— 相关系数无定义，抛错而不是返回 0。

    返回 0 会被下游读成「该因子与后续收益不相关」，而事实是
    「这个横截面上该因子没有区分度，算不出相关性」。两者结论完全不同。
    """
    with pytest.raises(UndefinedResult):
        spearman([D(1), D(1), D(1)], [D(1), D(2), D(3)])


# --- 精度契约（G-2）----------------------------------------------------

def test_precision_contract_is_declared_and_generous():
    """内部计算位数 = 有效位 + 保护位，与 adjusted_nav.py 同一套做法。"""
    assert QE_PRECISION == 60
    assert QE_GUARD_DIGITS == 60


def test_results_are_bit_identical_on_recomputation():
    """G-2：同一输入重算必须【完全一致】，不是「在容差内一致」。"""
    xs = [D("1.0000001") ** i for i in range(1, 60)]
    assert stdev(xs, ddof=1) == stdev(xs, ddof=1)
    assert spearman(xs, list(reversed(xs))) == spearman(xs, list(reversed(xs)))


def test_long_chain_stays_well_inside_the_reproducibility_tolerance():
    """保护位真的起作用：1000 期链路上 mean 的相对误差远小于 1e-10。"""
    xs = [D(1)] * 1000
    assert mean(xs) == D(1)
    assert abs(stdev(xs, ddof=1)) < D("1e-50")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_quant_engine.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'fip.libs'`（收集阶段）。

- [ ] **Step 3: 最小实现**

先落位（D-3：spec 的目录树表达的是分层关系，src-layout 下落到 `src/fip/libs/`）：

```bash
mkdir -p src/fip/libs
printf '"""L1 层：quant_engine（数值）与 strategy_library（策略领域逻辑）。\n\n两者都不做任何 I/O，数据经 platform/decision_data 的 PIT 端口注入。\n依赖方向：strategy_library → quant_engine，反向为设计错误（QE-1）。\n"""\n' \
  > src/fip/libs/__init__.py
git mv src/fip/quant_engine src/fip/libs/quant_engine
git mv src/fip/strategy_library src/fip/libs/strategy_library
```

`src/fip/libs/quant_engine/errors.py`：

```python
class QuantEngineError(ValueError):
    """数值层无法产出结果。

    继承 ValueError 而不是 RuntimeError：这些都是【输入不满足前提】，
    不是运行环境问题。调用方（strategy_library）据此把 FactorStatus 置为
    UNAVAILABLE 或 INVALID，【绝不】捕获后填 0 / 填 inf / 填组内均值（G-3）。
    """


class InsufficientObservations(QuantEngineError):
    """观测数不足以定义该统计量（如 n <= ddof、空序列）。

    映射到 FactorStatus.UNAVAILABLE（D-10：观测数 < min_obs）。
    """


class UndefinedResult(QuantEngineError):
    """数学上无定义（分母为 0、负方差、非正的价格基数）。

    映射到 FactorStatus.INVALID（D-10：计算过程产生数学上无意义的结果）。
    """


class UnsupportedBasis(QuantEngineError):
    """请求的口径本层不实现。

    静默退回到默认口径会让配置里写下的口径选择完全没有后果 —— 这与
    Plan-1 在 config loader 上确立的「不阻断但不静默」是同一条原则的严格版：
    口径不是可以将就的东西。
    """
```

`src/fip/libs/quant_engine/precision.py`：

```python
"""精度契约（G-2：可复现性容差 1e-10）。

做法与 services/data_service/normalization/adjusted_nav.py 一致，且是刻意
对齐的：内部滚动用「有效位 + 保护位」，只在产出时舍回有效位。先降精度再
累加会让舍入误差随序列长度累积 —— 因子序列可达数千期，那正是这一层最长的
链路。

60 位保护位是宽裕余量而非从误差增长公式推出的紧界（与 adjusted_nav.py 的
说明同源）。Decimal 的运算在给定 context 下是确定性的，因此「同一输入重算
必须完全一致」是构造性成立的，不是靠容差兜住的。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal, localcontext

QE_PRECISION = 60
QE_GUARD_DIGITS = 60
_COMPUTE_PRECISION = QE_PRECISION + QE_GUARD_DIGITS


@contextmanager
def computing() -> Iterator[None]:
    """在保护位精度下做中间运算。

    默认 context 的 traps 保留不动：DivisionByZero / InvalidOperation 必须
    抛出，不得静默产出 NaN 或 Infinity（G-3 的数值层对应物）。
    """
    with localcontext() as ctx:
        ctx.prec = _COMPUTE_PRECISION
        yield


def finalize(value: Decimal) -> Decimal:
    """把中间结果舍回对外的有效位数。"""
    with localcontext() as ctx:
        ctx.prec = QE_PRECISION
        return +value
```

`src/fip/libs/quant_engine/stats.py`：

```python
from collections.abc import Sequence
from decimal import Decimal

from fip.libs.quant_engine.errors import InsufficientObservations, UndefinedResult
from fip.libs.quant_engine.precision import computing, finalize


def mean(xs: Sequence[Decimal]) -> Decimal:
    values = list(xs)
    if not values:
        raise InsufficientObservations("mean 需要至少 1 个观测，实得 0")
    with computing():
        total = sum(values, Decimal(0))
        return finalize(total / Decimal(len(values)))


def median(xs: Sequence[Decimal]) -> Decimal:
    values = sorted(xs)
    n = len(values)
    if n == 0:
        raise InsufficientObservations("median 需要至少 1 个观测，实得 0")
    mid = n // 2
    if n % 2 == 1:
        return finalize(values[mid])
    with computing():
        return finalize((values[mid - 1] + values[mid]) / Decimal(2))


def stdev(xs: Sequence[Decimal], ddof: int) -> Decimal:
    """标准差。ddof 是【必填】的，没有默认值。

    D-9 把 volatility.ddof = 1 登记为 PROVISIONAL 口径选择。给这里一个默认值
    会让那条配置形同虚设：调用方忘记传时会静默拿到某一个口径，而样本与总体
    在 n 较小时差异不可忽略。
    """
    if ddof < 0:
        raise ValueError(f"ddof 不得为负，实得 {ddof}")
    values = list(xs)
    n = len(values)
    if n - ddof <= 0:
        raise InsufficientObservations(
            f"stdev(ddof={ddof}) 需要至少 {ddof + 1} 个观测，实得 {n}"
        )
    with computing():
        m = sum(values, Decimal(0)) / Decimal(n)
        ss = sum(((v - m) ** 2 for v in values), Decimal(0))
        variance = ss / Decimal(n - ddof)
        if variance < 0:
            raise UndefinedResult(f"方差为负（{variance}），数值不稳定")
        return finalize(variance.sqrt())
```

`src/fip/libs/quant_engine/series.py`：

```python
from collections.abc import Sequence
from decimal import Decimal

from fip.libs.quant_engine.errors import UndefinedResult, UnsupportedBasis
from fip.libs.quant_engine.precision import computing, finalize

SIMPLE = "SIMPLE"


def returns(prices: Sequence[Decimal], basis: str) -> list[Decimal]:
    """相邻两点的收益率序列，长度为 len(prices) - 1。

    basis 只接受 SIMPLE（r_t = p_t / p_{t-1} - 1）。对数口径本层不实现：
    对数收益不可横截面相加，而本平台的因子标准化与 IC 全是横截面运算。
    传入其它口径【抛错】而不是退回 SIMPLE。
    """
    if basis != SIMPLE:
        raise UnsupportedBasis(f"本层只实现 {SIMPLE} 口径，收到 {basis!r}")
    values = list(prices)
    if len(values) < 2:
        return []
    out: list[Decimal] = []
    with computing():
        for previous, current in zip(values, values[1:], strict=True):
            if previous <= 0:
                raise UndefinedResult(
                    f"基数 {previous} 非正，收益率无定义（不得返回 0 或 inf）"
                )
            out.append(finalize(current / previous - Decimal(1)))
    return out


def running_max(xs: Sequence[Decimal]) -> list[Decimal]:
    """前缀最大值序列，与输入等长、单调不减。"""
    out: list[Decimal] = []
    current: Decimal | None = None
    for value in xs:
        current = value if current is None or value > current else current
        out.append(current)
    return out


def rolling_windows(
    xs: Sequence[Decimal], window: int, step: int
) -> list[list[Decimal]]:
    """只产出【完整】窗口。

    残缺窗口必须被丢弃而不是补齐：补齐等于用更少的观测冒充一个窗口，
    会让 min_obs 的判定（D-10）被悄悄绕过。
    """
    if window < 1:
        raise ValueError(f"window 必须 >= 1，实得 {window}")
    if step < 1:
        raise ValueError(f"step 必须 >= 1，实得 {step}")
    values = list(xs)
    return [
        values[i : i + window]
        for i in range(0, len(values) - window + 1, step)
    ]
```

`src/fip/libs/quant_engine/correlation.py`：

```python
from collections.abc import Sequence
from decimal import Decimal

from fip.libs.quant_engine.errors import InsufficientObservations, UndefinedResult
from fip.libs.quant_engine.precision import computing, finalize


def _average_ranks(values: list[Decimal]) -> list[Decimal]:
    """并列取平均秩（Spearman 的标准并列处理）。

    ⚠️ 与 D-20 裁定的 COMPETITION_RANK 是两回事：后者用于对外呈现的名次
    （并列占用相同名次、之后跳号），平均秩用于相关系数的内部计算 ——
    跳号会让秩序列的均值偏离 (n+1)/2，给相关系数引入系统性偏差。
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks: list[Decimal] = [Decimal(0)] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        with computing():
            average = (Decimal(i + 1) + Decimal(j + 1)) / Decimal(2)
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def spearman(xs: Sequence[Decimal], ys: Sequence[Decimal]) -> Decimal:
    """秩相关系数。IC 用它而非 Pearson：因子与后续收益的关系未必线性。

    任一侧全并列时秩方差为 0，相关系数【无定义】—— 抛 UndefinedResult 而不是
    返回 0。返回 0 会被下游读成「该因子与后续收益不相关」，而事实是
    「这个横截面上该因子没有区分度，算不出相关性」。
    """
    a = list(xs)
    b = list(ys)
    if len(a) != len(b):
        raise ValueError(f"两个序列长度不等：{len(a)} vs {len(b)}")
    if len(a) < 2:
        raise InsufficientObservations(f"spearman 需要至少 2 个观测，实得 {len(a)}")
    ra = _average_ranks(a)
    rb = _average_ranks(b)
    with computing():
        n = Decimal(len(a))
        ma = sum(ra, Decimal(0)) / n
        mb = sum(rb, Decimal(0)) / n
        cov = sum(((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True)), Decimal(0))
        va = sum(((x - ma) ** 2 for x in ra), Decimal(0))
        vb = sum(((y - mb) ** 2 for y in rb), Decimal(0))
        if va == 0 or vb == 0:
            raise UndefinedResult(
                "至少一侧的秩全部并列，秩方差为 0，Spearman 无定义"
            )
        # 写成 (va * vb).sqrt() 而不是 va.sqrt() * vb.sqrt()：后者取两次
        # 无理数的近似再相乘，完全单调的输入也会得到 0.9999…9 而不是 1，
        # 让「完美秩相关 == 1」这条最基本的断言变得只能靠容差成立。
        # 前者在 va * vb 恰为完全平方（秩序列的常见情形）时是精确的。
        return finalize(cov / (va * vb).sqrt())
```

`src/fip/libs/quant_engine/__init__.py`：

```python
"""L1 数值层：矩阵、统计、时序。【无任何业务语义】（QE-1）。

本包不得 import fip.libs.strategy_library / fip.services / fip.platform，
标识符里也不得出现基金业务词汇 —— 两条都由
tests/fitness/test_architecture.py 断言。判据不是「用不用得上」，而是
「这段代码换到另一个完全不同的领域还成不成立」。
"""

from fip.libs.quant_engine.correlation import spearman
from fip.libs.quant_engine.errors import (
    InsufficientObservations,
    QuantEngineError,
    UndefinedResult,
    UnsupportedBasis,
)
from fip.libs.quant_engine.precision import QE_GUARD_DIGITS, QE_PRECISION
from fip.libs.quant_engine.series import SIMPLE, returns, rolling_windows, running_max
from fip.libs.quant_engine.stats import mean, median, stdev

__all__ = [
    "QE_GUARD_DIGITS",
    "QE_PRECISION",
    "SIMPLE",
    "InsufficientObservations",
    "QuantEngineError",
    "UndefinedResult",
    "UnsupportedBasis",
    "mean",
    "median",
    "returns",
    "rolling_windows",
    "running_max",
    "spearman",
    "stdev",
]
```

`tests/unit/test_package_layout.py` 的清单（第 22-37 行）改两行：

```python
        "fip.libs.quant_engine",
        "fip.libs.strategy_library",
```

`tests/fitness/test_architecture.py` 三处扫描根路径改为两段：

```python
        for f in _py_files("libs", "strategy_library")     # 三处
        for f in _py_files("libs", "quant_engine")          # 一处
```

```python
GUARDED_ROOTS: list[tuple[str, ...]] = [
    ("libs", "strategy_library"),
    ("libs", "quant_engine"),
    ("services", "portfolio_service"),
    ("platform",),
]
```

- [ ] **Step 4: 写 QE-1 适应度测试并确认它会红**

在 `tests/fitness/test_architecture.py` 末尾追加：

```python
# --- QE-1：Quant Engine 不含业务语义 -----------------------------------

QE_BANNED_PREFIXES = (
    "fip.libs.strategy_library",
    "fip.services",
    "fip.platform",
)


def test_quant_engine_does_not_depend_on_upper_layers():
    """QE-1 前半：依赖方向单向 strategy_library → quant_engine。

    反向依赖不会报错（Python 允许），只会在下一次有人想把 quant_engine
    抽成独立库时才暴露 —— 那时它已经缠满了业务类型。
    """
    offenders = []
    for f in _py_files("libs", "quant_engine"):
        bad = [
            m for m in _dotted_imports(f)
            if any(_touches(m, prefix) for prefix in QE_BANNED_PREFIXES)
        ]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"quant_engine 依赖了上层：{offenders}"


# 基金业务词汇。判据是「这个词在一个与基金无关的领域里还讲不讲得通」：
# window / step / ddof / ranks 讲得通，nav / sharpe / peer 讲不通。
# 刻意【不】收录 price / return / correlation —— 它们是通用数值/统计词汇，
# 收录会让接口契约里已经定死的 returns(prices, basis) 无法落地。
FUND_VOCABULARY = {
    "fund", "nav", "sharpe", "sortino", "calmar", "drawdown", "peer",
    "factor", "score", "benchmark", "universe", "portfolio", "dividend",
    "eligibility", "tier", "profile", "volatility", "alpha", "backtest",
    "strategy", "fee", "share_class", "shareclass", "investment",
}


def _identifier_words(name: str) -> set[str]:
    """把标识符切成词。用词级相等而非裸子串匹配。

    裸子串会把 'navigate' 判成含 'nav'，而一条会误报的适应度测试的下场
    是被人直接关掉。词级匹配再额外容忍一个复数 s（drawdowns → drawdown）。
    """
    words = {w for w in name.lower().split("_") if w}
    return words | {w[:-1] for w in words if w.endswith("s") and len(w) > 1}


def _declared_identifiers(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {path.stem}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_quant_engine_identifiers_carry_no_fund_vocabulary():
    """QE-1 后半：标识符不得出现基金业务词汇。

    什么情况下它会红：有人在这一层写下 def annualized_nav_return(...)
    或 class SharpeInput —— 那意味着业务语义正在往数值层渗，而这一层的
    全部价值就是它对领域一无所知。
    """
    offenders = []
    for f in _py_files("libs", "quant_engine"):
        hits = sorted(
            name for name in _declared_identifiers(f)
            if _identifier_words(name) & FUND_VOCABULARY
        )
        if hits:
            offenders.append((f.relative_to(SRC), hits))
    assert not offenders, f"quant_engine 出现基金业务词汇：{offenders}"


def test_qe_vocabulary_scanner_actually_matches():
    """守卫：直接对扫描器断言，不依赖仓库当前状态。

    没有这条，上面那条在 FUND_VOCABULARY 拼错或 _identifier_words 退化成
    恒返回空集时会静默变成一条永远通过的测试。
    """
    assert _identifier_words("annualized_nav_return") & FUND_VOCABULARY == {"nav"}
    assert _identifier_words("rolling_windows") & FUND_VOCABULARY == set()
    assert _identifier_words("drawdowns") & FUND_VOCABULARY == {"drawdown"}
    assert _identifier_words("navigate") & FUND_VOCABULARY == set()
```

制造红灯以证伪（G-18）：

```bash
cat >> src/fip/libs/quant_engine/stats.py <<'PY'


def annualized_nav_drawdown(xs):  # 临时：证伪 QE-1
    from fip.services.data_service.models.market import FundNav  # noqa: F401
    return xs
PY
.venv/bin/pytest tests/fitness/test_architecture.py -k quant_engine -v
```

Expected: 两条同时 FAIL ——
`AssertionError: quant_engine 依赖了上层：[(PosixPath('libs/quant_engine/stats.py'),
['fip.services.data_service.models.market', ...])]` 与
`AssertionError: quant_engine 出现基金业务词汇：[(PosixPath('libs/quant_engine/stats.py'),
['FundNav', 'annualized_nav_drawdown'])]`。把这段输出写进报告，然后还原：

Run: `git checkout -- src/fip/libs/quant_engine/stats.py`

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_quant_engine.py -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 30 条全绿（`test_quant_engine.py` 26 条 + QE-1 3 条 + 扫描器守卫 1 条）；
既有 281 条全绿（改动只有三个测试文件里的扫描根路径与模块名清单）。

- [ ] **Step 6: 提交**

```bash
git add src/fip/libs tests/unit/test_quant_engine.py
git commit --only \
  src/fip/libs \
  tests/unit/test_quant_engine.py \
  tests/unit/test_package_layout.py \
  tests/fitness/test_architecture.py \
  -m "feat(quant-engine): L1 数值层落位 src/fip/libs 并实现 7 个函数 + QE-1

D-3：spec §2.1 的顶层 libs/ 在 src-layout 下落位为 src/fip/libs/，
一致性优先于字面路径（目录树表达的是分层关系，不是文件系统路径）。
git mv 保留了 quant_engine / strategy_library 两个空包的历史。

7 个函数按跨任务接口契约逐字实现，全部 Decimal：
returns / stdev / mean / median / running_max / rolling_windows / spearman。
精度契约显式化（QE_PRECISION=60 + 60 位保护位，做法与 adjusted_nav.py 对齐），
G-2 的『同一输入重算一致』是构造性成立的而非靠容差。

四类失败一律抛错、绝不填值（G-3）：观测不足、数学无定义、口径不支持、
参数非法。Spearman 全并列时抛 UndefinedResult 而不是返回 0 —— 后者会被
读成『不相关』，而事实是『算不出相关性』。

QE-1 两条适应度测试（依赖方向 + 标识符词汇），并附扫描器自身的守卫用例。
证伪记录：临时加入 annualized_nav_drawdown + import FundNav，两条同时转红。"
```

---

### Task 4: `libs/strategy_library` 骨架 + SDL-1 / SDL-2 / SDL-3 适应度测试

**Files:**
- Create: `src/fip/libs/strategy_library/factor/__init__.py`
- Create: `src/fip/libs/strategy_library/factor/definitions.py`
- Create: `src/fip/libs/strategy_library/factor/status.py`
- Create: `src/fip/libs/strategy_library/peer_group/__init__.py`
- Create: `src/fip/libs/strategy_library/score/__init__.py`
- Create: `src/fip/libs/strategy_library/ranking/__init__.py`
- Create: `src/fip/libs/strategy_library/universe/__init__.py`
- Modify: `src/fip/libs/strategy_library/__init__.py`
- Create: `src/fip/platform/versioning.py`（SDL-3 的落点）
- Modify: `src/fip/platform/cli.py:169-181`（`cmd_pit_nav` 的 `code_version` 由常量改为实算）
- Modify: `tests/fitness/test_architecture.py`（SDL-1 加 repositories 禁令；新增 SDL-3 三条）
- Test: `tests/unit/test_factor_contract.py`（新建）
- Test: `tests/unit/test_code_version.py`（新建）

**Interfaces:**
- Consumes（Task 3 产出）：`fip.libs.quant_engine` 已落位于 `src/fip/libs/`；
  `src/fip/libs/strategy_library/` 已由 `git mv` 就位
- Produces（跨任务接口契约原文，Task 9 起全线消费）：
  - `fip.libs.strategy_library.factor.FactorStatus`（StrEnum：`VALID` / `WARNING` /
    `INVALID` / `UNAVAILABLE`）
  - `fip.libs.strategy_library.factor.PreferenceDirection`（StrEnum：
    `HIGHER_IS_BETTER` / `LOWER_IS_BETTER`）
  - `fip.libs.strategy_library.factor.FactorInput`（frozen slots dataclass：
    `effective_at: date`、`adjusted_navs: tuple[Decimal, ...]`、
    `nav_dates: tuple[date, ...]`、`chain_quality: str`、
    `risk_free_rate: Decimal | None`、`mar: Decimal | None`）
  - `fip.libs.strategy_library.factor.FactorResult`（frozen slots dataclass：
    `factor_id: str`、`value: Decimal | None`、`status: FactorStatus`、
    `reason: str`、`observation_count: int`）
  - `fip.platform.versioning.compute_code_version(roots: Iterable[pathlib.Path] | None = None) -> str`
  - `fip.platform.versioning.CODE_VERSION_ROOTS: tuple[pathlib.Path, ...]`
- 明确**不**产出：`compute_factor`（Task 9）、`percentile_rank`（Task 12）、
  `PeerGroupKey`（Task 11）—— 本任务只建骨架与契约类型

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/unit/test_factor_contract.py`：

```python
"""因子契约类型的形状（跨任务接口契约的唯一权威定义在实现计划里）。

Task 9 起有六个任务同时消费这些类型。任何一个字段名/类型漂移都会在
下游产生一个「看起来能跑但语义错了」的实现，因此在骨架阶段就锁死。
"""

import datetime as dt
import typing
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from fip.libs.strategy_library.factor import (
    FactorInput,
    FactorResult,
    FactorStatus,
    PreferenceDirection,
)


def test_factor_status_has_exactly_four_values():
    """四值，不多不少。多一个值意味着下游的 match 出现未覆盖分支。"""
    assert {s.value for s in FactorStatus} == {
        "VALID", "WARNING", "INVALID", "UNAVAILABLE"
    }


def test_factor_status_is_a_string_enum():
    """StrEnum：直接落库、直接进 JSON，不需要在边界上再转一次。"""
    assert FactorStatus.VALID == "VALID"


def test_preference_direction_has_exactly_two_values():
    """『中性』方向【不实现】（D-11 第 3 点）：M1 无 Benchmark、TE 恒
    UNAVAILABLE。这是一个已知缺口，写在枚举注释里；这里锁住它没有被
    悄悄补上一个语义未定的第三值。
    """
    assert {d.value for d in PreferenceDirection} == {
        "HIGHER_IS_BETTER", "LOWER_IS_BETTER"
    }


def test_factor_input_fields_match_the_contract():
    hints = typing.get_type_hints(FactorInput)
    assert [f.name for f in fields(FactorInput)] == [
        "effective_at", "adjusted_navs", "nav_dates",
        "chain_quality", "risk_free_rate", "mar",
    ]
    assert hints["effective_at"] is dt.date
    assert hints["chain_quality"] is str
    assert hints["risk_free_rate"] == Decimal | None
    assert hints["mar"] == Decimal | None


def test_factor_input_is_frozen():
    """纯函数只吃它（SDL-1）。可变输入会让『同一输入重算一致』（G-2）失效。"""
    inp = FactorInput(
        effective_at=dt.date(2026, 8, 31),
        adjusted_navs=(Decimal("1.0"),),
        nav_dates=(dt.date(2026, 8, 31),),
        chain_quality="INFERRED",
        risk_free_rate=None,
        mar=None,
    )
    with pytest.raises(FrozenInstanceError):
        inp.chain_quality = "EXACT"  # type: ignore[misc]


def test_factor_input_rejects_misaligned_navs_and_dates():
    """两个并行元组长度必须一致 —— 错位后每个因子都会静默算错。"""
    with pytest.raises(ValueError):
        FactorInput(
            effective_at=dt.date(2026, 8, 31),
            adjusted_navs=(Decimal("1.0"), Decimal("1.1")),
            nav_dates=(dt.date(2026, 8, 31),),
            chain_quality="INFERRED",
            risk_free_rate=None,
            mar=None,
        )


def test_factor_result_value_is_none_for_every_non_valid_status():
    """G-3 的类型层落地：非 VALID 时 value 必须为 None，【绝不填 0】。"""
    for status in (FactorStatus.INVALID, FactorStatus.UNAVAILABLE):
        with pytest.raises(ValueError, match="value"):
            FactorResult(
                factor_id="F-RET-001", value=Decimal("0"), status=status,
                reason="观测不足", observation_count=3,
            )


def test_factor_result_requires_a_reason_when_not_valid():
    """status 非 VALID 时 reason 必填（接口契约原文）。

    空 reason 会让下游只知道『没有值』而不知道『为什么没有值』——
    UNAVAILABLE 与 INVALID 的处置方式完全不同（前者按缺失处理，后者要告警）。
    """
    with pytest.raises(ValueError, match="reason"):
        FactorResult(
            factor_id="F-RET-001", value=None,
            status=FactorStatus.UNAVAILABLE, reason="", observation_count=0,
        )


def test_factor_result_accepts_a_value_when_valid():
    result = FactorResult(
        factor_id="F-RET-001", value=Decimal("0.12"),
        status=FactorStatus.VALID, reason="", observation_count=252,
    )
    assert result.value == Decimal("0.12")


def test_factor_result_valid_must_carry_a_value():
    """反向：VALID 却没有值，说明产出方漏了一条分支。"""
    with pytest.raises(ValueError, match="value"):
        FactorResult(
            factor_id="F-RET-001", value=None,
            status=FactorStatus.VALID, reason="", observation_count=252,
        )
```

新建 `tests/unit/test_code_version.py`：

```python
"""SDL-3：strategy_library 的版本参与 Code Version 计算。

Code Version 是决策快照的复现入口之一（DEC-3）。若策略库改了而 Code Version
不变，两次跑出不同结果的决策会带着【同一个】版本号落库 —— 快照从此不能
证明任何事情。
"""

import pathlib

import pytest

from fip.platform.versioning import CODE_VERSION_ROOTS, compute_code_version


def test_strategy_library_is_one_of_the_roots():
    assert any(
        root.parts[-2:] == ("libs", "strategy_library") for root in CODE_VERSION_ROOTS
    )


def test_quant_engine_is_one_of_the_roots():
    assert any(
        root.parts[-2:] == ("libs", "quant_engine") for root in CODE_VERSION_ROOTS
    )


def test_every_declared_root_exists():
    """守卫：根目录被改名后哈希会静默算在一个空集合上。"""
    for root in CODE_VERSION_ROOTS:
        assert root.is_dir(), f"{root} 不存在，Code Version 会静默漏掉它"


def test_code_version_is_a_stable_hex_digest():
    first = compute_code_version()
    second = compute_code_version()
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def _root(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    root = tmp_path / name
    root.mkdir()
    (root / "m.py").write_text(body, encoding="utf-8")
    return root


def test_content_change_changes_the_version(tmp_path):
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "m.py").write_text("X = 2\n", encoding="utf-8")
    assert compute_code_version([root]) != before


def test_new_file_changes_the_version(tmp_path):
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "n.py").write_text("Y = 1\n", encoding="utf-8")
    assert compute_code_version([root]) != before


def test_rename_changes_the_version(tmp_path):
    """内容相同但文件名不同必须得到不同版本 —— 路径进哈希，不只哈希内容。"""
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "m.py").rename(root / "renamed.py")
    assert compute_code_version([root]) != before


def test_non_python_files_do_not_change_the_version(tmp_path):
    """只哈希 .py：__pycache__、编辑器临时文件不得让版本号无故变化。"""
    root = _root(tmp_path, "pkg", "X = 1\n")
    before = compute_code_version([root])
    (root / "notes.txt").write_text("hello", encoding="utf-8")
    assert compute_code_version([root]) == before


def test_missing_root_fails_loudly(tmp_path):
    """不存在的根【抛错】而不是跳过：跳过会让版本号在缺半个库时照常产出。"""
    with pytest.raises(FileNotFoundError):
        compute_code_version([tmp_path / "nope"])


def test_a_real_change_in_strategy_library_changes_the_real_version():
    """最强的一条：在真实的 strategy_library 里写一个文件，版本必须变。

    什么情况下它会红：CODE_VERSION_ROOTS 里漏了 strategy_library，或
    compute_code_version 只哈希了包名而没哈希内容。用 try/finally 保证
    临时文件一定被清掉。
    """
    root = next(
        r for r in CODE_VERSION_ROOTS if r.parts[-2:] == ("libs", "strategy_library")
    )
    probe = root / "_code_version_probe.py"
    before = compute_code_version()
    try:
        probe.write_text("PROBE = 1\n", encoding="utf-8")
        assert compute_code_version() != before
    finally:
        probe.unlink(missing_ok=True)
    assert compute_code_version() == before
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_factor_contract.py tests/unit/test_code_version.py -v`

Expected: 两个文件都在收集阶段 FAIL ——
`ModuleNotFoundError: No module named 'fip.libs.strategy_library.factor'` 与
`ModuleNotFoundError: No module named 'fip.platform.versioning'`。

- [ ] **Step 3: 最小实现**

`src/fip/libs/strategy_library/factor/status.py`：

```python
from enum import StrEnum


class FactorStatus(StrEnum):
    """因子值的状态四值。

    上游 01-fund-evaluation §7.3 只给了【消费方】处理规则；【生产方】何时
    置哪个值在缺失的 08-factor-output 里，由设计定案 D-10 补齐：

      VALID        观测数 >= min_obs，全部依赖（R_f / MAR）可用，未触发降级
      WARNING      观测数落在 [min_obs, min_obs × 1.5)；
                   或输入序列的 chain_quality 含 INFERRED（NavSeries 产出，Task 2）
      INVALID      计算过程产生数学上无意义的结果（分母为 0、负方差、NaN）
      UNAVAILABLE  观测数 < min_obs；或必需依赖缺失（无 MAR 配置、无 R_f）

    消费方规则（上游原文）：VALID 参与；WARNING 参与但标记须【传递】；
    INVALID 不参与且告警；UNAVAILABLE 不参与、按缺失处理。
    四者都【不得】被任何填充值替代（G-3）。
    """

    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"
```

`src/fip/libs/strategy_library/factor/definitions.py`：

```python
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from fip.libs.strategy_library.factor.status import FactorStatus


class PreferenceDirection(StrEnum):
    """因子的偏好方向。

    ── 已知缺口（D-11 第 3 点，如实登记）──

    上游提到 Tracking Error 在 Active Equity 画像下方向为「中性」，而「中性」
    不属于这个枚举。M1 无 Benchmark、TE 恒 UNAVAILABLE，因此本 Plan
    【不实现】中性方向。补上它需要先定义「中性」在 Percentile Rank 下的
    语义（离目标值越近越好？那需要一个目标值，而上游没给），不是加一个
    枚举值就能了事的。
    """

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


@dataclass(frozen=True, slots=True)
class FactorInput:
    """因子计算的全部输入。纯函数只吃它，不碰数据库（SDL-1）。

    adjusted_navs 与 nav_dates 是两个【并行】元组，按日期升序，已按 PIT 解析
    （available_at <= decision_at，G-1）。分成两个元组而不是一个 (date, value)
    序列，是为了让 quant_engine 直接吃 adjusted_navs 而不必先解包 —— 代价是
    错位风险，因此在构造期就断言等长。

    chain_quality 来自 NavSeries.chain_quality（Task 2）：它是整条累乘链路上
    全部行的 availability_quality 按 min-over-chain 聚合的结果，【不是】任何
    单行的 quality。D-10 中 WARNING 的第二条触发条件读的正是它。

    risk_free_rate 与 mar 都可以是 None，且两个 None 的含义不同：
      · risk_free_rate is None —— R_f 曲线在该 decision_at 解析不出来
      · mar is None            —— mar_policy 未配置（G-6：必填无默认）
    两者都会让依赖它的因子 UNAVAILABLE，【绝不】用 0 兜底。上游的理由是
    「Downside Volatility 与 Sortino 两者数值相同但含义相反 —— 设默认会让
    配置遗漏静默产出看起来正常的 Sortino」。
    """

    effective_at: dt.date
    adjusted_navs: tuple[Decimal, ...]
    nav_dates: tuple[dt.date, ...]
    chain_quality: str
    risk_free_rate: Decimal | None
    mar: Decimal | None

    def __post_init__(self) -> None:
        if len(self.adjusted_navs) != len(self.nav_dates):
            raise ValueError(
                f"adjusted_navs（{len(self.adjusted_navs)} 条）与 nav_dates"
                f"（{len(self.nav_dates)} 条）长度不等，两个并行元组一旦错位，"
                "每个因子都会静默算错"
            )


@dataclass(frozen=True, slots=True)
class FactorResult:
    """一个因子在一个时点的产出。

    value 与 status 的组合被构造期不变式锁死：
      · status 非 VALID ⇒ value 必须为 None。填 0 是 G-3 明令禁止的
        —— 0 波动率在任何排序里都是「零风险」，0 收益率是「持平」，
        两者都会被下游当成真实观测参与横截面统计。
      · status 为 VALID ⇒ value 必须有值。VALID 而无值说明产出方漏了分支。
      · status 非 VALID ⇒ reason 必填。只说「没有值」而不说「为什么」，
        会让 UNAVAILABLE（按缺失处理）与 INVALID（要告警）无法区分。
    """

    factor_id: str
    value: Decimal | None
    status: FactorStatus
    reason: str
    observation_count: int

    def __post_init__(self) -> None:
        if self.status is FactorStatus.VALID:
            if self.value is None:
                raise ValueError(
                    f"{self.factor_id}: status=VALID 却没有 value"
                )
        elif self.status is FactorStatus.WARNING:
            if self.value is None:
                raise ValueError(
                    f"{self.factor_id}: status=WARNING 仍然参与评分，必须有 value"
                )
            if not self.reason:
                raise ValueError(
                    f"{self.factor_id}: status=WARNING 时 reason 必填"
                )
        else:
            if self.value is not None:
                raise ValueError(
                    f"{self.factor_id}: status={self.status} 时 value 必须为 None，"
                    f"实得 {self.value!r} —— 不得填 0、上期值、inf 或组内均值（G-3）"
                )
            if not self.reason:
                raise ValueError(
                    f"{self.factor_id}: status={self.status} 时 reason 必填，"
                    "否则下游无法区分『按缺失处理』与『要告警』"
                )
```

`src/fip/libs/strategy_library/factor/__init__.py`：

```python
"""因子域的策略逻辑。Task 9 在此补 compute.py，Task 12 补 normalize.py，
Task 13 补 effectiveness.py。本模块只做身份与契约类型。
"""

from fip.libs.strategy_library.factor.definitions import (
    FactorInput,
    FactorResult,
    PreferenceDirection,
)
from fip.libs.strategy_library.factor.status import FactorStatus

__all__ = [
    "FactorInput",
    "FactorResult",
    "FactorStatus",
    "PreferenceDirection",
]
```

其余四个子包各建一个说明性的空 `__init__.py`（内容为一行 docstring，
指明由哪个任务填充），例如
`src/fip/libs/strategy_library/peer_group/__init__.py`：

```python
"""Peer Group 构建。Task 5 放分类编码约定，Task 11 放 build.py。

C-4 / G-5：本包【不得】import 评分 / 排名 / Universe 模块，否则形成
Score → Universe → Peer Group → Score 的循环依赖 —— 该循环不报错，
只让每次重算得到不同分数，直接破坏 NFR-REPRO-001。
"""
```

`src/fip/platform/versioning.py`：

```python
"""Code Version 的计算（SDL-3）。

Code Version 随决策快照落库（DEC-3），是复现该次决策的入口之一。因此它
必须覆盖【所有会改变计算结果的代码】：策略库与数值层。两者任一改动而
版本号不变，等于让两次跑出不同结果的决策带着同一个版本号落库。

本模块只读文件、不 import 被度量的包 —— 度量者不该被度量对象的 import
副作用影响，也不必承担 platform 层反向依赖 libs 层的问题。
"""

import hashlib
import pathlib
from collections.abc import Iterable

_FIP = pathlib.Path(__file__).resolve().parent.parent

# SDL-3：strategy_library 的版本参与 Code Version 计算。quant_engine 同理 ——
# 一个纯数值函数改了舍入方式，因子值就会变，而它同样不在任何 Strategy /
# Policy 版本里。
CODE_VERSION_ROOTS: tuple[pathlib.Path, ...] = (
    _FIP / "libs" / "quant_engine",
    _FIP / "libs" / "strategy_library",
)


def compute_code_version(roots: Iterable[pathlib.Path] | None = None) -> str:
    """对给定包根下全部 .py 文件的【路径 + 内容】做 SHA-256。

    路径也进哈希：两个内容相同、文件名不同的模块是不同的代码。

    只哈希 .py：__pycache__ 与编辑器临时文件不得让版本号无故变化 ——
    一个每次运行都变的版本号与没有版本号等价。

    根不存在时【抛错】而不是跳过：跳过会让版本号在缺半个库时照常产出，
    这正是「静默失效」最典型的形状。
    """
    digest = hashlib.sha256()
    for root in (CODE_VERSION_ROOTS if roots is None else tuple(roots)):
        if not root.is_dir():
            raise FileNotFoundError(
                f"Code Version 根目录不存在：{root}。"
                "缺失的根【不得】被跳过 —— 那会让版本号在代码缺失时照常产出"
            )
        for path in sorted(root.rglob("*.py")):
            digest.update(f"{root.name}/{path.relative_to(root)}".encode())
            digest.update(b"\x00")
            digest.update(path.read_bytes())
            digest.update(b"\x00")
    return digest.hexdigest()
```

`src/fip/platform/cli.py` 的 `cmd_pit_nav`（第 169-181 行）——
把占位的 `code_version="cli"` 换成实算，让 SDL-3 在生产装配路径上非空洞：

```python
from fip.platform.versioning import compute_code_version
```

```python
        code_version=compute_code_version(),
```

- [ ] **Step 4: 收紧 SDL-1 并补 SDL-3 适应度测试**

`tests/fitness/test_architecture.py` —— SDL-1 当前只查 `IO_LIBS`
（第 154-161 行），按 D-3 的表格还须显式禁 repositories：

```python
SDL_BANNED_PREFIXES = (
    "fip.services.data_service.repositories",
    "fip.services.factor_service.repositories",
    "fip.services.fund_service.repositories",
    "fip.services.portfolio_service.repositories",
    "fip.services.backtest_service.repositories",
)


def test_strategy_library_does_not_import_any_repository():
    """SDL-1 的第二半：不含数据访问【实现】，也不 import 任何 repository。

    只查 sqlalchemy 是不够的：一个 repository 模块可以自己 import sqlalchemy
    而策略库只 import 那个 repository —— 库清单扫描对这种两跳完全失明，
    而它恰恰是「策略库偷偷开始自己取数」最自然的第一步。
    """
    offenders = []
    for f in _py_files("libs", "strategy_library"):
        bad = [
            m for m in _dotted_imports(f)
            if any(_touches(m, prefix) for prefix in SDL_BANNED_PREFIXES)
        ]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"strategy_library import 了 repository：{offenders}"


def test_strategy_library_participates_in_code_version():
    """SDL-3：该包的版本参与 Code Version 计算。

    这条放在 fitness 而不只是 unit：它约束的是【架构事实】——
    哪些目录被认为「会改变计算结果」。
    """
    from fip.platform.versioning import CODE_VERSION_ROOTS

    roots = {root.parts[-2:] for root in CODE_VERSION_ROOTS}
    assert ("libs", "strategy_library") in roots
    assert ("libs", "quant_engine") in roots
```

制造红灯以证伪（G-18）：

```bash
cat > src/fip/libs/strategy_library/factor/_probe.py <<'PY'
from fip.services.data_service.repositories.nav import SqlNavPitRepository  # noqa: F401

RUNTIME_MODE_PROBE = "BACKTEST"
PY
.venv/bin/pytest tests/fitness/test_architecture.py -k strategy_library -v
```

Expected: 三条 FAIL ——
`test_strategy_library_has_no_io_dependency` 不会红（`_probe.py` 自身没 import
sqlalchemy，这正是上面 docstring 说的「两跳失明」），而
`test_strategy_library_does_not_import_any_repository` 红：
`AssertionError: strategy_library import 了 repository：[(PosixPath('libs/strategy_library/factor/_probe.py'),
['fip.services.data_service.repositories.nav', ...])]`；
`test_strategy_library_has_no_runtime_mode_branch` 红：
`AssertionError: strategy_library 出现运行模式分支：[(PosixPath('libs/strategy_library/factor/_probe.py'), ['BACKTEST'])]`。
把输出写进报告，然后：

Run: `rm src/fip/libs/strategy_library/factor/_probe.py`

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_factor_contract.py tests/unit/test_code_version.py -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 22 条全绿（契约 10 条 + Code Version 10 条 + SDL 2 条）。

- [ ] **Step 6: 提交**

```bash
git add src/fip/libs/strategy_library src/fip/platform/versioning.py \
        tests/unit/test_factor_contract.py tests/unit/test_code_version.py
git commit --only \
  src/fip/libs/strategy_library \
  src/fip/platform/versioning.py \
  src/fip/platform/cli.py \
  tests/unit/test_factor_contract.py \
  tests/unit/test_code_version.py \
  tests/fitness/test_architecture.py \
  -m "feat(strategy-library): 骨架 + 契约类型，并补齐 SDL-1/2/3 适应度测试

骨架按实现计划的 File Structure 建出 factor / peer_group / score / ranking /
universe 五个子包，本任务只落契约类型：FactorStatus（D-10 的生产方触发条件
写进 docstring）、PreferenceDirection（『中性』方向作为已知缺口如实登记）、
FactorInput、FactorResult。

FactorResult 用 __post_init__ 把 G-3 锁进类型层：status 非 VALID 时 value
必须为 None 且 reason 必填 —— 填 0 会让『零波动率 = 零风险』这种结论静默
流进横截面统计。FactorInput 断言两个并行元组等长。

SDL-1 补第二半：除 sqlalchemy/psycopg 之外，显式禁 import 任何 repository
（库清单扫描对『策略库 → repository → sqlalchemy』这条两跳路径失明）。
SDL-3 首次有落点：新增 platform/versioning.py，把 libs/quant_engine 与
libs/strategy_library 纳入 Code Version；cli 的 code_version 由占位串 'cli'
改为实算，让这条约束在生产装配路径上非空洞。

证伪记录：临时放入 _probe.py（import repository + 字面量 'BACKTEST'），
SDL-1 第二条与 SDL-2 同时转红；SDL-1 的库清单那条【没有】红 —— 这正是
补第二条的理由。"
```

---

### Task 5: 基金分类灌入（D-5 / D-6）—— `基金类型` → `fund.fund_classification_history`

**Files:**
- Create: `src/fip/libs/strategy_library/peer_group/classification.py`
- Modify: `src/fip/services/data_service/models/fund.py:179-195`
  （`FundClassificationHistory` 补「至多一条开放区间」的部分唯一索引）
- Create: `db/migrations/versions/0016_fund_classification_open_interval.py`
- Modify: `src/fip/services/data_service/ingest.py:53-68`（`FundListIngestResult` 加一个字段）
- Modify: `src/fip/services/data_service/ingest.py:235-323`（`ingest_fund_list` 不再丢弃 `基金类型`）
- Modify: `src/fip/platform/cli.py:124-142`（`cmd_ingest_funds` 报告分类冲突）
- Test: `tests/unit/test_classification_codes.py`（新建）
- Test: `tests/integration/test_fund_classification_ingest.py`（新建）

**Interfaces:**
- Consumes（Task 4 产出）：`fip.libs.strategy_library.peer_group` 包已存在
- Produces（Task 11 消费，构造 `PeerGroupKey`）：
  - `fip.libs.strategy_library.peer_group.classification.CLASSIFICATION_SCHEME: str = "AKSHARE_FUND_TYPE"`
  - `fip.libs.strategy_library.peer_group.classification.UNCLASSIFIED_CODE: str = "UNCLASSIFIED"`
  - `normalize_classification_code(raw: str | None) -> str`
  - `level_1(code: str) -> str` —— `code.split("-")[0]`，**不落库、不另存列**
  - `is_groupable(code: str) -> bool` —— `UNCLASSIFIED` 恒 `False`（D-6）
  - `fip.services.data_service.ingest.ClassificationConflict`（frozen dataclass：
    `product_name: str`、`codes: tuple[str, ...]`，含 `describe() -> str`）
  - `FundListIngestResult.classification_conflicts: tuple[ClassificationConflict, ...]`
  - `fund.fund_classification_history` 里每个 `fund_id` 在 `AKSHARE_FUND_TYPE`
    scheme 下至多一条开放区间（数据库不变式 `uq_fch_open_interval`）

---

- [ ] **Step 1: 写失败的测试（纯函数部分）**

新建 `tests/unit/test_classification_codes.py`：

```python
"""Fund Classification 的编码约定（D-5 / D-6，均为【补齐】）。

⚠️ 这是【补齐】不是【裁定】：AKShare 的 `基金类型` 是数据供应商的商业分类，
不是投研定义的资产类别体系。一旦有正式分类体系，应整体替换 scheme 值
而非改代码 —— 这正是把 scheme 做成一个字段而不是硬编码的理由。
"""

import pytest

from fip.libs.strategy_library.peer_group.classification import (
    CLASSIFICATION_SCHEME,
    UNCLASSIFIED_CODE,
    is_groupable,
    level_1,
    normalize_classification_code,
)


def test_scheme_is_the_provider_scoped_label():
    assert CLASSIFICATION_SCHEME == "AKSHARE_FUND_TYPE"


@pytest.mark.parametrize(
    "raw",
    ["混合型-偏股", "指数型-股票", "债券型-混合二级", "股票型", "FOF-稳健型"],
)
def test_code_is_the_full_original_string(raw):
    """存【完整原串】（L2），不切、不映射、不翻译。

    切成 L1 存库会把「指数型-股票」与「指数型-固收」压成同一个码，
    而它们在真实数据里是 5589 只与 676 只两个完全不同的群体。
    """
    assert normalize_classification_code(raw) == raw


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_maps_to_unclassified_and_is_never_dropped(raw):
    """D-6：实测全市场 99 只基金的 `基金类型` 为空串。

    如实落库（不丢弃、不猜测），但它不是一个类别，是「我们不知道它属于
    哪个类别」—— 这两件事的区别正是 Plan-1 在 grouping_status 上反复吃过
    亏的那一条。
    """
    assert normalize_classification_code(raw) == UNCLASSIFIED_CODE


def test_whitespace_is_stripped_but_inner_text_is_untouched():
    assert normalize_classification_code("  混合型-偏股 ") == "混合型-偏股"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("混合型-偏股", "混合型"),
        ("指数型-股票", "指数型"),
        ("债券型-混合二级", "债券型"),
        ("股票型", "股票型"),          # 无连字符：L1 == L2
        ("FOF-稳健型", "FOF"),
        ("指数型-海外股票", "指数型"),
    ],
)
def test_level_1_is_derived_never_stored(code, expected):
    """L1 由 code.split("-")[0] 派生（D-5）。

    派生规则属 Strategy Library，不属数据 —— 所以【不另存一列】。
    存第二列意味着两份真值，两者一旦分叉无法判定谁对（与 D-15 对
    investment_eligibility 存引用而非副本是同一条理由）。
    """
    assert level_1(code) == expected


def test_unclassified_has_itself_as_level_1():
    """UNCLASSIFIED 无连字符，L1 就是它自己 —— 但它仍然不可分组。"""
    assert level_1(UNCLASSIFIED_CODE) == UNCLASSIFIED_CODE


def test_unclassified_is_not_groupable():
    """D-6：UNCLASSIFIED【不得】构成任何 Peer Group。

    落在这一类的基金：Evaluation Status = NOT_ELIGIBLE，理由 UNCLASSIFIED，
    不进入任何横截面计算。什么情况下这条会红：有人为了「让样本量够 30」
    把 UNCLASSIFIED 当成一个类别 —— 那会让一组彼此毫无可比性的基金
    互相排名，且排名看起来完全正常。
    """
    assert is_groupable(UNCLASSIFIED_CODE) is False


@pytest.mark.parametrize("code", ["混合型-偏股", "股票型", "FOF-稳健型"])
def test_real_codes_are_groupable(code):
    assert is_groupable(code) is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_classification_codes.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named
'fip.libs.strategy_library.peer_group.classification'`。

- [ ] **Step 3: 实现纯函数**

`src/fip/libs/strategy_library/peer_group/classification.py`：

```python
"""Fund Classification 的编码约定（设计定案 D-5 / D-6，两条都是【补齐】）。

── 为什么这段代码住在 strategy_library 而不是 data_service ──

它是【派生规则】而不是数据：L1 怎么从 code 切出来、哪些 code 可以构成
Peer Group，都是策略决定。放在 data_service 会让 Task 11 的 Peer Group
构建反过来依赖数据层。依赖方向 services → libs 是允许的，反向不是。

── PROVISIONAL 的边界 ──

AKShare 的 `基金类型` 是数据供应商的商业分类，不是投研定义的资产类别体系。
拿到正式分类体系后应整体替换 CLASSIFICATION_SCHEME 的取值并重灌一遍
`fund_classification_history`，而不是改这里的切分逻辑 —— scheme 之所以是
一个字段，就是为了让「换一套分类体系」是一次数据操作而不是一次代码改造。
"""

CLASSIFICATION_SCHEME = "AKSHARE_FUND_TYPE"

# 「我们不知道它属于哪个类别」，不是「它属于一个叫 UNCLASSIFIED 的类别」。
# 这两件事的区别决定了它不可分组（见 is_groupable）。
UNCLASSIFIED_CODE = "UNCLASSIFIED"

_LEVEL_SEPARATOR = "-"


def normalize_classification_code(raw: str | None) -> str:
    """把上游的 `基金类型` 原串归一为 classification_code。

    只做两件事：去首尾空白、把空值映射为 UNCLASSIFIED。【不切分、不翻译、
    不归并】—— 存的是完整原串（L2），层级由 level_1 在读侧派生。
    """
    if raw is None:
        return UNCLASSIFIED_CODE
    code = raw.strip()
    return code if code else UNCLASSIFIED_CODE


def level_1(code: str) -> str:
    """大类（连字符之前）。无连字符时 L1 == L2（如「股票型」）。

    实测全市场取值分布（27718 只）：
      L1: 混合型 指数型 债券型 股票型 货币型 FOF QDII Reits 商品 其他
      L2: 混合型-偏股 5693 · 指数型-股票 5589 · 债券型-长债 2797 …

    【不另存一列】：多存一份就是多一份真值，两者分叉后无法判定谁对。
    """
    return code.split(_LEVEL_SEPARATOR)[0]


def is_groupable(code: str) -> bool:
    """该 code 是否可以构成 Peer Group（D-6）。

    UNCLASSIFIED 恒 False。把它当成一个类别会让一组彼此毫无可比性的基金
    互相排名，且排名看起来完全正常 —— 这是本文件里唯一一条会造成
    「静默错误结论」的规则，因此它必须是一个函数而不是散落各处的 if。
    """
    return code != UNCLASSIFIED_CODE
```

- [ ] **Step 4: 写失败的集成测试（灌入与区间语义）**

新建 `tests/integration/test_fund_classification_ingest.py`：

```python
"""`基金类型` 的灌入（D-5 / D-6）。

Plan-1 的 ingest_fund_list 读了 `基金类型` 却把它丢弃 —— 与 Plan-1 Task 19
修掉的「code 被丢弃」是同一个模式：数据契约里声明了、取回来了、然后在
解析时静默蒸发。
"""

import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import text

from fip.libs.strategy_library.peer_group.classification import (
    CLASSIFICATION_SCHEME,
    UNCLASSIFIED_CODE,
)
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import Fund, FundClassificationHistory

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 9, 10, 18, 0, tzinfo=dt.UTC)


def _service(session, frame: pd.DataFrame, now=FIXED_NOW) -> IngestService:
    adapter = AkShareSourceAdapter(
        clock=lambda: now, caller=lambda *_a, **_k: frame
    )
    return IngestService(session, adapter, disclosure_lag_days=1)


def _rows(session, product_name: str) -> list[FundClassificationHistory]:
    fund = session.query(Fund).filter_by(product_name=product_name).one()
    return (
        session.query(FundClassificationHistory)
        .filter_by(fund_id=fund.id)
        .order_by(FundClassificationHistory.valid_from)
        .all()
    )


SIMPLE = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["混合型-偏股", "混合型-偏股"],
})


def test_classification_is_persisted_with_the_full_original_string(db_session):
    """存完整原串（L2），scheme 记为 AKSHARE_FUND_TYPE。"""
    _service(db_session, SIMPLE).ingest_fund_list()
    rows = _rows(db_session, "测试蓝筹混合")
    assert len(rows) == 1
    assert rows[0].classification_scheme == CLASSIFICATION_SCHEME
    assert rows[0].classification_code == "混合型-偏股"


def test_no_level_1_column_exists_on_the_table(db_session):
    """L1 是派生量，【不落库】（D-5）。

    什么情况下它会红：有人为了查询方便加一列 classification_level_1 —— 那
    就有了两份真值，转型时改一列忘一列，Peer Group 会静默按旧大类分组。
    """
    columns = {c.name for c in FundClassificationHistory.__table__.columns}
    assert not {c for c in columns if "level" in c or "l1" in c}


def test_the_interval_is_open_and_starts_at_the_ingest_date(db_session):
    """valid_from 取落库当日：我们【就是】在这一刻才知道这条分类。

    不去伪造一个更早的生效日 —— 那会让区间表宣称平台在看到分类之前它就
    已生效（C-12，与 _ensure_provider_identity 同一条理由）。
    """
    _service(db_session, SIMPLE).ingest_fund_list()
    row = _rows(db_session, "测试蓝筹混合")[0]
    assert row.valid_from == FIXED_NOW.date()
    assert row.valid_to is None
    assert row.availability_quality == "INFERRED"   # G-15：AKShare 链路恒 INFERRED
    assert row.published_at is None
    assert row.provider_available_at is None


def test_reingesting_the_same_classification_is_idempotent(db_session):
    svc = _service(db_session, SIMPLE)
    svc.ingest_fund_list()
    svc.ingest_fund_list()
    assert len(_rows(db_session, "测试蓝筹混合")) == 1


EMPTY = pd.DataFrame({
    "基金代码": ["000003"],
    "基金简称": ["测试无类型混合A"],
    "基金类型": [""],
})


def test_empty_type_is_stored_as_unclassified_not_dropped(db_session):
    """D-6：实测 99 只基金的 `基金类型` 为空串。如实落库，不丢弃、不猜测。"""
    _service(db_session, EMPTY).ingest_fund_list()
    rows = _rows(db_session, "测试无类型混合")
    assert len(rows) == 1
    assert rows[0].classification_code == UNCLASSIFIED_CODE


# 实测数据里真实存在的两类「同一产品主干、份额类别间类型不一致」：
#   兴全盈禧多元配置三个月持有混合(FOF)  A=FOF-稳健型  C=FOF-均衡型
#   中信建投民享稳健养老目标一年持有混合发起式(FOF)  A=FOF-稳健型  Y=''
# 全市场 15350 个产品主干中有 4 个命中，不是理论情形。
PARTIAL_BLANK = pd.DataFrame({
    "基金代码": ["000004", "000005"],
    "基金简称": ["测试养老FOFA", "测试养老FOFY"],
    "基金类型": ["FOF-稳健型", ""],
})

TRUE_CONFLICT = pd.DataFrame({
    "基金代码": ["000006", "000007"],
    "基金简称": ["测试多元FOFA", "测试多元FOFC"],
    "基金类型": ["FOF-稳健型", "FOF-均衡型"],
})


def test_a_blank_sibling_does_not_downgrade_a_known_classification(db_session):
    """一个份额类别没给类型，不等于这只基金没有类型。

    分类挂在 fund 上而上游按份额类别给值，两者粒度不同。「至多一个非空
    取值」时取那个非空值 —— 把它降级成 UNCLASSIFIED 会把一只本可分组的
    基金踢出全部横截面计算，那是用「不知道」覆盖「知道」。
    """
    _service(db_session, PARTIAL_BLANK).ingest_fund_list()
    rows = _rows(db_session, "测试养老FOF")
    assert len(rows) == 1
    assert rows[0].classification_code == "FOF-稳健型"


def test_two_different_non_empty_types_are_reported_and_nothing_is_written(db_session):
    """两个及以上不同的非空取值 = 冲突：不写、不猜、如实上报。

    与 _ensure_provider_identity 遇到重指派时的处理是同一条原则：绝不静默
    挑一个。挑错的后果是整只基金被排进错误的 Peer Group，而排名看起来
    完全正常。
    """
    result = _service(db_session, TRUE_CONFLICT).ingest_fund_list()
    assert len(result.classification_conflicts) == 1
    conflict = result.classification_conflicts[0]
    assert conflict.product_name == "测试多元FOF"
    assert set(conflict.codes) == {"FOF-稳健型", "FOF-均衡型"}
    assert _rows(db_session, "测试多元FOF") == []


RETYPED = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["债券型-混合二级", "债券型-混合二级"],
})


def test_a_changed_classification_closes_the_old_interval_and_opens_a_new_one(db_session):
    """基金转型会改变分类，回测必须使用【当时的】分类 —— 这正是这张表
    是区间型的理由（D-5 依据 2）。

    什么情况下它会红：实现用 UPDATE 原地改 classification_code。那样
    2026-09-01 的回测会看到 2026-09-10 才发生的转型结果，且没有任何痕迹
    表明它曾经是混合型。
    """
    _service(db_session, SIMPLE).ingest_fund_list()
    _service(db_session, RETYPED, now=LATER).ingest_fund_list()

    rows = _rows(db_session, "测试蓝筹混合")
    assert len(rows) == 2
    assert rows[0].classification_code == "混合型-偏股"
    assert rows[0].valid_from == FIXED_NOW.date()
    assert rows[0].valid_to == LATER.date()
    assert rows[1].classification_code == "债券型-混合二级"
    assert rows[1].valid_from == LATER.date()
    assert rows[1].valid_to is None


def test_a_same_day_correction_does_not_create_a_zero_length_interval(db_session):
    """同日改口不得产生 valid_from == valid_to 的空区间。

    ck_fund_classification_history_interval 要求 valid_from < valid_to，
    因此「关旧开新」在同一天会被数据库直接拒收。同日改口按【原地更正】
    处理：该行的 available_at 就是今天，没有任何更早的决策可能看见过它，
    因此不存在被改写的历史。
    """
    _service(db_session, SIMPLE).ingest_fund_list()
    _service(db_session, RETYPED).ingest_fund_list()   # 同一个 FIXED_NOW

    rows = _rows(db_session, "测试蓝筹混合")
    assert len(rows) == 1
    assert rows[0].classification_code == "债券型-混合二级"
    assert rows[0].valid_to is None


_DUPLICATE_OPEN = text("""
    INSERT INTO fund.fund_classification_history
        (fund_id, classification_scheme, classification_code,
         valid_from, valid_to, available_at, availability_quality,
         published_at, provider_available_at, ingested_at)
    VALUES (:fund_id, :scheme, :code, :valid_from, NULL,
            :available_at, 'INFERRED', NULL, NULL, :available_at)
""")


def test_database_rejects_a_second_open_interval_for_the_same_fund(db_session):
    """数据库不变式：每个 (fund_id, scheme) 至多一条开放区间。

    应用层的 read-then-write 守卫不是数据库不变式：它拦不住并发，也拦不住
    任何绕开 IngestService 的写入路径。两条开放区间共存时，读侧的
    `ORDER BY valid_from DESC LIMIT 1` 会静默挑一条 —— 挑错就是把基金
    排进错误的 Peer Group（与 uq_pfi_open_interval 同一条理由）。
    """
    from sqlalchemy.exc import IntegrityError

    _service(db_session, SIMPLE).ingest_fund_list()
    fund = db_session.query(Fund).filter_by(product_name="测试蓝筹混合").one()
    with pytest.raises(IntegrityError):
        db_session.execute(_DUPLICATE_OPEN, {
            "fund_id": fund.id, "scheme": CLASSIFICATION_SCHEME,
            "code": "股票型", "valid_from": dt.date(2026, 9, 1),
            "available_at": LATER,
        })
        db_session.flush()
```

- [ ] **Step 5: 跑测试确认失败**

Run: `.venv/bin/pytest tests/integration/test_fund_classification_ingest.py -v -m integration`

Expected: 11 条全部 FAIL。典型输出：
`test_classification_is_persisted_with_the_full_original_string ...
sqlalchemy.exc.NoResultFound: No row was found when one was required`
（`fund_classification_history` 里一行都没有 —— `基金类型` 被丢弃）；
`test_database_rejects_a_second_open_interval_for_the_same_fund ...
Failed: DID NOT RAISE <class 'sqlalchemy.exc.IntegrityError'>`
（部分唯一索引尚不存在）。把输出写进报告。

- [ ] **Step 6: 实现（ORM + 迁移 + 灌数）**

`src/fip/services/data_service/models/fund.py` 的 `FundClassificationHistory`
（第 179-195 行）加索引，并补写为什么：

```python
class FundClassificationHistory(Base, IntervalMixin):
    """基金分类的历史 —— 【区间型表】。

    基金转型会改变分类，回测必须使用【当时的】分类，因此不能是一张
    「当前分类」的维度列。scheme 限定的编码（而非固定层级的列）正适合
    层级尚未由投研定案的分类体系：换一套体系是一次数据操作，不是一次
    代码改造（设计定案 D-5）。
    """

    __tablename__ = "fund_classification_history"
    __table_args__ = (
        *interval_temporal_check_constraints("fund_classification_history"),
        interval_check("fund_classification_history"),
        # 部分唯一索引，须与迁移 0016 里的 CREATE UNIQUE INDEX 逐字一致
        # （含 WHERE 子句），否则 autogenerate 会把它当成待删除对象（G-16）。
        # 唯一性键取 (fund_id, classification_scheme) 而不是只取 fund_id：
        # 同一只基金在两套分类体系下各有一条开放区间是合法的（这正是把
        # scheme 做成字段的意义），只有【同一套体系内】才至多一条。
        Index(
            "uq_fch_open_interval",
            "fund_id",
            "classification_scheme",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund.id", ondelete="RESTRICT"), nullable=False
    )
    classification_scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_code: Mapped[str] = mapped_column(String(32), nullable=False)
```

新建 `db/migrations/versions/0016_fund_classification_open_interval.py`：

```python
"""fund_classification_history 补「至多一条开放区间」的部分唯一索引

Plan-2 Task 5。本表在 Plan-1 建出后【从未被写入过】（fip_dev 实测 0 行），
Plan-2 的分类灌入是它的第一个写入方 —— Plan-1 交接项四「趁表还空着就做」
指的正是这个时刻：加约束的迁移在空表上很便宜，有数据之后成本高一个量级。

唯一性键是 (fund_id, classification_scheme) 而不是只有 fund_id：同一只基金
在两套分类体系下各有一条开放区间是合法的。这一条【必须逐表判断】，不可
一刀切照抄 provider_fund_identity（交接项四原文）。

本迁移只加索引，不动任何列、不动任何数据（C-12）。

Revision ID: 0016
Revises: 0015
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_fch_open_interval "
        "ON fund.fund_classification_history (fund_id, classification_scheme) "
        "WHERE valid_to IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX fund.uq_fch_open_interval")
```

> ⚠️ **编号占用**：实现计划的 File Structure 把 0016 分配给 `factor` schema、
> 0017 分配给 `evaluation` schema。本任务先落地，因此 Task 7 / Task 8 的迁移
> 顺延为 **0017 / 0018**。这一条必须在合并本任务时同步改进计划正文，
> 否则两个任务会同时写 0016 并在 `down_revision` 上分叉。

`src/fip/services/data_service/ingest.py` —— 新增冲突记录类型并扩展结果：

```python
@dataclass(frozen=True)
class ClassificationConflict:
    """同一产品主干下，各份额类别给出了两个及以上【不同的非空】基金类型。

    分类挂在 fund 上，而上游按份额类别给值 —— 两者粒度不同，实测全市场
    15350 个产品主干中有 4 个命中（如「兴全盈禧多元配置三个月持有混合(FOF)」
    A=FOF-稳健型、C=FOF-均衡型）。不是理论情形。

    与 IdentityReassignment 同一条原则：绝不静默挑一个。挑错的后果是整只
    基金被排进错误的 Peer Group，而排名看起来完全正常。
    """

    product_name: str
    codes: tuple[str, ...]

    def describe(self) -> str:
        return f"产品「{self.product_name}」的份额类别给出了不同的基金类型：{list(self.codes)}"


@dataclass(frozen=True)
class FundListIngestResult:
    created: int
    reassignments: tuple[IdentityReassignment, ...]
    classification_conflicts: tuple[ClassificationConflict, ...] = ()
```

`ingest_fund_list` 的循环体内累积、循环后统一写入：

```python
        provider = self._provider()
        created = 0
        reassignments: list[IdentityReassignment] = []
        # fund_id -> 该产品全部份额类别给出的【归一后】code 集合。
        # 必须在循环【之后】才写分类：分类挂在 fund 上而上游按份额类别给值，
        # 边循环边写会让「最后一条份额类别」静默决定整只基金的分类。
        observed: dict[int, set[str]] = {}
        names: dict[int, str] = {}
        for _, row in frame.iterrows():
            code = str(row["基金代码"]).strip()
            display_name = str(row["基金简称"]).strip()
            grouping = split_share_class_name(display_name)
            ...                     # Fund / FundShareClass 的既有逻辑不动
            observed.setdefault(fund.id, set()).add(
                normalize_classification_code(row.get("基金类型"))
            )
            names[fund.id] = grouping.product_name
            ...                     # _ensure_provider_identity 的既有逻辑不动

        conflicts = self._write_classifications(observed, names, record.ingested_at)
        return FundListIngestResult(
            created=created,
            reassignments=tuple(reassignments),
            classification_conflicts=tuple(conflicts),
        )
```

```python
    def _write_classifications(
        self,
        observed: dict[int, set[str]],
        names: dict[int, str],
        ingested_at: dt.datetime,
    ) -> list[ClassificationConflict]:
        """把本批观测到的基金类型落到 fund.fund_classification_history。

        ── 归并规则（D-6 的落地）──

        · 恰好一个非空取值 → 用它。一个份额类别没给类型，不等于这只基金
          没有类型；把它降级成 UNCLASSIFIED 是用「不知道」覆盖「知道」，
          会把一只本可分组的基金踢出全部横截面计算。
        · 全部为空       → UNCLASSIFIED。如实落库，不丢弃、不猜测。
        · 两个及以上不同的非空取值 → 冲突：【不写】，如实上报，由人裁定。

        ── 区间维护 ──

        · 无开放区间           → 新开一条，valid_from = 落库当日。
        · 开放区间的 code 未变 → 什么都不做（幂等）。
        · 开放区间的 code 变了：
            - 该区间的 valid_from < 今天 → 关旧（valid_to = 今天）、开新。
              基金转型会改变分类，回测必须使用当时的分类；原地 UPDATE 会让
              转型前的历史凭空消失。
            - 该区间的 valid_from == 今天 → 【原地更正】。关旧开新会产生
              valid_from == valid_to 的空区间，被 ck_*_interval 直接拒收；
              而这一行的 available_at 就是今天，没有任何更早的决策可能看见过
              它，因此不存在被改写的历史。
        """
        conflicts: list[ClassificationConflict] = []
        today = ingested_at.astimezone(dt.UTC).date()
        available_at, quality = resolve_availability(None, None, ingested_at)
        for fund_id, codes in observed.items():
            concrete = sorted(c for c in codes if c != UNCLASSIFIED_CODE)
            if len(concrete) > 1:
                conflicts.append(ClassificationConflict(
                    product_name=names[fund_id], codes=tuple(concrete)
                ))
                continue
            code = concrete[0] if concrete else UNCLASSIFIED_CODE

            existing = self._session.execute(
                select(FundClassificationHistory).where(
                    FundClassificationHistory.fund_id == fund_id,
                    FundClassificationHistory.classification_scheme
                    == CLASSIFICATION_SCHEME,
                    FundClassificationHistory.valid_to.is_(None),
                )
            ).scalars().first()

            if existing is not None:
                if existing.classification_code == code:
                    continue
                if existing.valid_from >= today:
                    existing.classification_code = code
                    existing.available_at = available_at
                    existing.ingested_at = ingested_at
                    self._session.flush()
                    continue
                existing.valid_to = today
                self._session.flush()

            self._session.add(FundClassificationHistory(
                fund_id=fund_id,
                classification_scheme=CLASSIFICATION_SCHEME,
                classification_code=code,
                valid_from=today,
                valid_to=None,
                available_at=available_at,
                availability_quality=quality.value,
                published_at=None,           # AKShare 给不出，如实留空（C-12）
                provider_available_at=None,  # 同上
                ingested_at=ingested_at,
            ))
            self._session.flush()
        return conflicts
```

顶部 import 追加：

```python
from fip.libs.strategy_library.peer_group.classification import (
    CLASSIFICATION_SCHEME,
    UNCLASSIFIED_CODE,
    normalize_classification_code,
)
from fip.services.data_service.models.fund import FundClassificationHistory
```

`src/fip/platform/cli.py` 的 `cmd_ingest_funds`（第 124-142 行）—— 冲突同样
以非零退出码响亮失败，与重指派并列：

```python
    problems: list[str] = []
    if result.reassignments:
        problems.append(
            f"检测到 {len(result.reassignments)} 处 provider 映射重指派，"
            "这些映射【未被改动】：\n"
            + "\n".join(f"  · {c.describe()}" for c in result.reassignments)
            + "\n请人工确认每一条历史的归属、关闭旧区间后再重跑。"
        )
    if result.classification_conflicts:
        problems.append(
            f"检测到 {len(result.classification_conflicts)} 处基金分类冲突，"
            "这些基金【未写入】任何分类，因而不会进入任何 Peer Group：\n"
            + "\n".join(
                f"  · {c.describe()}" for c in result.classification_conflicts
            )
            + "\n请人工裁定该产品的分类归属（不得由代码任选一个）。"
        )
    if problems:
        raise SystemExit("\n\n".join(problems))
```

- [ ] **Step 7: 跑测试确认通过**

Run: `.venv/bin/alembic -x db=test upgrade head`
Run: `.venv/bin/pytest tests/unit/test_classification_codes.py -v`
Run: `.venv/bin/pytest tests/integration/test_fund_classification_ingest.py -v -m integration`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

G-16 的闸门（autogenerate 必须报告零操作 —— 手工执行，CI 不跑）：

```bash
.venv/bin/python - <<'PY'
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
import db.migrations.env  # noqa: F401 —— 触发全部 model 模块的注册
from fip.platform.db.base import Base
from fip.settings import settings

engine = create_engine(settings.test_database_url, future=True)
with engine.connect() as conn:
    ctx = MigrationContext.configure(
        conn, opts={"include_object": db.migrations.env.include_object}
    )
    diff = compare_metadata(ctx, Base.metadata)
print("autogenerate 差异条数:", len(diff))
for d in diff:
    print(" ", d)
assert not diff, "ORM 声明与迁移产出不一致（G-16）"
PY
```

Expected: `autogenerate 差异条数: 0`。

G-17 的闸门（CHECK 黄金快照）：本任务只加索引、不改任何 CHECK，
`check_constraints.snapshot` 应当**不变**。

Run: `.venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot -v`
Expected: PASS，且 `git status` 显示 `check_constraints.snapshot` 未被修改。

- [ ] **Step 8: 提交**

```bash
git add src/fip/libs/strategy_library/peer_group/classification.py \
        db/migrations/versions/0016_fund_classification_open_interval.py \
        tests/unit/test_classification_codes.py \
        tests/integration/test_fund_classification_ingest.py
git commit --only \
  src/fip/libs/strategy_library/peer_group/classification.py \
  db/migrations/versions/0016_fund_classification_open_interval.py \
  src/fip/services/data_service/models/fund.py \
  src/fip/services/data_service/ingest.py \
  src/fip/platform/cli.py \
  tests/unit/test_classification_codes.py \
  tests/integration/test_fund_classification_ingest.py \
  -m "feat(classification): 灌入 AKShare 基金类型，解开 BLOCK-1

D-5 / D-6（均为【补齐】）：ingest_fund_list 此前读了 \`基金类型\` 却丢弃 ——
与 Task 19 修掉的『code 被丢弃』同一个模式。现写入 Plan-1 已建好的区间型表
fund.fund_classification_history，scheme = AKSHARE_FUND_TYPE，code 存完整原串
（L2）；L1 由 code.split('-')[0] 在 strategy_library 侧派生，【不另存列】。

空 \`基金类型\`（实测 99 只）映射为 UNCLASSIFIED，如实落库但 is_groupable()
恒 False —— 它不是一个类别，是『我们不知道它属于哪个类别』。

分类挂在 fund 上而上游按份额类别给值。实测 15350 个产品主干中有 4 个的份额
类别给出了不同类型。归并规则：恰好一个非空取值则取它（一个份额类别没给
类型不等于这只基金没有类型）；全空则 UNCLASSIFIED；两个及以上不同的非空
取值则【不写】并如实上报，由人裁定 —— 与遇到 provider 重指派时同一条原则。

迁移 0016 趁表还空着（fip_dev 实测 0 行）补上 uq_fch_open_interval：
(fund_id, classification_scheme) 至多一条开放区间。唯一性键带 scheme ——
同一只基金在两套体系下各有一条开放区间是合法的（交接项四要求逐表判断）。
⚠️ 0016 被本任务占用，factor / evaluation schema 的迁移顺延为 0017 / 0018。"
```

---

### Task 6: 批量灌数（D-2）—— ≥300 个份额类别，`AdjustedNavUnavailable` 保护下沉到 service

**Files:**
- Modify: `src/fip/services/data_service/ingest.py:424-425`
  （`rebuild_adjusted_nav` 之后新增单只与批量两个方法）
- Modify: `src/fip/platform/cli.py:145-166`（`cmd_ingest_nav` 改用 service 的单只方法）
- Modify: `src/fip/platform/cli.py:215-236`（新增 `ingest-nav-batch` 子命令）
- Test: `tests/integration/test_batch_ingest.py`（新建）
- Test: `tests/fitness/test_architecture.py`（新增一条：CLI 不得再自己捕获 `AdjustedNavUnavailable`）

**Interfaces:**
- Consumes（Task 5 产出）：`fund.provider_fund_identity` 已由 `ingest-funds` 登记
  ≥300 条开放区间；`FundListIngestResult.classification_conflicts`
- Produces（Task 9 / 11 / 13 的数据前提）：
  - `fip.services.data_service.ingest.ShareClassIngestStatus`（StrEnum：
    `INGESTED` / `ADJUSTED_NAV_UNAVAILABLE` / `FAILED` / `SKIPPED`）
  - `fip.services.data_service.ingest.ShareClassIngestOutcome`（frozen slots dataclass：
    `share_class_id: int`、`provider_fund_id: str`、`status: ShareClassIngestStatus`、
    `nav_rows: int`、`event_rows: int`、`rebuilt_rows: int`、`detail: str`）
  - `fip.services.data_service.ingest.BatchIngestReport`（frozen slots dataclass：
    `outcomes: tuple[ShareClassIngestOutcome, ...]`，方法
    `count(status: ShareClassIngestStatus) -> int`、
    `failures() -> tuple[ShareClassIngestOutcome, ...]`）
  - `IngestService.ingest_share_class(share_class_id: int, provider_fund_id: str,
    decision_at: dt.date) -> ShareClassIngestOutcome`
  - `IngestService.ingest_nav_batch(targets: Sequence[tuple[int, str]],
    decision_at: dt.date, skip_already_ingested: bool = False) -> BatchIngestReport`
  - `fip_dev` 中 `market.fund_nav` 覆盖 **≥ 300** 个不同的 `share_class_id`
    —— IC / ICIR 是横截面统计量，`MIN_PEER_GROUP_SIZE = 30` 在 3 只基金上
    根本达不到（D-2）

---

- [ ] **Step 1: 写失败的测试**

新建 `tests/integration/test_batch_ingest.py`：

```python
"""批量灌数与 AdjustedNavUnavailable 的保护位置（D-2 / Plan-1 交接项三）。

交接项原文：「AdjustedNavUnavailable 只在 CLI 的单只调用点被捕获，
IngestService 自身无保护。Plan-1 没有批处理循环所以不构成缺陷，但 Plan-2
第一次写多只基金的批处理循环就会重新踩到：一只基金复权不可算会中断整个
循环。保护应下沉到 service 层。」
"""

import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import select

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import (
    IngestService,
    ShareClassIngestStatus,
)
from fip.services.data_service.models.fund import FundShareClass, ProviderFundIdentity
from fip.services.data_service.models.market import FundNav

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)
DECISION_AT = dt.date(2026, 8, 31)

FUND_LIST = pd.DataFrame({
    "基金代码": ["000001", "000002", "000003"],
    "基金简称": ["测试甲混合A", "测试乙混合A", "测试丙混合A"],
    "基金类型": ["混合型-偏股", "混合型-偏股", "混合型-偏股"],
})

GOOD_NAV = pd.DataFrame({
    "净值日期": ["2020-01-02", "2020-01-03"],
    "单位净值": ["1.0000", "1.1000"],
})

# 复权不可算：除息金额 >= 除息日净值 → shares 递推的分母非正。
BAD_NAV = pd.DataFrame({
    "净值日期": ["2020-01-02", "2020-01-03"],
    "单位净值": ["1.0000", "0.5000"],
})
BAD_DIVIDEND = pd.DataFrame({
    "年份": ["2020"], "权益登记日": ["2020-01-02"],
    "除息日": ["2020-01-03"], "每10份分红": ["每10份派现金9.0000元"],
})

EMPTY_DIVIDEND = pd.DataFrame({
    "年份": [], "权益登记日": [], "除息日": [], "每10份分红": [],
})
EMPTY_SPLIT = pd.DataFrame({"年份": [], "拆分折算日": [], "拆分折算比例": []})


def _caller_for(bad_symbols: set[str], exploding_symbols: set[str] = frozenset()):
    def caller(name, **params):
        if name == "fund_name_em":
            return FUND_LIST
        symbol = params.get("symbol", "")
        if symbol in exploding_symbols:
            raise RuntimeError(f"上游炸了：{symbol}")
        indicator = params.get("indicator")
        bad = symbol in bad_symbols
        if indicator == "单位净值走势":
            return BAD_NAV if bad else GOOD_NAV
        if indicator == "分红送配详情":
            return BAD_DIVIDEND if bad else EMPTY_DIVIDEND
        if indicator == "拆分详情":
            return EMPTY_SPLIT
        raise AssertionError(f"未预期的调用 {name} {params}")
    return caller


def _service(session, caller) -> IngestService:
    return IngestService(
        session,
        AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=caller),
        disclosure_lag_days=1,
    )


@pytest.fixture()
def targets(db_session) -> list[tuple[int, str]]:
    _service(db_session, _caller_for(set())).ingest_fund_list()
    rows = db_session.execute(
        select(ProviderFundIdentity.share_class_id, ProviderFundIdentity.provider_fund_id)
        .where(ProviderFundIdentity.valid_to.is_(None))
        .order_by(ProviderFundIdentity.provider_fund_id)
    ).all()
    return [(r[0], r[1]) for r in rows]


def _nav_count(session, share_class_id: int) -> int:
    return (
        session.query(FundNav).filter_by(share_class_id=share_class_id).count()
    )


def test_one_unadjustable_fund_does_not_abort_the_batch(db_session, targets):
    """一只基金复权不可算，其余两只必须照常灌完。

    什么情况下它会红：保护留在 CLI 而 service 直接把
    AdjustedNavUnavailable 抛出循环 —— 那正是 Plan-1 结束时的状态。
    """
    service = _service(db_session, _caller_for({"000002"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    assert len(report.outcomes) == 3
    assert report.count(ShareClassIngestStatus.INGESTED) == 2
    assert report.count(ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE) == 1


def test_navs_of_the_unadjustable_fund_are_kept_not_discarded(db_session, targets):
    """净值与事件已成功灌入，不得因复权回填失败而把它们一并丢弃。

    复权是【读路径现算】的，物化列只是运维值；净值行本身完全有效。
    丢弃它们等于让一次回填失败抹掉真实的市场数据。
    """
    service = _service(db_session, _caller_for({"000002"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    bad = next(
        o for o in report.outcomes
        if o.status is ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE
    )
    assert bad.nav_rows == 2
    assert bad.rebuilt_rows == 0
    assert _nav_count(db_session, bad.share_class_id) == 2


def test_an_upstream_exception_is_isolated_to_one_share_class(db_session, targets):
    """网络/上游异常同样不得中断整批 —— 但必须逐只如实上报，不得吞掉。"""
    service = _service(db_session, _caller_for(set(), exploding_symbols={"000003"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    assert report.count(ShareClassIngestStatus.INGESTED) == 2
    failures = report.failures()
    assert len(failures) == 1
    assert failures[0].provider_fund_id == "000003"
    assert "上游炸了" in failures[0].detail


def test_the_session_is_usable_after_a_failure(db_session, targets):
    """失败后必须 rollback，否则后续每一只都会撞上
    PendingRollbackError —— 「一只失败不中断整批」会退化成
    「第一只失败之后全部失败」，而报告里看起来是 N-1 个独立故障。
    """
    service = _service(db_session, _caller_for(set(), exploding_symbols={"000001"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    assert report.count(ShareClassIngestStatus.FAILED) == 1
    assert report.count(ShareClassIngestStatus.INGESTED) == 2
    survivors = [
        o for o in report.outcomes if o.status is ShareClassIngestStatus.INGESTED
    ]
    for outcome in survivors:
        assert _nav_count(db_session, outcome.share_class_id) == 2


def test_every_target_gets_exactly_one_outcome_row(db_session, targets):
    """报告必须逐只 —— 只给「成功 N 只 / 失败 M 只」的汇总，
    运维就无法知道该重跑哪几只。
    """
    service = _service(db_session, _caller_for({"000002"}, {"000003"}))
    report = service.ingest_nav_batch(targets, decision_at=DECISION_AT)

    reported = {(o.share_class_id, o.provider_fund_id) for o in report.outcomes}
    assert reported == set(targets)
    assert {o.status for o in report.outcomes} == {
        ShareClassIngestStatus.INGESTED,
        ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE,
        ShareClassIngestStatus.FAILED,
    }


def test_resume_skips_share_classes_that_already_have_navs(db_session, targets):
    """断点续灌：已有净值的份额类别直接跳过，不再打一次上游。

    判据取【数据库里的真实状态】而不是一个游标文件：进度文件与数据库
    分叉时无法判定谁对，而『这只已经有净值行了』是可以直接观测的事实。
    """
    service = _service(db_session, _caller_for(set()))
    first = service.ingest_nav_batch(targets[:1], decision_at=DECISION_AT)
    assert first.count(ShareClassIngestStatus.INGESTED) == 1

    second = service.ingest_nav_batch(
        targets, decision_at=DECISION_AT, skip_already_ingested=True
    )
    assert second.count(ShareClassIngestStatus.SKIPPED) == 1
    assert second.count(ShareClassIngestStatus.INGESTED) == 2
    skipped = next(
        o for o in second.outcomes if o.status is ShareClassIngestStatus.SKIPPED
    )
    assert skipped.share_class_id == targets[0][0]


def test_resume_is_off_by_default(db_session, targets):
    """默认【不跳过】：日常增量灌数要的是重跑同一只以取回新净值。

    把续灌做成默认行为会让「每天跑一次」变成「只灌第一天」，且没有任何
    错误信号。
    """
    service = _service(db_session, _caller_for(set()))
    service.ingest_nav_batch(targets[:1], decision_at=DECISION_AT)
    again = service.ingest_nav_batch(targets[:1], decision_at=DECISION_AT)
    assert again.count(ShareClassIngestStatus.SKIPPED) == 0
    assert again.count(ShareClassIngestStatus.INGESTED) == 1


def test_single_share_class_entry_point_never_raises_adjusted_nav_unavailable(
    db_session, targets
):
    """保护【在 service 层】：单只入口自己就不会把该异常抛出去。

    什么情况下它会红：有人把 try/except 又搬回 CLI —— 那样任何绕过 CLI 的
    调用方（批处理、未来的 job worker）都会重新踩到同一个坑。
    """
    service = _service(db_session, _caller_for({"000002"}))
    share_class_id, symbol = next(t for t in targets if t[1] == "000002")
    outcome = service.ingest_share_class(share_class_id, symbol, DECISION_AT)
    assert outcome.status is ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE
    assert outcome.detail


EMPTY_NAV = pd.DataFrame({"净值日期": [], "单位净值": []})


def _empty_caller(name, **params):
    """上游对该基金一行净值都没有：列结构合法、行数为 0。

    刻意给出【有列名的空表】而不是 pd.DataFrame()：后者是 AKShare 对
    「无此类记录」的另一种表达（0 行 0 列），会被 _assert_columns 原样放行，
    但 parse_nav_frame 拿到它时行为不确定。这条测试要验的是「合法但空」，
    不是「无 schema」。
    """
    if name == "fund_name_em":
        return FUND_LIST
    indicator = params.get("indicator")
    if indicator == "单位净值走势":
        return EMPTY_NAV
    if indicator == "分红送配详情":
        return EMPTY_DIVIDEND
    if indicator == "拆分详情":
        return EMPTY_SPLIT
    raise AssertionError(f"未预期的调用 {name} {params}")


def test_zero_nav_rows_is_reported_as_zero_not_hidden(db_session):
    """上游一行净值都没有时，报告里必须看得出是 0 行。

    状态仍是 INGESTED（这一只确实跑完了、没有出错），但 nav_rows == 0 与
    「灌了 2 行」必须可区分 —— 只看状态的话运维会以为覆盖已经完成，而
    这只基金在后续的横截面计算里会一直缺席且没有任何线索。
    """
    service = _service(db_session, _empty_caller)
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).order_by(FundShareClass.id).first()
    outcome = service.ingest_share_class(sc.id, "000001", DECISION_AT)
    assert outcome.nav_rows == 0
    assert outcome.rebuilt_rows == 0
    assert outcome.status is ShareClassIngestStatus.INGESTED
    assert "0 行" in outcome.detail
```

同时在 `tests/fitness/test_architecture.py` 末尾追加一条，防止保护被搬回 CLI：

```python
CLI_PY = SRC / "platform" / "cli.py"


def test_cli_does_not_own_the_adjusted_nav_unavailable_guard():
    """D-2 / 交接项三：保护必须在 service 层，不得在 CLI 再包一层。

    CLI 只是众多调用方之一。把 try/except AdjustedNavUnavailable 放在这里，
    等于让每一个未来的调用方（批处理循环、job worker、API handler）各自
    重新发现同一个坑 —— Plan-1 交接项明确警告『第一次写批处理循环就会
    重新踩到』。

    什么情况下它会红：有人在 cli.py 里写下 `except AdjustedNavUnavailable`。
    """
    tree = ast.parse(CLI_PY.read_text(encoding="utf-8"), filename=str(CLI_PY))
    caught = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            for sub in ast.walk(node.type):
                if isinstance(sub, ast.Name):
                    caught.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    caught.add(sub.attr)
    assert "AdjustedNavUnavailable" not in caught, (
        "cli.py 又开始自己捕获 AdjustedNavUnavailable；该保护属 IngestService"
    )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/integration/test_batch_ingest.py -v -m integration`
Expected: 全部 FAIL —— `ImportError: cannot import name 'ShareClassIngestStatus'
from 'fip.services.data_service.ingest'`。

Run: `.venv/bin/pytest tests/fitness/test_architecture.py -k adjusted_nav_unavailable -v`
Expected: FAIL with
`AssertionError: cli.py 又开始自己捕获 AdjustedNavUnavailable；该保护属 IngestService`
—— 这正是 Plan-1 结束时的状态（`cli.py:156` 与 `cli.py:195` 各一处）。

- [ ] **Step 3: 最小实现**

`src/fip/services/data_service/ingest.py` —— 顶部 import 补
`from enum import StrEnum` 与
`from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable`，
并新增：

```python
class ShareClassIngestStatus(StrEnum):
    INGESTED = "INGESTED"
    ADJUSTED_NAV_UNAVAILABLE = "ADJUSTED_NAV_UNAVAILABLE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class ShareClassIngestOutcome:
    """一只份额类别的灌数结果。逐只如实记录，不做汇总。

    ADJUSTED_NAV_UNAVAILABLE 与 FAILED 【必须】是两个状态而不是一个：
    前者是「净值与事件都灌进去了，只是这只基金的复权链路算不出来」——
    数据是好的，物化列留 NULL，读路径照样能现算它可算的部分；
    后者是「这一只整个没灌成」。把两者合并会让运维分不清该重跑哪些。
    """

    share_class_id: int
    provider_fund_id: str
    status: ShareClassIngestStatus
    nav_rows: int
    event_rows: int
    rebuilt_rows: int
    detail: str


@dataclass(frozen=True, slots=True)
class BatchIngestReport:
    outcomes: tuple[ShareClassIngestOutcome, ...]

    def count(self, status: ShareClassIngestStatus) -> int:
        return sum(1 for o in self.outcomes if o.status is status)

    def failures(self) -> tuple[ShareClassIngestOutcome, ...]:
        return tuple(
            o for o in self.outcomes if o.status is ShareClassIngestStatus.FAILED
        )
```

`IngestService` 内新增两个方法（接在 `rebuild_adjusted_nav` 之后）：

```python
    def ingest_share_class(
        self, share_class_id: int, provider_fund_id: str, decision_at: dt.date
    ) -> ShareClassIngestOutcome:
        """灌一只份额类别的净值 + 事件 + 复权回填，返回如实的结果。

        ── AdjustedNavUnavailable 的保护在这里，不在 CLI（交接项三）──

        Plan-1 只在 cmd_ingest_nav 的单只调用点捕获它，IngestService 自身
        无保护。CLI 只是众多调用方之一：批处理循环、未来的 job worker、
        API handler 都会重新踩到同一个坑，而后果是「一只基金复权不可算
        中断整个循环」。保护属于这一层。

        捕获【只覆盖复权回填】，不覆盖净值与事件的灌入：后者失败是真正的
        失败，必须抛给调用方。复权回填失败则不同 —— 净值行本身完全有效，
        复权值由读路径按 decision_at 现算（物化列只是运维值），因此这里
        如实记录并继续，【不】回滚已灌入的净值（C-6 禁止的是填 0 / 沿用
        上期，不是禁止保留真实的市场数据）。
        """
        navs = self.ingest_nav(share_class_id, provider_fund_id)
        events = self.ingest_distributions(share_class_id, provider_fund_id)
        try:
            rebuilt = self.rebuild_adjusted_nav(share_class_id, decision_at)
        except AdjustedNavUnavailable as exc:
            return ShareClassIngestOutcome(
                share_class_id=share_class_id,
                provider_fund_id=provider_fund_id,
                status=ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE,
                nav_rows=navs,
                event_rows=events,
                rebuilt_rows=0,
                detail=(
                    f"净值 {navs} 行、事件 {events} 行已灌入；"
                    f"复权回填跳过：{exc}。该份额类别的 adjusted_nav 物化列"
                    "保持 NULL，读路径仍按 decision_at 现算"
                ),
            )
        return ShareClassIngestOutcome(
            share_class_id=share_class_id,
            provider_fund_id=provider_fund_id,
            status=ShareClassIngestStatus.INGESTED,
            nav_rows=navs,
            event_rows=events,
            rebuilt_rows=rebuilt,
            detail=f"净值 {navs} 行、事件 {events} 行、复权回填 {rebuilt} 行",
        )

    def _has_navs(self, share_class_id: int) -> bool:
        return self._session.execute(
            select(func.count()).select_from(FundNav).where(
                FundNav.share_class_id == share_class_id
            )
        ).scalar_one() > 0

    def ingest_nav_batch(
        self,
        targets: Sequence[tuple[int, str]],
        decision_at: dt.date,
        skip_already_ingested: bool = False,
    ) -> BatchIngestReport:
        """按 (share_class_id, provider_fund_id) 逐只灌数。

        ── 三条硬性质（D-2）──

        1. **一只失败不得中断整批**：捕获 Exception（不含 BaseException，
           因此 KeyboardInterrupt / SystemExit 照常穿出 —— 运维按 Ctrl-C
           必须真的能停下）。
        2. **逐只报告成败**：每个 target 恰好产出一条 outcome。只给汇总数字
           会让运维无法知道该重跑哪几只。
        3. **断点续灌**：skip_already_ingested=True 时跳过已有净值行的份额
           类别。判据取数据库里的真实状态而不是一个进度文件 —— 进度文件与
           数据库分叉时无法判定谁对。默认为 False，因为日常增量灌数要的
           恰恰是重跑同一只以取回新净值。

        ── 为什么在这一层 commit ──

        本方法【逐只提交】。这是本仓库第一处在 service 层提交的地方，是
        刻意的：断点续灌要求「已灌完的那些必须真的落库」，而单一大事务下
        第 287 只失败会让前 286 只一起回滚 —— 那样「断点」根本不存在。
        每只失败后必须 rollback，否则后续每一只都会撞上 PendingRollbackError，
        「一只失败不中断整批」会退化成「第一只失败之后全部失败」。
        """
        outcomes: list[ShareClassIngestOutcome] = []
        for share_class_id, provider_fund_id in targets:
            if skip_already_ingested and self._has_navs(share_class_id):
                outcomes.append(ShareClassIngestOutcome(
                    share_class_id=share_class_id,
                    provider_fund_id=provider_fund_id,
                    status=ShareClassIngestStatus.SKIPPED,
                    nav_rows=0, event_rows=0, rebuilt_rows=0,
                    detail="已有净值行，断点续灌跳过",
                ))
                continue
            try:
                outcome = self.ingest_share_class(
                    share_class_id, provider_fund_id, decision_at
                )
                self._session.commit()
            except Exception as exc:  # noqa: BLE001 —— 见方法 docstring 第 1 条
                self._session.rollback()
                outcome = ShareClassIngestOutcome(
                    share_class_id=share_class_id,
                    provider_fund_id=provider_fund_id,
                    status=ShareClassIngestStatus.FAILED,
                    nav_rows=0, event_rows=0, rebuilt_rows=0,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            outcomes.append(outcome)
        return BatchIngestReport(outcomes=tuple(outcomes))
```

顶部 import 追加 `from collections.abc import Sequence`。

`src/fip/platform/cli.py` —— `cmd_ingest_nav`（第 145-166 行）改为调用 service，
CLI 里不再出现任何 `except AdjustedNavUnavailable`：

```python
def cmd_ingest_nav(args: argparse.Namespace) -> None:
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        outcome = _service(session).ingest_share_class(
            share_class.id, args.symbol, dt.date.today()
        )
        session.commit()
    print(f"{share_class.display_name}：{outcome.status} —— {outcome.detail}")
```

新增批量子命令与它的 handler：

```python
def cmd_ingest_nav_batch(args: argparse.Namespace) -> None:
    """批量灌入净值。ingest_nav_batch 自己逐只提交，这里不再包事务。"""
    # 延迟 import：见文件顶部说明。
    from fip.services.data_service.ingest import ShareClassIngestStatus
    from fip.services.data_service.models.fund import ProviderFundIdentity
    from fip.services.data_service.models.governance import DataProvider
    from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter

    with _session() as session:
        rows = session.execute(
            select(
                ProviderFundIdentity.share_class_id,
                ProviderFundIdentity.provider_fund_id,
            )
            .join(DataProvider, DataProvider.id == ProviderFundIdentity.provider_id)
            .where(
                DataProvider.provider_code == AkShareSourceAdapter.provider_code,
                ProviderFundIdentity.valid_to.is_(None),
            )
            .order_by(ProviderFundIdentity.provider_fund_id)
            .limit(args.limit)
        ).all()
        targets = [(r[0], r[1]) for r in rows]
        report = _service(session).ingest_nav_batch(
            targets, dt.date.today(), skip_already_ingested=args.resume
        )

    for outcome in report.outcomes:
        print(f"{outcome.provider_fund_id}\t{outcome.status}\t{outcome.detail}")
    print(
        f"共 {len(report.outcomes)} 只："
        f"成功 {report.count(ShareClassIngestStatus.INGESTED)}、"
        f"复权不可算 {report.count(ShareClassIngestStatus.ADJUSTED_NAV_UNAVAILABLE)}、"
        f"跳过 {report.count(ShareClassIngestStatus.SKIPPED)}、"
        f"失败 {report.count(ShareClassIngestStatus.FAILED)}"
    )
    if report.failures():
        # 响亮失败：已灌入的部分照常保留（逐只提交），但退出码非零，
        # 否则批处理脚本会以为整批都成功了。
        raise SystemExit(
            f"{len(report.failures())} 只失败，可加 --resume 重跑（已成功的会被跳过）"
        )
```

`main()` 里注册：

```python
    p_batch = sub.add_parser(
        "ingest-nav-batch", help="批量灌入净值与事件（逐只提交，可断点续灌）"
    )
    p_batch.add_argument("--limit", type=int, default=None)
    p_batch.add_argument(
        "--resume", action="store_true",
        help="跳过已有净值行的份额类别（断点续灌）；默认不跳过，用于日常增量",
    )
    p_batch.set_defaults(func=cmd_ingest_nav_batch)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/integration/test_batch_ingest.py -v -m integration`
Run: `.venv/bin/pytest tests/fitness/test_architecture.py -k adjusted_nav_unavailable -v`
Run: `.venv/bin/pytest tests/unit tests/fitness tests/integration -q`
Run: `make typecheck && .venv/bin/ruff check src tests`

Expected: 新增 10 条全绿。注意 `tests/integration/test_cli.py` 里断言
`cmd_ingest_nav` 输出文本的用例需要同步改成新的一行格式 —— 那是本任务
【预期内】的改动，不得为了让旧断言通过而保留 CLI 里的 try/except。

- [ ] **Step 5: 真实灌数（D-2 的验收，对 `fip_dev` 执行）**

净值/分红/拆分三个数据集各要打一次上游，约 300 只 ≈ 900 次请求，
实测节奏下需要 30~60 分钟。必须放后台跑，不要在前台阻塞：

```bash
.venv/bin/fip ingest-funds --limit 400 2>&1 | tail -20
nohup .venv/bin/fip ingest-nav-batch --limit 400 --resume \
  > /tmp/fip-batch.log 2>&1 &
```

中途或结束后查看进度与逐只结果：

```bash
tail -5 /tmp/fip-batch.log
grep -c INGESTED /tmp/fip-batch.log
grep -E "FAILED|ADJUSTED_NAV_UNAVAILABLE" /tmp/fip-batch.log
```

中断后直接重跑同一条命令即可（`--resume` 跳过已灌完的）。

- [ ] **Step 6: 验收 ≥300 个份额类别（D-2 的硬指标）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings
e = create_engine(settings.database_url, future=True)
with e.connect() as c:
    covered = c.execute(text(
        "SELECT count(DISTINCT share_class_id) FROM market.fund_nav")).scalar()
    rows = c.execute(text("SELECT count(*) FROM market.fund_nav")).scalar()
    classified = c.execute(text("""
        SELECT count(*) FROM fund.fund_classification_history
        WHERE valid_to IS NULL AND classification_code <> 'UNCLASSIFIED'""")).scalar()
    groups = c.execute(text("""
        SELECT split_part(classification_code, '-', 1) AS l1, count(*)
        FROM fund.fund_classification_history
        WHERE valid_to IS NULL AND classification_code <> 'UNCLASSIFIED'
        GROUP BY 1 ORDER BY 2 DESC""")).all()
print("覆盖份额类别:", covered, " 净值行:", rows, " 已分类基金:", classified)
print("L1 分组规模:", groups)
assert covered >= 300, f"D-2 要求 >= 300 个份额类别，实得 {covered}"
PY
```

Expected: `覆盖份额类别: >= 300`。同时把 `L1 分组规模` 抄进任务报告 ——
D-7 把 Peer Group 粒度默认定为 L1 的理由正是「L1 分组约 30~100 只才能让
横截面派生量真正产出」，这里是**第一次可以用真实数据检验那条假设**。
若某个 L1 分组不足 `MIN_PEER_GROUP_SIZE = 30`，如实记录，**不要**为了凑数
而扩大 `--limit` 之外的任何东西（G-7 的判定基数是 `n_effective`，不是组规模，
组规模不足本身是一个需要被 Task 11 如实呈现的事实）。

- [ ] **Step 7: 提交**

```bash
git add tests/integration/test_batch_ingest.py
git commit --only \
  src/fip/services/data_service/ingest.py \
  src/fip/platform/cli.py \
  tests/integration/test_batch_ingest.py \
  tests/fitness/test_architecture.py \
  tests/integration/test_cli.py \
  -m "feat(ingest): 批量灌数 + AdjustedNavUnavailable 保护下沉到 service 层

D-2 与 Plan-1 交接项三。交接项原文警告『第一次写多只基金的批处理循环就会
重新踩到』—— 本任务正是那个循环，因此保护必须在这里下沉，而不是在 CLI
再包一层：CLI 只是众多调用方之一，批处理、job worker、API handler 都会
各自重新发现同一个坑。

新增 IngestService.ingest_share_class（单只，自带保护）与 ingest_nav_batch
（逐只提交、逐只报告、一只失败不中断整批）。三个状态刻意分开：
· ADJUSTED_NAV_UNAVAILABLE —— 净值与事件都灌好了，只是复权链路算不出来。
  净值行完全有效（复权由读路径现算），不得因回填失败而丢弃真实市场数据。
· FAILED —— 这一只整个没灌成，已 rollback。
· SKIPPED —— 断点续灌跳过；判据取数据库里的真实状态而不是进度文件。
每只失败后 rollback：否则后续每只都撞 PendingRollbackError，『一只失败不
中断整批』会退化成『第一只失败之后全部失败』。

新增适应度测试：cli.py 里不得再出现 except AdjustedNavUnavailable。
新增 CLI 子命令 ingest-nav-batch --limit/--resume。

实测灌入结果（fip_dev）：把 Step 6 脚本打印的『覆盖份额类别 / 净值行 /
L1 分组规模』三个数字原样抄进本段 —— D-7 把 Peer Group 粒度默认定为 L1
的假设，到这里第一次得到真实数据的检验，数字必须留在提交历史里。"
```

> 提交前先跑一遍 Step 6 的脚本，把它打印的三个数字填进上面这条提交信息的
> 最后一段。**不要**留任何占位符 —— 一条写着「覆盖若干只」的提交信息在
> 半年后与没有这段话等价。
