"""Pure inventory rules (no I/O)."""

from enum import Enum


class AdjustmentReason(str, Enum):
    # Reasons a user may choose when adjusting stock manually.
    RECEIVED = "RECEIVED"  # new stock arrived            (+)
    RETURNED = "RETURNED"  # customer return restocked    (+)
    DAMAGED = "DAMAGED"  # damaged / lost / expired       (-)
    CORRECTION = "CORRECTION"  # stock-count correction   (+ or -)
    OTHER = "OTHER"  # anything else, note is mandatory   (+ or -)
    # Written by the system only; they cannot be chosen through the adjustment endpoint.
    INITIAL_STOCK = "INITIAL_STOCK"
    ORDER_RESERVED = "ORDER_RESERVED"
    ORDER_CANCELLED = "ORDER_CANCELLED"


MANUAL_REASONS = (
    AdjustmentReason.RECEIVED,
    AdjustmentReason.RETURNED,
    AdjustmentReason.DAMAGED,
    AdjustmentReason.CORRECTION,
    AdjustmentReason.OTHER,
)

_MUST_INCREASE = {AdjustmentReason.RECEIVED, AdjustmentReason.RETURNED}
_MUST_DECREASE = {AdjustmentReason.DAMAGED}


def manual_adjustment_problem(reason: AdjustmentReason, quantity_change: int, note: str | None) -> str | None:
    """Return a human-readable problem with a manual adjustment, or None if it is acceptable."""
    if reason not in MANUAL_REASONS:
        return f"Reason {reason.value} is reserved for system-generated movements"
    if quantity_change == 0:
        return "Quantity change must not be zero"
    if reason in _MUST_INCREASE and quantity_change < 0:
        return f"Reason {reason.value} requires a positive quantity change"
    if reason in _MUST_DECREASE and quantity_change > 0:
        return f"Reason {reason.value} requires a negative quantity change"
    if reason is AdjustmentReason.OTHER and not (note and note.strip()):
        return "A note is required when the reason is OTHER"
    return None


def new_stock_level(current: int, quantity_change: int) -> int:
    return current + quantity_change
