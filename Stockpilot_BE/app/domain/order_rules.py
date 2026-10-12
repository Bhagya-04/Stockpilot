"""Pure order rules (no I/O): lifecycle, transitions and item merging."""

import uuid
from collections.abc import Iterable
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# Stock strategy: stock is RESERVED (deducted) when the order is created.
#   PENDING   -> CONFIRMED : no stock effect
#   CONFIRMED -> COMPLETED : no stock effect (deduction is kept)
#   PENDING/CONFIRMED -> CANCELLED : stock is restored, exactly once
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

# Statuses whose value counts as "order value" on the dashboard (everything except cancelled).
VALUE_COUNTING_STATUSES = (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.COMPLETED)


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def restores_stock(target: OrderStatus) -> bool:
    return target is OrderStatus.CANCELLED


def merge_items(items: Iterable[tuple[uuid.UUID, int]]) -> dict[uuid.UUID, int]:
    """Combine duplicate products into a single line by summing quantities (first-seen order is kept)."""
    merged: dict[uuid.UUID, int] = {}
    for product_id, quantity in items:
        merged[product_id] = merged.get(product_id, 0) + quantity
    return merged


def format_order_number(order_number: int) -> str:
    return f"ORD-{order_number:06d}"


def parse_order_number(text: str) -> int | None:
    """Accepts 'ORD-000123', 'ord-123' or '123'."""
    cleaned = text.strip().upper()
    if cleaned.startswith("ORD-"):
        cleaned = cleaned[4:]
    if cleaned.isdigit() and len(cleaned) <= 18:
        return int(cleaned)
    return None
