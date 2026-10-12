"""Money arithmetic. Decimal only - never floats."""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    return money(Decimal(unit_price) * quantity)


def order_total(line_totals: Iterable[Decimal]) -> Decimal:
    return money(sum(line_totals, ZERO))
