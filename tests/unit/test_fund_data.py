import datetime as dt
from decimal import Decimal

from fip.platform.decision_data.pit import FeePoint
from fip.strategy_library.fund_data import expense_ratio


def _fee(fee_type: str, rate: str) -> FeePoint:
    return FeePoint(fee_type, Decimal(rate), dt.date(2026, 1, 1), "EXACT")


def test_expense_ratio_sums_only_recurring_expense_types():
    fees = [
        _fee("management", "0.010"),
        _fee("custodian", "0.002"),
        _fee("sales-service", "0.003"),
        _fee("subscription", "0.015"),
        _fee("redemption", "0.005"),
    ]

    assert expense_ratio(fees) == Decimal("0.015")


def test_expense_ratio_of_no_recurring_fees_is_zero():
    assert expense_ratio([_fee("subscription", "0.01")]) == Decimal(0)
