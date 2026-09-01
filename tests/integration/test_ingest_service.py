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
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundNav
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
    created = service.ingest_fund_list()
    assert created == 2
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
