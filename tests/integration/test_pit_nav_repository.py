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
from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable
from fip.services.data_service.normalization.backfill import backfill_adjusted_nav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-PIT", product_name="PIT 测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="PIT 测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _utc(year, month, day):
    return dt.datetime(year, month, day, tzinfo=dt.UTC)


def _add_nav(session, sc, day, value, version=1, available_at=None):
    session.add(FundNav(
        share_class_id=sc.id, effective_at=day, version=version,
        unit_nav=Decimal(value),
        available_at=available_at or _utc(day.year, day.month, day.day)
        + dt.timedelta(days=1),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))


def _add_dist(session, sc, day, dividend, available_at, split="1", version=1):
    session.add(FundDistribution(
        share_class_id=sc.id, effective_at=day, version=version,
        dividend_per_unit=Decimal(dividend), split_ratio=Decimal(split),
        available_at=available_at, availability_quality="INFERRED",
        published_at=None, provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-PIT", decision_at=decision_at, data_as_of=decision_at,
        strategy_version="sv-1", policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def _series(db_session, sc, decision_at, date_from, date_to):
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to)


_COLUMN_SQL = text("""
    SELECT effective_at, version, adjusted_nav
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id
    ORDER BY effective_at, version
""")


def _column(db_session, sc) -> dict[tuple[dt.date, int], Decimal | None]:
    """直接读 market.fund_nav.adjusted_nav 这个【运维物化列】。

    自 fix round 3 起，PIT 读路径不再读该列（复权净值按 decision_at 现算），
    因此凡是要断言「回填往列里写了什么」的测试，都必须像这样直连该列 ——
    经由 SqlNavPitRepository 断言列内容已经不成立，那条链路上的值来自现算。
    """
    rows = db_session.execute(
        _COLUMN_SQL, {"share_class_id": sc.id}
    ).mappings().all()
    return {(r["effective_at"], r["version"]): r["adjusted_nav"] for r in rows}


def test_materialized_column_matches_recomputed_series_when_aligned(
    db_session, share_class
):
    """一致性对照：对齐不变式成立时，现算结果与物化列【逐点相等】。

    「对齐不变式」= 净值与事件的 available_at 都由同一时滞从 effective_at
    推出，没有迟到披露。此时任何 checkpoint 上可见的事件集合与净值集合是
    配套的，「首个 checkpoint 盖章」写进列里的值恰好等于在最终 decision_at
    现算的值。

    这条测试是保护物化列不悄悄跑偏的网：现算是真值来源，列是排查用的物化
    副本；对齐场景下两者必须一致，一旦分叉就说明其中一条路径出了 bug。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1")
    _add_dist(db_session, share_class, dt.date(2020, 1, 3), "0.1",
              available_at=_utc(2020, 1, 4))
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.0")
    db_session.flush()

    updated = backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    assert updated == 2

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.adjusted_nav for p in points] == [Decimal("1.1"), Decimal("1.1")]

    stored = _column(db_session, share_class)
    for point in points:
        assert point.adjusted_nav == stored[(point.effective_at, point.version)]


def test_data_not_yet_available_is_invisible(db_session, share_class):
    """PIT 的核心断言：决策时点看不见的数据不得参与。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0",
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.5",
             available_at=_utc(2020, 1, 10))  # 迟到的数据
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    early = _series(db_session, share_class, dt.date(2020, 1, 5),
                    dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in early] == [dt.date(2020, 1, 2)]

    later = _series(db_session, share_class, dt.date(2020, 1, 15),
                    dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in later] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_revision_is_resolved_by_decision_time(db_session, share_class):
    """净值修订：决策时点之前看到的是旧版本，之后才是新版本。

    版本解析规则（对每个 effective_at 取 available_at ≤ decision_at 中
    version 最大者）不因改为现算而改变；改变的只是 adjusted_nav 的来源。
    """
    day = dt.date(2020, 1, 2)
    _add_nav(db_session, share_class, day, "1.0", version=1,
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, day, "1.2", version=2,
             available_at=_utc(2020, 2, 1))
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    before = _series(db_session, share_class, dt.date(2020, 1, 10), day, day)
    assert before[0].unit_nav == Decimal("1.0")
    assert before[0].version == 1
    assert before[0].adjusted_nav == Decimal("1.0")

    after = _series(db_session, share_class, dt.date(2020, 3, 1), day, day)
    assert after[0].unit_nav == Decimal("1.2")
    assert after[0].version == 2
    assert after[0].adjusted_nav == Decimal("1.2")


def test_superseded_version_gets_its_own_materialized_value(db_session, share_class):
    """被取代的旧版本不能永远停留在 adjusted_nav = NULL（fix round 1）。

    两个版本都在【同一次】批量回填运行【之前】就已存在——这正是 Task 19
    历史全量回填会遇到的形状：回填只跑一次，但 fund_nav 里已经有多版本。

    断言直接打在物化列上（见 _column 的说明）：这条不变式属于
    backfill_adjusted_nav 的写入行为，而 PIT 读路径已不读该列，经由
    SqlNavPitRepository 断言它会变成一条恒真的假测试。
    """
    day = dt.date(2020, 1, 2)
    _add_nav(db_session, share_class, day, "1.0", version=1,
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, day, "1.2", version=2,
             available_at=_utc(2020, 2, 1))
    db_session.flush()

    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    assert _column(db_session, share_class) == {
        (day, 1): Decimal("1.0"),
        (day, 2): Decimal("1.2"),
    }


