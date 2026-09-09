import datetime as dt
from decimal import Decimal

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.models.fund import (
    Fund,
    FundClassificationHistory,
    FundFee,
    FundShareClass,
)
from fip.services.data_service.models.market import RiskFreeRate

pytestmark = pytest.mark.integration


def _utc(month: int, day: int) -> dt.datetime:
    return dt.datetime(2026, month, day, tzinfo=dt.UTC)


def _times(available_at: dt.datetime) -> dict[str, object]:
    return {
        "available_at": available_at,
        "availability_quality": "INFERRED",
        "published_at": None,
        "provider_available_at": None,
        "ingested_at": _utc(9, 8),
    }


def _context(session) -> PitDataContext:
    day = dt.date(2026, 8, 31)
    execution = DecisionExecutionContext(
        decision_id="D-DIMENSION-PIT",
        decision_at=day,
        data_as_of=day,
        strategy_version="sv1",
        policy_version="pv1",
        code_version="cv1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    return PitDataContext(execution, session)


@pytest.fixture()
def fund_and_class(db_session):
    fund = Fund(
        fund_code="P-DIM-PIT",
        product_name="dimension PIT",
        grouping_status="CONFIRMED",
    )
    db_session.add(fund)
    db_session.flush()
    share_class = FundShareClass(
        fund_id=fund.id,
        share_class_code="A",
        display_name="dimension PITA",
    )
    db_session.add(share_class)
    db_session.flush()
    return fund, share_class


def test_classification_current_uses_latest_visible_correction(
    db_session, fund_and_class
):
    fund, _share_class = fund_and_class
    common = {
        "fund_id": fund.id,
        "classification_scheme": "FIP_INTERNAL_L2",
        "valid_from": dt.date(2026, 1, 1),
        "valid_to": dt.date(2027, 1, 1),
    }
    db_session.add_all([
        FundClassificationHistory(
            **common, classification_code="BOND", **_times(_utc(8, 1))
        ),
        FundClassificationHistory(
            **common, classification_code="HYBRID", **_times(_utc(8, 20))
        ),
        FundClassificationHistory(
            **common, classification_code="ACTIVE_EQUITY", **_times(_utc(9, 1))
        ),
    ])
    db_session.flush()

    point = _context(db_session).classifications().current(fund.id)

    assert point is not None
    assert point.classification_code == "HYBRID"
    assert point.valid_from == dt.date(2026, 1, 1)


def test_fee_current_returns_latest_visible_value_per_type(db_session, fund_and_class):
    _fund, share_class = fund_and_class
    common = {
        "share_class_id": share_class.id,
        "fee_type": "management",
        "valid_from": dt.date(2026, 1, 1),
        "valid_to": dt.date(2027, 1, 1),
    }
    db_session.add_all([
        FundFee(**common, rate=Decimal("0.010"), **_times(_utc(8, 1))),
        FundFee(**common, rate=Decimal("0.009"), **_times(_utc(8, 20))),
        FundFee(**common, rate=Decimal("0.008"), **_times(_utc(9, 1))),
        FundFee(
            share_class_id=share_class.id,
            fee_type="custodian",
            rate=Decimal("0.002"),
            valid_from=dt.date(2026, 1, 1),
            valid_to=dt.date(2027, 1, 1),
            **_times(_utc(8, 1)),
        ),
    ])
    db_session.flush()

    points = _context(db_session).fees().current(share_class.id)

    assert [(point.fee_type, point.rate) for point in points] == [
        ("custodian", Decimal("0.00200000")),
        ("management", Decimal("0.00900000")),
    ]


def test_risk_free_series_uses_highest_visible_version(db_session):
    day = dt.date(2026, 8, 1)
    common = {
        "curve_code": "CN_TREASURY",
        "currency": "CNY",
        "tenor": "1Y",
        "effective_at": day,
    }
    db_session.add_all([
        RiskFreeRate(**common, version=1, rate=Decimal("0.020"), **_times(_utc(8, 2))),
        RiskFreeRate(**common, version=2, rate=Decimal("0.021"), **_times(_utc(8, 20))),
        RiskFreeRate(**common, version=3, rate=Decimal("0.022"), **_times(_utc(9, 1))),
    ])
    db_session.flush()

    points = _context(db_session).risk_free_rates().series(
        "CNY", "1Y", dt.date(2026, 8, 1), dt.date(2026, 8, 31)
    )

    assert len(points) == 1
    assert points[0].version == 2
    assert points[0].rate == Decimal("0.02100000")
