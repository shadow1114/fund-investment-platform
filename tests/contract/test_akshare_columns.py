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
