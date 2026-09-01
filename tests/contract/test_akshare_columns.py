"""数据源契约测试 —— 需联网，用 -m contract 单独运行。

作用：AKShare 升级后若改了列名，本测试失败，而不是让 Adapter
静默错映射字段。这是 R-2 的主要防线。
"""

import pytest

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.adapters.akshare.datasets import DATASETS

pytestmark = pytest.mark.contract

PROBE_PARAMS: dict[str, dict[str, str]] = {
    "fund_list": {},
    "fund_nav": {"symbol": "000001"},
    "fund_cumulative_nav": {"symbol": "000001"},
    "fund_distribution": {"symbol": "161725"},
    "fund_split": {"symbol": "161725"},
    "risk_free_rate": {"start_date": "20240101", "end_date": "20240110"},
}


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_upstream_still_provides_declared_columns(dataset):
    adapter = AkShareSourceAdapter()
    record = adapter.fetch(dataset, **PROBE_PARAMS[dataset])
    assert record.row_count >= 0


def test_every_dataset_has_probe_params():
    assert set(PROBE_PARAMS) == set(DATASETS), (
        "新增数据集时必须同时补探查参数，否则该数据集没有契约保护"
    )


@pytest.mark.parametrize(
    "symbol",
    ["161725", "110022"],
    ids=["has_split_history", "no_split_history"],
)
def test_fund_split_handles_both_split_and_no_split_funds(symbol):
    """161725 有拆分历史；110022 从未拆分过，上游返回 0 行 0 列（无 schema）
    的空 DataFrame。只探测有数据的基金（如原先只覆盖 161725）看不出“无
    schema 的合法空结果”被误判为契约违反的问题 —— 两种形状都必须成功。"""
    adapter = AkShareSourceAdapter()
    record = adapter.fetch("fund_split", symbol=symbol)
    assert record.row_count >= 0

