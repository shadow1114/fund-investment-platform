from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TenorRate:
    currency: str
    days: int
    rate: Decimal


def interpolate_rate(
    lower: TenorRate, upper: TenorRate, target_days: int
) -> Decimal:
    if lower.currency != upper.currency:
        raise ValueError("cannot interpolate rates across currency")
    if lower.days >= upper.days:
        raise ValueError("lower tenor must be shorter than upper tenor")
    if not lower.days <= target_days <= upper.days:
        raise ValueError("target tenor must be between adjacent tenors")
    if target_days == lower.days:
        return lower.rate
    if target_days == upper.days:
        return upper.rate
    weight = Decimal(target_days - lower.days) / Decimal(upper.days - lower.days)
    return lower.rate + (upper.rate - lower.rate) * weight
