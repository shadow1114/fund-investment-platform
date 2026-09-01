import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.eligibility import EligibilityStatus, LifecycleStatus
from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import (
    Fund,
    FundManager,
    FundManagerAssignment,
    FundShareClass,
    FundStatusHistory,
    InvestmentEligibility,
)

pytestmark = pytest.mark.integration

ING = dt.datetime(2026, 8, 31, tzinfo=dt.UTC)


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-DIM", product_name="维度测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="维度测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _times(available: dt.datetime):
    return dict(available_at=available, availability_quality="INFERRED",
                published_at=None, provider_available_at=None, ingested_at=ING)


def test_manager_assignment_supports_co_management(db_session, share_class):
    """同一基金同一时段可有多位经理。"""
    managers = [FundManager(manager_code=f"M{i}", manager_name=f"经理{i}")
                for i in (1, 2)]
    db_session.add_all(managers)
    db_session.flush()
    for m in managers:
        db_session.add(FundManagerAssignment(
            fund_id=share_class.fund_id, manager_id=m.id,
            valid_from=dt.date(2020, 1, 1), valid_to=None,
            **_times(dt.datetime(2020, 1, 5, tzinfo=dt.UTC)),
        ))
    db_session.flush()
    assert db_session.query(FundManagerAssignment).filter_by(
        fund_id=share_class.fund_id).count() == 2


def test_interval_with_end_before_start_is_rejected(db_session, share_class):
    db_session.add(FundStatusHistory(
        share_class_id=share_class.id,
        lifecycle_status=LifecycleStatus.NORMAL.value,
        subscription_open=True, redemption_open=True,
        valid_from=dt.date(2020, 6, 1), valid_to=dt.date(2020, 1, 1),
        **_times(dt.datetime(2020, 6, 2, tzinfo=dt.UTC)),
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_interval_tables_also_enforce_quality_source_check(db_session, share_class):
    """区间型表同样受 C-12 约束：标 EXACT 就必须真有推送时刻。"""
    db_session.add(FundStatusHistory(
        share_class_id=share_class.id,
        lifecycle_status=LifecycleStatus.NORMAL.value,
        subscription_open=True, redemption_open=True,
        valid_from=dt.date(2020, 1, 1), valid_to=None,
        available_at=dt.datetime(2020, 1, 2, tzinfo=dt.UTC),
        availability_quality="EXACT",
        published_at=None, provider_available_at=None, ingested_at=ING,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_eligibility_history_is_persisted_for_backtest(db_session, share_class):
    """派生实体也要落表 —— 回测需要查当时的可投资性。"""
    db_session.add_all([
        InvestmentEligibility(
            share_class_id=share_class.id,
            eligibility_status=EligibilityStatus.FULLY_ELIGIBLE.value,
            valid_from=dt.date(2020, 1, 1), valid_to=dt.date(2021, 1, 1),
            **_times(dt.datetime(2020, 1, 2, tzinfo=dt.UTC)),
        ),
        InvestmentEligibility(
            share_class_id=share_class.id,
            eligibility_status=EligibilityStatus.EXIT_ONLY.value,
            valid_from=dt.date(2021, 1, 1), valid_to=None,
            **_times(dt.datetime(2021, 1, 2, tzinfo=dt.UTC)),
        ),
    ])
    db_session.flush()
    assert db_session.query(InvestmentEligibility).filter_by(
        share_class_id=share_class.id).count() == 2
