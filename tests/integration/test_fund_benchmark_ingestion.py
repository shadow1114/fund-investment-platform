"""从基金概况到基准定义、组成项及份额映射的数据库测试。"""

import datetime as dt
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import func, select

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.benchmark import (
    BenchmarkComponent,
    BenchmarkDefinition,
    BenchmarkIndex,
    BenchmarkMapping,
)
from fip.services.data_service.models.fund import FundShareClass

pytestmark = pytest.mark.integration
NOW = dt.datetime(2026, 11, 12, 10, tzinfo=dt.UTC)
EXPRESSION = "中证800成长指数收益率*70%+中债-综合全价（总值）指数收益率*30%"


def _service(session, expression):
    def caller(name, **params):
        if name == "fund_name_em":
            return pd.DataFrame({
                "基金代码": ["000001"], "基金简称": ["测试基金A"], "基金类型": ["混合型"],
            })
        if name == "fund_overview_em":
            return pd.DataFrame([{
                "基金代码": params["symbol"], "基金全称": "测试基金", "基金类型": "混合型",
                "业绩比较基准": expression,
            }])
        raise AssertionError(f"非预期接口调用：{name}")

    return IngestService(
        session, AkShareSourceAdapter(clock=lambda: NOW, caller=caller), disclosure_lag_days=None,
    )


def test_fund_list_saves_composite_benchmark_and_is_idempotent(db_session):
    service = _service(db_session, EXPRESSION)
    result = service.ingest_fund_list()
    assert not result.warnings
    share = db_session.scalars(select(FundShareClass)).one()
    mapping = db_session.scalars(select(BenchmarkMapping)).one()
    assert mapping.share_class_id == share.id
    assert mapping.valid_from == NOW.date()
    assert mapping.available_at == NOW
    rows = db_session.execute(
        select(BenchmarkIndex.display_name, BenchmarkComponent.weight)
        .join(BenchmarkComponent, BenchmarkComponent.index_id == BenchmarkIndex.id)
        .where(BenchmarkComponent.benchmark_id == mapping.benchmark_id)
    ).all()
    assert set(rows) == {
        ("中证800成长", Decimal("0.7")), ("中债综合全价(总值)", Decimal("0.3")),
    }
    service.ingest_fund_list()
    assert db_session.scalar(select(func.count()).select_from(BenchmarkDefinition)) == 1
    assert db_session.scalar(select(func.count()).select_from(BenchmarkMapping)) == 1
    assert db_session.scalar(select(func.count()).select_from(BenchmarkComponent)) == 2


def test_changed_weights_update_same_definition_and_mapping(db_session):
    _service(db_session, EXPRESSION).ingest_fund_list()
    mapping = db_session.scalars(select(BenchmarkMapping)).one()
    mapping_id, definition_id = mapping.id, mapping.benchmark_id
    changed = "中证800成长指数收益率*60%+中债-综合全价（总值）指数收益率*40%"
    _service(db_session, changed).ingest_fund_list()
    mapping = db_session.scalars(select(BenchmarkMapping)).one()
    assert mapping.id == mapping_id
    assert mapping.benchmark_id == definition_id
    assert db_session.scalar(select(func.count()).select_from(BenchmarkDefinition)) == 1
    rows = db_session.execute(
        select(BenchmarkIndex.display_name, BenchmarkComponent.weight)
        .join(BenchmarkComponent, BenchmarkComponent.index_id == BenchmarkIndex.id)
        .where(BenchmarkComponent.benchmark_id == definition_id)
    ).all()
    assert set(rows) == {
        ("中证800成长", Decimal("0.6")), ("中债综合全价(总值)", Decimal("0.4")),
    }


def test_unmapped_component_skips_entire_benchmark_and_reports_name(db_session, capsys):
    expression = "中证800成长指数收益率*70%+未配置指数收益率*30%"
    result = _service(db_session, expression).ingest_fund_list()
    assert any("未配置指数收益率" in warning for warning in result.warnings)
    assert "未配置指数收益率" in capsys.readouterr().out
    for model in (BenchmarkDefinition, BenchmarkComponent, BenchmarkMapping):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
    assert db_session.scalar(select(func.count()).select_from(FundShareClass)) == 1
