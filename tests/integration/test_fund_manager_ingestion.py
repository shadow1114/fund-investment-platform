import datetime as dt

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import (
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


def test_basic_info_ingest_persists_manager_history_and_tracks_changes(db_session):
    observed_at = [FIXED_NOW]
    current_managers: list[str | None] = ["张三、李四"]
    manager_field = ["基金经理人"]

    def caller(name, **params):
        if name == "fund_name_em":
            return FUND_LIST
        if name == "fund_overview_em":
            fields: dict[str, list[str | None]] = {
                "基金全称": ["测试蓝筹混合"],
                "基金类型": ["混合型"],
            }
            if current_managers[0] is not None:
                fields[manager_field[0]] = [current_managers[0]]
            return pd.DataFrame(fields)
        raise AssertionError(f"Unexpected call {name} {params}")

    adapter = AkShareSourceAdapter(clock=lambda: observed_at[0], caller=caller)
    ingest = IngestService(db_session, adapter, disclosure_lag_days=None)
    ingest.ingest_fund_list()
    fund_id = db_session.query(FundShareClass).one().fund_id

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")

    history = db_session.query(FundBasicInfoHistory).filter_by(fund_id=fund_id).one()
    assert history.raw_fields["基金经理人"] == "张三、李四"
    assert history.normalized_fields["manager_name"] == "张三、李四"
    managers = db_session.query(FundManager).order_by(FundManager.manager_name).all()
    assert [manager.manager_name for manager in managers] == ["张三", "李四"]
    assignments = (
        db_session.query(FundManagerAssignment)
        .join(FundManager, FundManager.id == FundManagerAssignment.manager_id)
        .order_by(FundManager.manager_name)
        .all()
    )
    assert [assignment.valid_from for assignment in assignments] == [FIXED_NOW.date()] * 2
    assert all(assignment.valid_to is None for assignment in assignments)
    assert all(assignment.available_at == FIXED_NOW for assignment in assignments)
    assert all(assignment.availability_quality == "INFERRED" for assignment in assignments)

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    assert db_session.query(FundManager).count() == 2
    assert db_session.query(FundManagerAssignment).count() == 2

    observed_at[0] += dt.timedelta(days=3)
    current_managers[0] = "张三、王五"
    manager_field[0] = "基金经理"
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")

    assignments_by_name = {
        manager.manager_name: assignment
        for assignment, manager in db_session.query(FundManagerAssignment, FundManager)
        .join(FundManager, FundManager.id == FundManagerAssignment.manager_id)
        .all()
    }
    assert assignments_by_name["张三"].valid_to is None
    assert assignments_by_name["李四"].valid_to == observed_at[0].date()
    assert assignments_by_name["王五"].valid_from == observed_at[0].date()
    assert assignments_by_name["王五"].valid_to is None

    observed_at[0] += dt.timedelta(days=2)
    current_managers[0] = None
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    assert db_session.query(FundManagerAssignment).filter_by(valid_to=None).count() == 2
