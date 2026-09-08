import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import (
    Fund,
    FundShareClass,
    ProviderFundIdentity,
)
from fip.services.data_service.models.governance import DataProvider
from fip.services.data_service.models.market import FundDistribution, FundNav
from fip.services.data_service.models.raw import RawPayload

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)

FUND_LIST = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["混合型", "混合型"],
})

NAV_FRAME = pd.DataFrame({
    "净值日期": ["2020-01-02", "2020-01-03"],
    "单位净值": ["1.1000", "1.0000"],
})

DIVIDEND_FRAME = pd.DataFrame({
    "年份": ["2020"], "权益登记日": ["2020-01-02"],
    "除息日": ["2020-01-03"], "每10份分红": ["每10份派现金1.0000元"],
})

SPLIT_FRAME = pd.DataFrame({"年份": [], "拆分折算日": [], "拆分折算比例": []})


def _fake_caller(name, **params):
    indicator = params.get("indicator")
    if name == "fund_name_em":
        return FUND_LIST
    if indicator == "单位净值走势":
        return NAV_FRAME
    if indicator == "分红送配详情":
        return DIVIDEND_FRAME
    if indicator == "拆分详情":
        return SPLIT_FRAME
    raise AssertionError(f"未预期的调用 {name} {params}")


@pytest.fixture()
def service(db_session) -> IngestService:
    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_fake_caller)
    return IngestService(db_session, adapter, disclosure_lag_days=1)


def test_fund_list_creates_funds_and_share_classes(db_session, service):
    """两个类别归入同一产品。"""
    result = service.ingest_fund_list()
    assert result.created == 2
    assert result.reassignments == ()
    assert db_session.query(Fund).count() == 1
    assert db_session.query(FundShareClass).count() == 2
    codes = {sc.share_class_code for sc in db_session.query(FundShareClass).all()}
    assert codes == {"A", "C"}


def test_ingest_is_idempotent(db_session, service):
    service.ingest_fund_list()
    service.ingest_fund_list()
    assert db_session.query(FundShareClass).count() == 2


def test_nav_ingest_persists_raw_payload(db_session, service):
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")
    payload = db_session.query(RawPayload).first()
    assert payload is not None
    assert pd.read_parquet(io.BytesIO(payload.payload)).shape[0] == 2
    assert payload.provider_available_at is None  # C-12：如实留空


def test_nav_uses_declared_lag_and_inferred_quality(db_session, service):
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")
    row = db_session.query(FundNav).filter_by(
        effective_at=dt.date(2020, 1, 2)).one()
    assert row.availability_quality == "INFERRED"
    assert row.available_at == dt.datetime(2020, 1, 3, tzinfo=dt.UTC)


def test_revised_value_creates_version_two(db_session, service):
    """同日不同净值 → 新版本，旧版本保留。"""
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")

    revised = AkShareSourceAdapter(
        clock=lambda: FIXED_NOW,
        caller=lambda *_a, **_k: pd.DataFrame({
            "净值日期": ["2020-01-02"], "单位净值": ["1.2000"],
        }),
    )
    IngestService(db_session, revised, disclosure_lag_days=1).ingest_nav(sc.id, "000001")

    rows = db_session.query(FundNav).filter_by(
        effective_at=dt.date(2020, 1, 2)).order_by(FundNav.version).all()
    assert [r.version for r in rows] == [1, 2]
    assert [r.unit_nav for r in rows] == [Decimal("1.1000"), Decimal("1.2000")]


def test_end_to_end_pit_query_returns_adjusted_series(db_session, service):
    """Plan-1 的验收断言。"""
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")
    service.ingest_distributions(sc.id, "000001")
    service.rebuild_adjusted_nav(sc.id, dt.date(2026, 8, 31))

    ctx = DecisionExecutionContext(
        decision_id="D-E2E", decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31), strategy_version="sv-1",
        policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    points = PitDataContext(context=ctx, session=db_session).navs().adjusted_nav_series(
        sc.id, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )
    # 1.10 → 除息 0.10 后 1.00：复权后收益为 0
    assert [p.adjusted_nav for p in points] == [Decimal("1.1"), Decimal("1.1")]
    assert points[-1].chain_availability_quality == "INFERRED"


# --- 同日「分红 + 拆分」合并 ---------------------------------------------
# 六个既有 fixture 里 SPLIT_FRAME 恒为空，从没有哪个日期同时出现在两个 frame
# 里，因此 _MergedEvent 的合并语义（对分红求和、对拆分连乘）此前只由阅读证明。
# 下面这组 fixture 让同一个 effective_at 同时出现分红与拆分。

MERGE_DIVIDEND_FRAME = pd.DataFrame({
    "年份": ["2020"], "权益登记日": ["2020-01-02"],
    "除息日": ["2020-01-03"], "每10份分红": ["每10份派现金1.0000元"],
})

MERGE_SPLIT_FRAME = pd.DataFrame({
    "年份": ["2020"], "拆分折算日": ["2020-01-03"], "拆分折算比例": ["2.0000"],
})


