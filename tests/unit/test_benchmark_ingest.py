"""基准公式解析、配置匹配及幂等写入编排测试。"""

import datetime as dt
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd
import pytest

from fip.platform.source.port import SourceRecord
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.benchmark_ingest import (
    load_component_mapping,
    normalize_component,
    parse_benchmark,
    save_fund_benchmark,
)
from fip.services.data_service.company import fund_overview_from_record
from fip.services.data_service.models.benchmark import (
    BenchmarkComponent,
    BenchmarkDefinition,
    BenchmarkIndex,
    BenchmarkMapping,
)

EXPRESSION = "中证800成长指数收益率*70%+中债-综合全价（总值）指数收益率*30%"
NOW = dt.datetime(2026, 11, 12, 10, tzinfo=dt.UTC)


@pytest.mark.parametrize(("expression", "expected"), [
    (EXPRESSION, (("中证800成长指数收益率", Decimal("0.7")),
                  ("中债-综合全价(总值)指数收益率", Decimal("0.3")))),
    ("指数A", (("指数A", Decimal(1)),)),
    ("恒生指数收益率5%(经汇率估值调整)",
     (("恒生指数收益率5%(经汇率估值调整)", Decimal(1)),)),
    ("指数A*未注明", (("指数A*未注明", Decimal(1)),)),
    ("中债综合指数（全价）", (("中债综合指数(全价)", Decimal(1)),)),
    ("70%×指数A + 30%*指数B", (("指数A", Decimal("0.7")), ("指数B", Decimal("0.3")))),
    ("指数A*70%+指数A*30%", (("指数A", Decimal(1)),)),
])
def test_parse_benchmark(expression, expected):
    assert parse_benchmark(expression) == expected


@pytest.mark.parametrize("expression", [
    "", "指数A*70%+指数B*20%", "一年期存款利率+1.2%", "指数A+指数B",
    "(指数A*70%+指数B*30%)*100%", "指数A*0%+指数B*100%", "指数A*101%",
    "指数A*50%+", "指数A)*100%", "指数A(*100%", "指数A*33.333333333%+指数B*66.666666667%",
])
def test_unsupported_formulas_are_not_silently_changed(expression):
    with pytest.raises(ValueError):
        parse_benchmark(expression)


def test_overview_extracts_benchmark_after_identity_validation():
    frame = pd.DataFrame([{
        "基金代码": "000001（前端）、000002（后端）", "基金全称": "华夏成长",
        "基金类型": "混合型", "业绩比较基准": EXPRESSION,
    }])
    record = AkShareSourceAdapter(
        clock=lambda: NOW, caller=lambda *args, **kwargs: frame,
    ).fetch("fund_overview", symbol="000001")
    assert fund_overview_from_record(record, symbol="000001").benchmark == EXPRESSION
    with pytest.raises(ValueError, match="identity"):
        fund_overview_from_record(record, symbol="000003")


def test_repository_config_resolves_000001_components():
    mapping = load_component_mapping()
    assert mapping["中证800成长指数收益率"] == "中证800成长"
    assert mapping["中债-综合全价(总值)指数收益率"] == "中债综合全价(总值)"
    assert mapping["上证国债指数收益率"] == "上证国债"


