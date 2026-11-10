import datetime as dt

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import (
    Fund,
    FundBasicInfoHistory,
    FundManager,
    FundManagerAssignment,
    FundShareClass,
)

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)
FUND_LIST = pd.DataFrame(
    {
        "基金代码": ["000001"],
        "基金简称": ["测试蓝筹混合A"],
        "基金类型": ["混合型"],
    }
)


def test_basic_info_ingest_stores_fund_company_but_not_manager_data(db_session):
    observed_at = [FIXED_NOW]
    current_managers: list[str | None] = ["张三、李四"]
    manager_field = ["基金经理人"]

    def caller(name, **params):
        if name == "fund_name_em":
            return FUND_LIST
        if name == "fund_overview_em":
            fields: dict[str, list[str | None]] = {
                "基金代码": [params["symbol"]],
                "基金全称": ["测试蓝筹混合"],
                "基金类型": ["混合型"],
            }
            if current_managers[0] is not None:
                fields[manager_field[0]] = [current_managers[0]]
            return pd.DataFrame(fields)
        if name == "fund_individual_basic_info_xq":
            return pd.DataFrame(
                [
                    ("基金代码", params["symbol"]),
                    ("基金公司", "华夏基金"),
                    ("基金经理", "李四"),
                ],
                columns=["item", "value"],
            )
        raise AssertionError(f"Unexpected call {name} {params}")

    adapter = AkShareSourceAdapter(clock=lambda: observed_at[0], caller=caller)
    ingest = IngestService(db_session, adapter, disclosure_lag_days=None)
    ingest.ingest_fund_list()
    fund_id = db_session.query(FundShareClass).one().fund_id

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")

    history = db_session.query(FundBasicInfoHistory).filter_by(fund_id=fund_id).one()
    assert "基金经理人" not in history.raw_fields
    assert "基金经理" not in history.raw_fields
    assert "基金管理人" not in history.raw_fields
    assert history.raw_fields["基金公司"] == "华夏基金"
    assert db_session.get(Fund, fund_id).fund_company == "华夏基金"
    assert "manager_name" not in history.normalized_fields
    assert db_session.query(FundManager).count() == 0
    assert db_session.query(FundManagerAssignment).count() == 0

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    assert db_session.query(FundManager).count() == 0
    assert db_session.query(FundManagerAssignment).count() == 0

    observed_at[0] += dt.timedelta(days=3)
    current_managers[0] = "张三、王五"
    manager_field[0] = "基金经理"
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")

    assert db_session.query(FundManager).count() == 0
    assert db_session.query(FundManagerAssignment).count() == 0

    observed_at[0] += dt.timedelta(days=2)
    current_managers[0] = None
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    assert db_session.query(FundManager).count() == 0
    assert db_session.query(FundManagerAssignment).count() == 0