def _merge_caller(name, **params):
    indicator = params.get("indicator")
    if name == "fund_name_em":
        return FUND_LIST
    if indicator == "单位净值走势":
        return NAV_FRAME
    if indicator == "分红送配详情":
        return MERGE_DIVIDEND_FRAME
    if indicator == "拆分详情":
        return MERGE_SPLIT_FRAME
    raise AssertionError(f"未预期的调用 {name} {params}")


@pytest.fixture()
def merge_service(db_session) -> IngestService:
    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_merge_caller)
    return IngestService(db_session, adapter, disclosure_lag_days=1)


def test_same_day_dividend_and_split_merge_into_one_row(db_session, merge_service):
    """同一天同时分红与拆分：合并成一行，两个字段各自保留自己的值。

    parse_distribution_frame 恒发 split_ratio=1、parse_split_frame 恒发
    dividend_per_unit=0，因此「对分红求和」不能把拆分比例吃掉（乘上 1 是
    幂等的），「对拆分连乘」也不能把分红吃掉（加上 0 是幂等的）。这两条性质
    在此之前从未被任何 fixture 触及。
    """
    merge_service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    inserted = merge_service.ingest_distributions(sc.id, "000001")

    rows = db_session.query(FundDistribution).filter_by(share_class_id=sc.id).all()
    assert inserted == 1
    assert len(rows) == 1
    row = rows[0]
    assert row.effective_at == dt.date(2020, 1, 3)
    assert row.dividend_per_unit == Decimal("0.1")   # 求和没吃掉拆分
    assert row.split_ratio == Decimal("2")           # 连乘没吃掉分红


# --- 重复灌入不得产生新版本 ---------------------------------------------

def test_repeated_distribution_ingest_does_not_create_new_versions(db_session, service):
    """重跑是预期的日常增量用法，不得把整部分红史重新插一遍新版本。

    version 的语义是「真实修订」（models/market.py FundDistribution 的
    docstring）。无条件 _next_version + insert 会让每一次重跑都污染它，
    且无界增长。ingest_nav 早已有值相等则跳过的检查，这里必须镜像它。
    """
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()

    first = service.ingest_distributions(sc.id, "000001")
    second = service.ingest_distributions(sc.id, "000001")

    assert first == 1
    assert second == 0, "第二次灌入同一份 fixture 不得插入任何行"
    rows = db_session.query(FundDistribution).filter_by(
        share_class_id=sc.id, effective_at=dt.date(2020, 1, 3)
    ).order_by(FundDistribution.version).all()
    assert [r.version for r in rows] == [1]


def test_revised_distribution_still_creates_new_version(db_session, service):
    """值确实变了才产生新版本 —— 去重不能把真实修订一起吞掉。"""
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_distributions(sc.id, "000001")

    revised = AkShareSourceAdapter(
        clock=lambda: FIXED_NOW,
        caller=lambda name, **params: (
            FUND_LIST if name == "fund_name_em"
            else pd.DataFrame({
                "年份": ["2020"], "权益登记日": ["2020-01-02"],
                "除息日": ["2020-01-03"], "每10份分红": ["每10份派现金2.0000元"],
            }) if params.get("indicator") == "分红送配详情"
            else SPLIT_FRAME
        ),
    )
    IngestService(db_session, revised, disclosure_lag_days=1).ingest_distributions(
        sc.id, "000001"
    )

    rows = db_session.query(FundDistribution).filter_by(
        share_class_id=sc.id, effective_at=dt.date(2020, 1, 3)
    ).order_by(FundDistribution.version).all()
    assert [r.version for r in rows] == [1, 2]
    assert [r.dividend_per_unit for r in rows] == [Decimal("0.1"), Decimal("0.2")]


# --- provider 标识映射 ---------------------------------------------------

def test_fund_list_registers_provider_identity(db_session, service):
    """ingest_fund_list 必须把 AKShare 代码登记成 provider_fund_identity。

    没有这张映射，CLI 就只能靠猜（display_name LIKE 数字代码 → 永不命中 →
    兜底取最小 id），把净值静默写进别人的 PIT 历史。
    """
    service.ingest_fund_list()
    provider = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    a = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    c = db_session.query(FundShareClass).filter_by(share_class_code="C").one()

    mapping = {
        row.provider_fund_id: row.share_class_id
        for row in db_session.query(ProviderFundIdentity).filter_by(
            provider_id=provider.id
        ).all()
    }
    assert mapping == {"000001": a.id, "000002": c.id}


def test_provider_identity_records_are_inferred_and_honest(db_session, service):
    """C-12：AKShare 给不出披露时刻，两列必须如实留空、质量恒为 INFERRED。"""
    service.ingest_fund_list()
    rows = db_session.query(ProviderFundIdentity).all()
    assert rows
    for row in rows:
        assert row.availability_quality == "INFERRED"
        assert row.published_at is None
        assert row.provider_available_at is None
        assert row.available_at == FIXED_NOW
        assert row.ingested_at == FIXED_NOW
        assert row.valid_to is None


