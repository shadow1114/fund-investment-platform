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
    ("symbol", "expect_zero_rows"),
    [("161725", False), ("110022", True)],
    ids=["has_split_history", "no_split_history"],
)
def test_fund_split_handles_both_split_and_no_split_funds(symbol, expect_zero_rows):
    """161725 有拆分历史；110022 从未拆分过，上游返回 0 行 0 列（无 schema）
    的空 DataFrame。断言依据同下方 test_fund_distribution_handles_both_
    dividend_and_no_dividend_funds 的 docstring：用 row_count 的具体取值
    而非“没有抛异常”来断言。"""
    adapter = AkShareSourceAdapter()
    record = adapter.fetch("fund_split", symbol=symbol)
    if expect_zero_rows:
        assert record.row_count == 0
    else:
        assert record.row_count > 0


@pytest.mark.parametrize(
    ("symbol", "expect_zero_rows"),
    [("161725", False), ("110022", True)],
    ids=["has_dividend_history", "no_dividend_history"],
)
def test_fund_distribution_handles_both_dividend_and_no_dividend_funds(
    symbol, expect_zero_rows
):
    """与 fund_split 的空结果走的是同一套 _assert_columns 代码路径，但这是
    两个不同的数据集 —— 若只靠 split 测试“顺带”覆盖，一旦有人给 split
    加特例或收窄空结果分支，分红这边会静默失效而没有测试变红。161725 有
    分红历史（3 行）；110022 从未分红过，上游同样返回 0 行 0 列（无 schema）
    的空 DataFrame。用 row_count 的具体取值而非“没有抛异常”来断言 ——
    后者无法区分“处理正确”与“恰好没崩”。"""
    adapter = AkShareSourceAdapter()
    record = adapter.fetch("fund_distribution", symbol=symbol)
    if expect_zero_rows:
        assert record.row_count == 0
    else:
        assert record.row_count > 0

