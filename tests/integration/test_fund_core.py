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


_VALID_FROM = dt.date(2020, 1, 1)
_AVAILABLE_AT = dt.datetime(2020, 1, 1, 9, 0, tzinfo=dt.UTC)
_INGESTED_AT = dt.datetime(2020, 1, 1, 10, 0, tzinfo=dt.UTC)


def _identity_kwargs(**overrides):
    """provider_fund_identity 是 IntervalMixin（anchor=valid_from）表，
    available_at / availability_quality / ingested_at 均为 NOT NULL
    （fix round 1，04-database-design §6.2）。"""
    base = dict(
        valid_from=_VALID_FROM,
        available_at=_AVAILABLE_AT,
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=_INGESTED_AT,
    )
    base.update(overrides)
    return base


def test_one_share_class_can_have_multiple_provider_identities(db_session):
    sc = _make_fund(db_session, "华夏成长混合", "P-0004")
    p1 = DataProvider(provider_code="AKSHARE", display_name="AKShare")
    p2 = DataProvider(provider_code="VENDOR_X", display_name="Vendor X")
    db_session.add_all([p1, p2])
    db_session.flush()
    db_session.add_all([
        ProviderFundIdentity(provider_id=p1.id, provider_fund_id="000001",
                             share_class_id=sc.id, **_identity_kwargs()),
        ProviderFundIdentity(provider_id=p2.id, provider_fund_id="CN000001",
                             share_class_id=sc.id, **_identity_kwargs()),
    ])
    db_session.flush()
    assert db_session.query(ProviderFundIdentity).filter_by(
        share_class_id=sc.id).count() == 2


def test_provider_fund_identity_available_at_cannot_precede_valid_from(db_session):
    """fix round 1 的回归测试：ck_provider_fund_identity_time_order 必须以
    anchor="valid_from" 生效 —— available_at 早于 valid_from 意味着平台在
    这条 Provider 映射生效前就“看到”了它，是前视偏差，必须被拒绝。"""
    sc = _make_fund(db_session, "华夏成长混合", "P-0005")
    provider = DataProvider(provider_code="AKSHARE2", display_name="AKShare")
    db_session.add(provider)
    db_session.flush()
    early = _VALID_FROM - dt.timedelta(days=1)
    db_session.add(ProviderFundIdentity(
        provider_id=provider.id, provider_fund_id="000002", share_class_id=sc.id,
        **_identity_kwargs(available_at=dt.datetime(
            early.year, early.month, early.day, 9, 0, tzinfo=dt.UTC
        )),
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()
