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
