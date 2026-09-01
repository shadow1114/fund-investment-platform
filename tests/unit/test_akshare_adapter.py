import datetime as dt
import io

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.client import (
    AkShareContractError,
    AkShareSourceAdapter,
)
from fip.services.data_service.adapters.akshare.datasets import DATASETS

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)


def _adapter(frame: pd.DataFrame) -> AkShareSourceAdapter:
    return AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=lambda *_a, **_k: frame)


def test_fetch_returns_parquet_payload_and_row_count():
    frame = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0000"],
                          "日增长率": ["0.10"]})
    record = _adapter(frame).fetch("fund_nav", symbol="000001")
    assert record.row_count == 1
    assert record.dataset == "fund_nav"
    restored = pd.read_parquet(io.BytesIO(record.payload))
    assert list(restored.columns) == ["净值日期", "单位净值", "日增长率"]


def test_fetch_leaves_both_time_sources_null():
    """C-12：AKShare 给不出披露时刻，Adapter 必须如实留空。"""
    frame = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0000"],
                          "日增长率": ["0.10"]})
    record = _adapter(frame).fetch("fund_nav", symbol="000001")
    assert record.published_at is None
    assert record.provider_available_at is None
    assert record.ingested_at == FIXED_NOW


def test_missing_required_column_raises_contract_error():
    """列缺失必须显式失败 —— 静默错映射是最危险的失败模式。"""
    frame = pd.DataFrame({"净值日期": ["2020-01-02"]})  # 缺 单位净值
    with pytest.raises(AkShareContractError, match="单位净值"):
        _adapter(frame).fetch("fund_nav", symbol="000001")


def test_unknown_dataset_raises():
    with pytest.raises(KeyError, match="not_a_dataset"):
        _adapter(pd.DataFrame()).fetch("not_a_dataset")


def test_request_params_are_recorded():
    frame = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0000"],
                          "日增长率": ["0.10"]})
    record = _adapter(frame).fetch("fund_nav", symbol="000001")
    assert record.request_params["symbol"] == "000001"
    assert record.request_params["indicator"] == "单位净值走势"


def test_adapter_satisfies_the_source_port():
    from fip.platform.source.port import SourceAdapter

    assert isinstance(_adapter(pd.DataFrame()), SourceAdapter)


def test_every_dataset_declares_required_columns():
    """没有列契约的数据集等于没有契约测试。"""
    for code, spec in DATASETS.items():
        assert spec.required_columns, f"数据集 {code} 未声明 required_columns"


def test_zero_schema_empty_frame_is_a_legitimate_empty_result():
    """AKShare 对“该基金无此类记录”（如从未拆分过）的表达是 0 行 0 列的
    空 DataFrame（df.columns 为空）。这不是 schema 变更，必须放行，
    row_count=0，不抛异常。"""
    frame = pd.DataFrame()
    record = _adapter(frame).fetch("fund_split", symbol="110022")
    assert record.row_count == 0


def test_zero_row_frame_with_wrong_columns_still_raises():
    """0 行但上游给出了列结构，且列结构与契约不符：说明 schema 变了，
    不能因为“没有数据行”就放行 —— 判据是有没有 schema，不是有没有数据。"""
    frame = pd.DataFrame(columns=["年份", "拆分折算日"])  # 缺 拆分折算比例
    with pytest.raises(AkShareContractError, match="拆分折算比例"):
        _adapter(frame).fetch("fund_split", symbol="161725")