def test_series_is_sorted_and_bounded_by_date_range(db_session, share_class):
    for day, value in [(dt.date(2020, 1, 3), "1.1"),
                       (dt.date(2020, 1, 2), "1.0"),
                       (dt.date(2021, 1, 4), "1.3")]:
        _add_nav(db_session, share_class, day, value)
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in points] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_chain_starts_at_inception_not_at_date_from(db_session, share_class):
    """复权是累乘链路：起点被 date_from 截断会让整段序列的绝对水平错掉。

    2020-01-01 的分红落在查询区间【之外】。若实现只取 [date_from, date_to]
    的净值来算，2020-06-01 这一点会算成 1.0（该分红凭空消失）；正确结果是
    1.1 —— 累计份额 1.1 是自成立以来一路乘下来的，区间切片必须发生在
    计算【之后】。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 1), "1.0")
    _add_dist(db_session, share_class, dt.date(2020, 1, 1), "0.1",
              available_at=_utc(2020, 1, 2))
    _add_nav(db_session, share_class, dt.date(2020, 6, 1), "1.0")
    db_session.flush()

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 6, 1), dt.date(2020, 6, 1))
    assert [p.effective_at for p in points] == [dt.date(2020, 6, 1)]
    assert points[0].adjusted_nav == Decimal("1.1")


def test_availability_quality_is_returned(db_session, share_class):
    """调用方必须能判断这段序列的 PIT 可信度。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0")
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert points[0].availability_quality == "INFERRED"


def test_empty_range_returns_empty_list(db_session, share_class):
    assert _series(db_session, share_class, dt.date(2026, 8, 31),
                   dt.date(2020, 1, 1), dt.date(2020, 12, 31)) == []


