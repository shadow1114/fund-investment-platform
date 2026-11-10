import datetime as dt

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import Fund, FundBasicInfoHistory, FundShareClass

pytestmark = pytest.mark.integration

NOW = dt.datetime(2026, 11, 3, 10, 0, tzinfo=dt.UTC)
FUND_LIST = pd.DataFrame(
    {"基金代码": ["000001"], "基金简称": ["测试基金A"], "基金类型": ["混合型"]}
)


def _ingest_service(db_session, overview_row, fund_company_row=None):
    def caller(name, **params):
        if name == "fund_name_em":
            return FUND_LIST
        if name == "fund_overview_em":
            return pd.DataFrame([overview_row])
        if name == "fund_individual_basic_info_xq":
            rows = [("基金代码", params["symbol"])]
            if fund_company_row is not None:
                rows.extend(fund_company_row.items())
            return pd.DataFrame(rows, columns=["item", "value"])
        raise AssertionError(f"unexpected provider call: {name}")

    ingest = IngestService(
        db_session,
        AkShareSourceAdapter(clock=lambda: NOW, caller=caller),
        disclosure_lag_days=None,
    )
    ingest.ingest_fund_list()
    return ingest, db_session.query(FundShareClass).one().fund_id


def test_basic_info_persists_fund_company_not_management_person_or_manager(db_session):
    ingest, fund_id = _ingest_service(
        db_session,
        {
            "基金全称": "测试基金",
            "基金类型": "混合型",
            "基金管理人": "王经理",
            "基金经理": "张经理",
        },
        {"基金公司": " 华夏基金 ", "基金经理": "李经理"},
    )

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")

    fund = db_session.get(Fund, fund_id)
    history = db_session.query(FundBasicInfoHistory).filter_by(fund_id=fund_id).one()
    assert fund.fund_company == "华夏基金"
    assert history.normalized_fields["fund_company"] == "华夏基金"
    assert history.raw_fields["基金公司"] == " 华夏基金 "
    assert "基金管理人" not in history.raw_fields
    assert "基金经理" not in history.raw_fields
    assert "基金经理" not in history.normalized_fields


def test_missing_company_never_erases_projection_and_real_change_versions_history(db_session):
    company_row = {"基金公司": "公司甲"}
    ingest, fund_id = _ingest_service(
        db_session, {"基金全称": "测试基金", "基金类型": "混合型"}, company_row
    )
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    company_row["基金公司"] = "  "

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    assert db_session.get(Fund, fund_id).fund_company == "公司甲"

    company_row["基金公司"] = "公司乙"
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    histories = (
        db_session.query(FundBasicInfoHistory)
        .filter_by(fund_id=fund_id)
        .order_by(FundBasicInfoHistory.version)
        .all()
    )
    assert db_session.get(Fund, fund_id).fund_company == "公司乙"
    assert [row.normalized_fields.get("fund_company") for row in histories] == [
        "公司甲",
        None,
        "公司乙",
    ]


def test_repeated_identical_overview_does_not_duplicate_history_version(db_session):
    ingest, fund_id = _ingest_service(
        db_session,
        {"基金全称": "测试基金", "基金类型": "混合型"},
        {"基金公司": "稳定公司"},
    )

    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")

    histories = db_session.query(FundBasicInfoHistory).filter_by(fund_id=fund_id).all()
    assert len(histories) == 1
    assert histories[0].version == 1


def test_local_backfill_uses_retained_company_evidence_without_editing_snapshots(db_session):
    from fip.services.data_service.company import backfill_fund_companies

    ingest, fund_id = _ingest_service(
        db_session,
        {"基金全称": "测试基金", "基金类型": "混合型"},
        {"基金公司": "历史公司"},
    )
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    fund = db_session.get(Fund, fund_id)
    fund.fund_company = None
    history = db_session.query(FundBasicInfoHistory).filter_by(fund_id=fund_id).one()
    original_normalized = dict(history.normalized_fields)
    original_raw = dict(history.raw_fields)

    report = backfill_fund_companies(db_session, dry_run=False)

    assert report.updated == 1
    assert fund.fund_company == "历史公司"
    assert history.normalized_fields == original_normalized
    assert history.raw_fields == original_raw


def test_local_backfill_can_resolve_legacy_raw_company_without_normalized_field(db_session):
    from fip.services.data_service.company import backfill_fund_companies

    ingest, fund_id = _ingest_service(
        db_session,
        {"基金全称": "测试基金", "基金类型": "混合型"},
        {"基金公司": "原始来源公司"},
    )
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    fund = db_session.get(Fund, fund_id)
    fund.fund_company = None
    history = db_session.query(FundBasicInfoHistory).filter_by(fund_id=fund_id).one()
    history.normalized_fields = {
        key: value for key, value in history.normalized_fields.items() if key != "fund_company"
    }
    original_normalized = dict(history.normalized_fields)
    original_raw = dict(history.raw_fields)

    report = backfill_fund_companies(db_session, dry_run=False)

    assert report.updated == 1
    assert fund.fund_company == "原始来源公司"
    assert history.normalized_fields == original_normalized
    assert history.raw_fields == original_raw


def test_local_backfill_dry_run_and_existing_projection_preservation(db_session):
    from fip.services.data_service.company import backfill_fund_companies

    ingest, fund_id = _ingest_service(
        db_session,
        {"基金全称": "测试基金", "基金类型": "混合型"},
        {"基金公司": "旧公司"},
    )
    ingest.ingest_fund_overview(fund_id, "000001", actor="test")
    fund = db_session.get(Fund, fund_id)
    fund.fund_company = "人工校准公司"

    report = backfill_fund_companies(db_session, dry_run=True)

    assert report.updated == 0
    assert report.candidates == 0
    assert fund.fund_company == "人工校准公司"
