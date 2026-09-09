from collections.abc import Sequence
from decimal import Decimal

from fip.platform.decision_data.pit import FeePoint

_EXPENSE_FEE_TYPES = frozenset({"management", "custodian", "sales-service"})


def expense_ratio(fees: Sequence[FeePoint]) -> Decimal:
    return sum(
        (fee.rate for fee in fees if fee.fee_type in _EXPENSE_FEE_TYPES),
        start=Decimal(0),
    )
