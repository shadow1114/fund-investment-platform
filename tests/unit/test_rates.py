from decimal import Decimal

import pytest

from fip.strategy_library.rates import TenorRate, interpolate_rate


def test_interpolate_rate_is_linear_between_adjacent_tenors():
    lower = TenorRate("CNY", 90, Decimal("0.020"))
    upper = TenorRate("CNY", 180, Decimal("0.026"))

    assert interpolate_rate(lower, upper, 120) == Decimal("0.022")


def test_interpolate_rate_returns_exact_endpoint():
    lower = TenorRate("CNY", 90, Decimal("0.020"))
    upper = TenorRate("CNY", 180, Decimal("0.026"))

    assert interpolate_rate(lower, upper, 90) == lower.rate


def test_interpolate_rate_rejects_cross_currency_input():
    with pytest.raises(ValueError, match="currency"):
        interpolate_rate(
            TenorRate("CNY", 90, Decimal("0.020")),
            TenorRate("USD", 180, Decimal("0.026")),
            120,
        )


@pytest.mark.parametrize("target", [89, 181])
def test_interpolate_rate_does_not_extrapolate(target):
    with pytest.raises(ValueError, match="between"):
        interpolate_rate(
            TenorRate("CNY", 90, Decimal("0.020")),
            TenorRate("CNY", 180, Decimal("0.026")),
            target,
        )