def _late_event_scenario(db_session, share_class) -> None:
    """迟到事件场景（轮 2 沿用至今）。

    v1(2020-01-02) 从 2020-01-03 起可见，直到 2020-03-01 才被 v2 取代；
    一个 effective_at=2020-01-01 的分红事件迟到，2020-01-15 才披露 ——
    正好落在 v1 的 reign 内。这一个形状同时暴露了标量列两种盖章规则各自的
    毛病，因此前视回归与口径一致性两条测试共用它。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 1), "1.0",
             available_at=_utc(2020, 1, 2))
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1", version=1,
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.2", version=2,
             available_at=_utc(2020, 3, 1))
    _add_dist(db_session, share_class, dt.date(2020, 1, 1), "0.1",
              available_at=_utc(2020, 1, 15))
    db_session.flush()
    # 仍然跑一次回填：现算路径必须与列里存了什么【无关】，跑了回填才能证明
    # 这一点（下面 test_recomputed_series_ignores_stale_materialized_column
    # 直接对比两者）。
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))


def test_late_event_is_invisible_before_it_is_disclosed(db_session, share_class):
    """前视回归（现算版）：decision_at 早于事件披露时，序列不含该事件的影响。

    这是构造性保证而非规则约定：adjusted_nav_series 的两条查询都带
    `available_at <= decision_at`，2020-01-15 才可见的分红根本不可能进入
    compute_adjusted_nav 的输入。含事件的值会是 [1.1, 1.21]。
    """
    _late_event_scenario(db_session, share_class)

    points = _series(db_session, share_class, dt.date(2020, 1, 10),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [(p.effective_at, p.version) for p in points] == [
        (dt.date(2020, 1, 1), 1),
        (dt.date(2020, 1, 2), 1),
    ]
    assert [p.adjusted_nav for p in points] == [Decimal("1.0"), Decimal("1.1")]


def test_series_uses_one_event_set_across_all_points(db_session, share_class):
    """口径一致性：同一次查询里早期点与晚期点用的是【同一套】事件。

    这正是轮 2「首个 checkpoint 盖章」修不掉的缺陷。decision_at=2020-06-01
    时迟到分红早已披露，两个点都应含它：
      · 2020-01-01：shares 1.1 → adj 1.0 × 1.1 = 1.1
      · 2020-01-02(v2)：shares 1.1 → adj 1.2 × 1.1 = 1.32
    轮 2 的列里存的是 [1.0, 1.32]：2020-01-01 行在 2020-01-02 盖章（事件尚未
    披露，不含），2020-01-02 v2 行在 2020-03-01 盖章（事件已披露，含）。
    于是两点之间的复权收益率变成 1.32/1.0 = +32%，而单位净值只涨了
    1.2/1.0 = +20% —— 凭空多出的 10% 就是伪造的收益尖峰。对动量/波动率
    这类因子而言，伪造的尖峰与前视一样是污染。

    因此这里既断言绝对值，也断言「区间内无事件时，复权收益率必须等于单位
    净值收益率」这条不变式 —— 后者才是「无凭空尖峰」的直接表述。
    """
    _late_event_scenario(db_session, share_class)

    points = _series(db_session, share_class, dt.date(2020, 6, 1),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [(p.effective_at, p.version) for p in points] == [
        (dt.date(2020, 1, 1), 1),
        (dt.date(2020, 1, 2), 2),
    ]
    early, late = points
    # 早期点也已含 2020-01-01 的分红（轮 2 在此返回 1.0）。
    assert early.adjusted_nav == Decimal("1.1")
    assert late.adjusted_nav == Decimal("1.32")
    # 两点之间没有任何事件，故复权收益率必须与单位净值收益率相同。
    assert late.adjusted_nav / early.adjusted_nav == late.unit_nav / early.unit_nav


def test_recomputed_series_ignores_stale_materialized_column(db_session, share_class):
    """读路径【不读】物化列：列里存的是过时值，现算结果与它不同。

    这条测试锁死「adjusted_nav 列已降级为运维物化值」这个语义。若日后有人
    把读路径改回逐字读该列（或加一条「算不出来就回退读列」的兜底），本测试
    立即失败。
    """
    _late_event_scenario(db_session, share_class)

    stored = _column(db_session, share_class)
    # 轮 2 的「首个 checkpoint 盖章」：2020-01-01 行在事件披露前就盖了章。
    assert stored[(dt.date(2020, 1, 1), 1)] == Decimal("1.0")

    points = _series(db_session, share_class, dt.date(2020, 6, 1),
                     dt.date(2020, 1, 1), dt.date(2020, 1, 1))
    assert points[0].adjusted_nav == Decimal("1.1")
    assert points[0].adjusted_nav != stored[(dt.date(2020, 1, 1), 1)]


def _unavailable_scenario(db_session, share_class) -> None:
    """2020-01-05 的分红在 2020-01-06 就披露，而当天的净值要到 2020-01-10
    才可见 —— 在 2020-01-06 ~ 2020-01-09 之间的任何决策时点上，事件日都缺
    再投资价格，复权净值【真的】算不出来。
    """
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0",
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, dt.date(2020, 1, 4), "1.05",
             available_at=_utc(2020, 1, 6))
    _add_dist(db_session, share_class, dt.date(2020, 1, 5), "0.1",
              available_at=_utc(2020, 1, 6))
    _add_nav(db_session, share_class, dt.date(2020, 1, 5), "1.0",
             available_at=_utc(2020, 1, 10))
    _add_nav(db_session, share_class, dt.date(2020, 1, 6), "1.2",
             available_at=_utc(2020, 1, 11))
    db_session.flush()


def test_unavailable_propagates_out_of_the_pit_query(db_session, share_class):
    """C-6：算不出来就抛，不得吞掉、不得回退读列、不得填 0 或沿用上期。

    现算意味着 AdjustedNavUnavailable 现在会从 PIT 查询里传播出来。这是
    正确行为：调用方据此把该份额类别在该决策日标记为 UNAVAILABLE。
    先跑一次回填，确保列里【有】值——即便有，读路径也不得拿它兜底。
    """
    _unavailable_scenario(db_session, share_class)
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    assert any(v is not None for v in _column(db_session, share_class).values())

    with pytest.raises(AdjustedNavUnavailable):
        _series(db_session, share_class, dt.date(2020, 1, 7),
                dt.date(2020, 1, 1), dt.date(2020, 12, 31))

    # 缺口补齐之后（2020-01-10 起 2020-01-05 的净值可见），同一份额类别照常
    # 可算 —— 不可算是【该决策时点】的性质，不是该份额类别的永久状态。
    points = _series(db_session, share_class, dt.date(2020, 1, 12),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.adjusted_nav for p in points] == [
        Decimal("1.0"), Decimal("1.05"), Decimal("1.1"), Decimal("1.32"),
    ]


def test_unavailable_checkpoint_does_not_void_whole_share_class(db_session, share_class):
    """回填的逐 checkpoint 容错：单个 checkpoint 算不出来只影响它首发的那些行。

    2020-01-06 这个 checkpoint 上事件日缺净值，compute_adjusted_nav 抛
    AdjustedNavUnavailable。只有在该 checkpoint 才首次成为当前版本的
    2020-01-04 行保持 NULL（列里就是 NULL，不填 0、不沿用上期，C-6），
    其余行照常盖章。

    断言直接打在物化列上（见 _column 的说明）：这是 backfill_adjusted_nav
    的写入行为。PIT 读路径已不读该列，同一场景在读路径上的表现由
    test_unavailable_propagates_out_of_the_pit_query 覆盖 —— 读路径不会
    看到一个 None，它会直接抛异常。
    """
    _unavailable_scenario(db_session, share_class)

    updated = backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    assert updated == 3

    assert _column(db_session, share_class) == {
        (dt.date(2020, 1, 2), 1): Decimal("1.0"),
        (dt.date(2020, 1, 4), 1): None,
        (dt.date(2020, 1, 5), 1): Decimal("1.1"),
        (dt.date(2020, 1, 6), 1): Decimal("1.32"),
    }