def test_invalid_config_is_rejected(tmp_path):
    path = tmp_path / "mapping.yaml"
    path.write_text("component_to_lookup_name: {指数A: 123456}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_component_mapping(path)


def _save(session, expression=EXPRESSION, mapping=None):
    warnings = []
    save_fund_benchmark(
        session, share_class_id=101, fund_code="000001", expression=expression,
        record=SourceRecord(dataset="fund_overview", payload=b"", row_count=1, ingested_at=NOW),
        component_mapping=load_component_mapping() if mapping is None else mapping,
        warnings=warnings,
    )
    return warnings


def _session(current=None, definition=None):
    session = MagicMock()
    equity = BenchmarkIndex(id=201, provider_code="H30355", display_name="中证800成长")
    bond = BenchmarkIndex(
        id=202, provider_code="2c90818811afed8d0111c0c672b31578",
        display_name="中债综合全价(总值)",
    )
    equity_result, bond_result, mapping_result = MagicMock(), MagicMock(), MagicMock()
    equity_result.all.return_value = [equity]
    bond_result.all.return_value = [bond]
    mapping_result.first.return_value = current
    session.scalars.side_effect = [equity_result, bond_result, mapping_result]
    session.scalar.return_value = definition

    def add(item):
        if isinstance(item, BenchmarkDefinition):
            item.id = 501

    session.add.side_effect = add
    return session


def test_complete_match_saves_definition_weights_and_share_mapping():
    session = _session()
    assert _save(session) == []
    definition = session.add.call_args_list[0].args[0]
    assert isinstance(definition, BenchmarkDefinition)
    components = session.add_all.call_args.args[0]
    assert {(item.index_id, item.weight) for item in components} == {
        (201, Decimal("0.7")), (202, Decimal("0.3")),
    }
    assert all(isinstance(item, BenchmarkComponent) for item in components)
    mapping = session.add.call_args_list[1].args[0]
    assert mapping.share_class_id == 101
    assert mapping.benchmark_id == 501
    assert mapping.valid_from == NOW.date()
    assert mapping.available_at == NOW
    assert mapping.availability_quality == "INFERRED"


def test_missing_component_prints_name_and_writes_nothing(capsys):
    session = _session()
    warnings = _save(session, mapping={normalize_component("中证800成长指数收益率"): "中证800成长"})
    assert len(warnings) == 1
    assert "中债-综合全价(总值)指数收益率" in capsys.readouterr().out
    session.add.assert_not_called()
    session.add_all.assert_not_called()


@pytest.mark.parametrize("candidates", [[], [
    BenchmarkIndex(id=1, display_name="同码指数甲"),
    BenchmarkIndex(id=2, display_name="同码指数乙"),
]])
def test_missing_or_ambiguous_database_index_writes_nothing(candidates, capsys):
    session = MagicMock()
    session.scalars.return_value.all.return_value = candidates
    warnings = _save(session, expression="指数A", mapping={"指数A": "A"})
    assert len(warnings) == 1
    assert "指数A" in capsys.readouterr().out
    session.add.assert_not_called()


def _existing_session(weights, *, shared=False):
    current = BenchmarkMapping(
        id=1, benchmark_id=501, valid_from=dt.date(2026, 11, 11),
        available_at=NOW - dt.timedelta(days=1), ingested_at=NOW - dt.timedelta(days=1),
    )
    definition = BenchmarkDefinition(id=501, display_name=EXPRESSION)
    session = _session(current=current, definition=definition)
    results = list(session.scalars.side_effect)
    component_result = MagicMock()
    component_result.all.return_value = [
        BenchmarkComponent(index_id=index_id, weight=weight) for index_id, weight in weights.items()
    ]
    session.scalars.side_effect = [*results, component_result]
    session.scalar.side_effect = [definition, 99 if shared else None]
    return session, current, definition


def test_repeated_identical_mapping_is_noop():
    session, current, definition = _existing_session({201: Decimal("0.7"), 202: Decimal("0.3")})
    assert _save(session) == []
    session.add.assert_not_called()
    session.add_all.assert_not_called()
    assert current.available_at == NOW - dt.timedelta(days=1)


def test_change_updates_existing_definition_and_mapping_in_place():
    session, current, definition = _existing_session({201: Decimal("0.6"), 202: Decimal("0.4")})
    assert _save(session) == []
    session.add.assert_not_called()
    assert current.benchmark_id == definition.id == 501
    assert current.valid_from == dt.date(2026, 11, 11)
    assert current.valid_to is None
    assert current.available_at == NOW
    assert current.ingested_at == NOW
    components = session.add_all.call_args.args[0]
    assert {(item.index_id, item.weight) for item in components} == {
        (201, Decimal("0.7")), (202, Decimal("0.3")),
    }
    assert all(item.benchmark_id == 501 for item in components)


def test_shared_definition_is_not_modified(capsys):
    session, current, definition = _existing_session(
        {201: Decimal("0.6"), 202: Decimal("0.4")}, shared=True,
    )
    assert len(_save(session)) == 1
    assert "其他映射引用" in capsys.readouterr().out
    session.add.assert_not_called()
    session.add_all.assert_not_called()
    assert current.available_at == NOW - dt.timedelta(days=1)


def test_index_is_resolved_by_configured_provider_code():
    session = _session()
    assert _save(session) == []
    query = session.scalars.call_args_list[1].args[0]
    assert "benchmark_index.display_name =" in str(query)
    assert query.compile().params == {"display_name_1": "中债综合全价(总值)"}
