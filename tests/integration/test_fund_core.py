import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus, split_share_class_name
from fip.services.data_service.models.fund import Fund, FundShareClass, ProviderFundIdentity
from fip.services.data_service.models.governance import DataProvider

pytestmark = pytest.mark.integration


def _make_fund(session, display_name: str, fund_code: str) -> FundShareClass:
    grouping = split_share_class_name(display_name)
    fund = Fund(
        fund_code=fund_code,
        product_name=grouping.product_name,
        grouping_status=grouping.status.value,
    )
    session.add(fund)
    session.flush()
    sc = FundShareClass(
        fund_id=fund.id,
        share_class_code=grouping.share_class_code,
        display_name=display_name,
    )
    session.add(sc)
    session.flush()
    return sc


def test_two_share_classes_can_belong_to_one_fund(db_session):
    fund = Fund(fund_code="P-0001", product_name="易方达蓝筹精选混合",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    db_session.add_all([
        FundShareClass(fund_id=fund.id, share_class_code="A",
                       display_name="易方达蓝筹精选混合A"),
        FundShareClass(fund_id=fund.id, share_class_code="C",
                       display_name="易方达蓝筹精选混合C"),
    ])
    db_session.flush()
    assert db_session.query(FundShareClass).filter_by(fund_id=fund.id).count() == 2


def test_duplicate_share_class_code_within_a_fund_is_rejected(db_session):
    fund = Fund(fund_code="P-0002", product_name="X",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    db_session.add(FundShareClass(fund_id=fund.id, share_class_code="A", display_name="XA"))
    db_session.flush()
    db_session.add(FundShareClass(fund_id=fund.id, share_class_code="A", display_name="XA2"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unconfirmed_grouping_is_persisted_as_its_own_fund(db_session):
    """不猜 —— 归组不确定者单独成一个 fund 并留下待确认标记。"""
    sc = _make_fund(db_session, "广发纳斯达克100ETF", "P-0003")
    fund = db_session.get(Fund, sc.fund_id)
    assert fund.grouping_status == GroupingStatus.UNCONFIRMED.value
    assert sc.share_class_code == "DEFAULT"


def test_one_share_class_can_have_multiple_provider_identities(db_session):
    sc = _make_fund(db_session, "华夏成长混合", "P-0004")
    p1 = DataProvider(provider_code="AKSHARE", display_name="AKShare")
    p2 = DataProvider(provider_code="VENDOR_X", display_name="Vendor X")
    db_session.add_all([p1, p2])
    db_session.flush()
    db_session.add_all([
        ProviderFundIdentity(provider_id=p1.id, provider_fund_id="000001",
                             share_class_id=sc.id, valid_from=dt.date(2020, 1, 1)),
        ProviderFundIdentity(provider_id=p2.id, provider_fund_id="CN000001",
                             share_class_id=sc.id, valid_from=dt.date(2020, 1, 1)),
    ])
    db_session.flush()
    assert db_session.query(ProviderFundIdentity).filter_by(
        share_class_id=sc.id).count() == 2