def test_provider_identity_registration_is_idempotent(db_session, service):
    """重跑 ingest_fund_list（份额类别都已存在，走 continue 分支）不得重复登记。"""
    service.ingest_fund_list()
    service.ingest_fund_list()
    assert db_session.query(ProviderFundIdentity).count() == 2


# --- 份额类别已存在但映射缺失 -------------------------------------------
# fix round 2 item 6：上一轮只覆盖了「份额类别与映射【都】已存在」的重跑，
# 没有覆盖「份额类别已存在、映射缺失」这条分支 —— 而这正是
# _ensure_provider_identity 必须无条件被调用（而不是塞进 `if share_class is
# None` 里）的理由：映射可能是上一轮遗漏的、也可能被人工清理过，
# 「份额类别已存在」不蕴含「映射已存在」。

def test_missing_mapping_is_registered_even_when_share_class_exists(db_session, service):
    """删掉映射后重跑：份额类别一个不新建，映射必须被补回来。"""
    service.ingest_fund_list()
    db_session.query(ProviderFundIdentity).delete()
    db_session.flush()
    assert db_session.query(ProviderFundIdentity).count() == 0

    result = service.ingest_fund_list()

    assert result.created == 0, "份额类别已存在，不得重复新建"
    assert db_session.query(FundShareClass).count() == 2
    provider = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    mapping = {
        row.provider_fund_id: row.share_class_id
        for row in db_session.query(ProviderFundIdentity).filter_by(
            provider_id=provider.id
        ).all()
    }
    a = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    c = db_session.query(FundShareClass).filter_by(share_class_code="C").one()
    assert mapping == {"000001": a.id, "000002": c.id}


# --- 重指派冲突不得丢掉整批已抓数据 --------------------------------------
# fix round 2 item 4：_ensure_provider_identity 原先直接抛 ValueError，一路
# 穿出 ingest_fund_list，而 cmd_ingest_funds 不捕获 —— 整批 ingest-funds 全废，
# 包括本次已抓到的 raw payload。触发条件并不罕见：上游基金简称改名导致
# split_share_class_name 归到另一个 product_name 就会触发。
# 方向保持（响亮失败优于静默沿用旧映射），但改为收集全部冲突、跑完再统一报告。

RENAMED_FUND_LIST = pd.DataFrame({
    # 000001 的简称改了名，split_share_class_name 会把它归到另一个
    # product_name，于是解析到一个新的份额类别 —— 这就是一次重指派冲突。
    # 000003 是全新的代码，必须照常登记。
    "基金代码": ["000001", "000003"],
    "基金简称": ["测试改名混合A", "测试另一只混合A"],
    "基金类型": ["混合型", "混合型"],
})


def _renamed_caller(name, **params):
    if name == "fund_name_em":
        return RENAMED_FUND_LIST
    raise AssertionError(f"未预期的调用 {name} {params}")


def _renamed_service(session) -> IngestService:
    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_renamed_caller)
    return IngestService(session, adapter, disclosure_lag_days=1)


def test_reassignment_conflict_is_collected_not_raised(db_session, service):
    """冲突逐条收集并如实报告，而不是抛异常炸掉整批。"""
    service.ingest_fund_list()
    a = db_session.query(FundShareClass).filter_by(
        display_name="测试蓝筹混合A").one()

    result = _renamed_service(db_session).ingest_fund_list()

    assert len(result.reassignments) == 1
    conflict = result.reassignments[0]
    assert conflict.provider_code == "AKSHARE"
    assert conflict.provider_fund_id == "000001"
    assert conflict.existing_share_class_id == a.id
    assert conflict.incoming_share_class_id != a.id


def test_conflict_does_not_discard_the_rest_of_the_batch(db_session, service):
    """有冲突时其余基金仍被正常登记 —— 一条冲突不得废掉整批已抓数据。"""
    service.ingest_fund_list()
    # 改名后的批次里也会出现 share_class_code == "A" 的新份额类别，
    # 因此这里必须在第二批之前把「原来那一条」记下来。
    a_id = db_session.query(FundShareClass).filter_by(
        display_name="测试蓝筹混合A").one().id

    result = _renamed_service(db_session).ingest_fund_list()
    assert result.reassignments, "前置条件：本批确实有冲突"

    provider = db_session.query(DataProvider).filter_by(provider_code="AKSHARE").one()
    mapping = {
        row.provider_fund_id: row.share_class_id
        for row in db_session.query(ProviderFundIdentity).filter_by(
            provider_id=provider.id
        ).all()
    }
    # 000003 是本批新代码，必须已登记；
    # 000001 的旧映射必须【原样保留】，绝不静默改指向新份额类别。
    assert "000003" in mapping
    assert mapping["000001"] == a_id
    # raw payload 也照常留存（重跑抓到的这一份不得因冲突被丢弃）。
    assert db_session.query(RawPayload).count() == 2
