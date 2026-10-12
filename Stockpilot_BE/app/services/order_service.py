"""Order business rules.

Stock strategy: RESERVE AT CREATION.
  * create   -> every line's stock is deducted immediately (status PENDING)
  * confirm  -> no stock effect
  * complete -> no stock effect (the deduction stays)
  * cancel   -> every line's stock is restored, exactly once

Concurrency model: all stock-touching paths lock the rows involved with SELECT ... FOR UPDATE
(products in primary-key order, so concurrent multi-item orders cannot deadlock; the order row
first when cancelling). The stock check and the deduction therefore happen under the lock, and the
CHECK (stock_quantity >= 0) constraint is a second line of defence.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import WorkspaceContext
from app.core.errors import AppError, ConflictError, NotFoundError, ValidationFailedError
from app.db.unit_of_work import unit_of_work, violated_constraint
from app.domain.inventory_rules import AdjustmentReason
from app.domain.order_rules import OrderStatus, can_transition, merge_items, restores_stock
from app.domain.pricing import ZERO, line_total, order_total
from app.models import Order, OrderItem
from app.repositories import orders as order_repo
from app.repositories import products as product_repo
from app.repositories.common import utc_bounds
from app.schemas.common import DateRange, PageParams
from app.schemas.order import OrderCreate, OrderSort
from app.schemas.product import SortDir
from app.services.inventory_service import apply_stock_change

_IDEMPOTENCY_INDEX = "uq_orders_workspace_id_idempotency_key"

_TIMESTAMP_FOR_STATUS = {
    OrderStatus.CONFIRMED: "confirmed_at",
    OrderStatus.COMPLETED: "completed_at",
    OrderStatus.CANCELLED: "cancelled_at",
}


def create_order(
    db: Session, ctx: WorkspaceContext, data: OrderCreate, idempotency_key: str | None = None
) -> tuple[Order, bool]:
    """Create a PENDING order and reserve stock. Returns (order, created).

    `created` is False when the same Idempotency-Key was already used: the original order is
    returned and nothing is written, so a retried request cannot double-book stock."""
    if idempotency_key:
        existing = order_repo.get_by_idempotency_key(db, ctx.workspace_id, idempotency_key)
        if existing:
            return existing, False

    try:
        order_id = _create_order_tx(db, ctx, data, idempotency_key)
    except IntegrityError as exc:
        if idempotency_key and violated_constraint(exc) == _IDEMPOTENCY_INDEX:
            # A concurrent request with the same key won the race; hand back its order.
            existing = order_repo.get_by_idempotency_key(db, ctx.workspace_id, idempotency_key)
            if existing:
                return existing, False
        raise
    return _load(db, ctx, order_id), True


def _create_order_tx(db: Session, ctx: WorkspaceContext, data: OrderCreate, idempotency_key: str | None) -> uuid.UUID:
    requested = merge_items((item.product_id, item.quantity) for item in data.items)

    with unit_of_work(db):  # all-or-nothing: order, lines, stock deduction and audit rows
        products = product_repo.lock_many(db, ctx.workspace_id, sorted(requested))

        problems = _find_problems(requested, products)
        if problems:
            raise _order_error(problems)

        order = Order(
            id=uuid.uuid4(),
            workspace_id=ctx.workspace_id,
            created_by=ctx.user.id,
            status=OrderStatus.PENDING.value,
            total_amount=ZERO,
            notes=data.notes,
            idempotency_key=idempotency_key,
        )
        db.add(order)
        db.flush()

        totals = []
        for product_id, quantity in requested.items():
            product = products[product_id]
            total = line_total(product.unit_price, quantity)  # price comes from the DB, never the client
            totals.append(total)
            db.add(
                OrderItem(
                    order_id=order.id,
                    workspace_id=ctx.workspace_id,
                    product_id=product.id,
                    product_name=product.name,  # snapshots: later edits to the product don't touch history
                    sku=product.sku,
                    unit_price=product.unit_price,
                    quantity=quantity,
                    line_total=total,
                )
            )
        order.total_amount = order_total(totals)
        db.flush()

        for product_id, quantity in requested.items():
            apply_stock_change(
                db,
                products[product_id],
                ctx=ctx,
                quantity_change=-quantity,
                reason=AdjustmentReason.ORDER_RESERVED,
                order_id=order.id,
            )
    return order.id


def _find_problems(requested: dict[uuid.UUID, int], products: dict[uuid.UUID, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for product_id, quantity in requested.items():
        product = products.get(product_id)
        base = {"product_id": str(product_id)}
        if product is None:
            # Same answer for "does not exist" and "belongs to another workspace": no information leak.
            problems.append({**base, "code": "PRODUCT_NOT_FOUND", "message": "Product not found in this workspace"})
        elif not product.is_active:
            problems.append(
                {**base, "sku": product.sku, "code": "PRODUCT_INACTIVE", "message": f"{product.name} is inactive"}
            )
        elif product.stock_quantity < quantity:
            problems.append(
                {
                    **base,
                    "sku": product.sku,
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"{product.name}: requested {quantity}, only {product.stock_quantity} available",
                    "available": product.stock_quantity,
                    "requested": quantity,
                }
            )
    return problems


def _order_error(problems: list[dict[str, Any]]) -> AppError:
    if all(p["code"] == "INSUFFICIENT_STOCK" for p in problems):
        return ConflictError(
            "Insufficient stock for one or more items; no order was created",
            code="INSUFFICIENT_STOCK",
            details=problems,
        )
    return ValidationFailedError(
        "One or more items cannot be ordered; no order was created", code="INVALID_ORDER_ITEMS", details=problems
    )


def get_order(db: Session, ctx: WorkspaceContext, order_id: uuid.UUID) -> Order:
    return _load(db, ctx, order_id)


def list_orders(
    db: Session,
    ctx: WorkspaceContext,
    params: PageParams,
    date_range: DateRange,
    *,
    status: OrderStatus | None,
    q: str | None,
    sort_by: OrderSort,
    sort_dir: SortDir,
) -> tuple[list[Order], int]:
    start, end = utc_bounds(date_range)
    return order_repo.search(
        db, ctx.workspace_id, params, status=status, start=start, end=end, q=q, sort_by=sort_by, sort_dir=sort_dir
    )


def change_status(db: Session, ctx: WorkspaceContext, order_id: uuid.UUID, target: OrderStatus) -> Order:
    with unit_of_work(db):
        # Row lock: a second (retried / concurrent) request waits here and then sees the new status.
        order = order_repo.get_for_update(db, ctx.workspace_id, order_id)
        if order is None:
            raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")

        current = OrderStatus(order.status)
        if not can_transition(current, target):
            raise ConflictError(
                f"Cannot change an order from {current.value} to {target.value}",
                code="INVALID_TRANSITION",
                details=[{"from": current.value, "to": target.value}],
            )

        if restores_stock(target):
            _restore_stock(db, ctx, order)

        order.status = target.value
        setattr(order, _TIMESTAMP_FOR_STATUS[target], datetime.now(timezone.utc))
    return _load(db, ctx, order_id)


def _restore_stock(db: Session, ctx: WorkspaceContext, order: Order) -> None:
    """Give every line's quantity back. Runs only on a legal CANCELLED transition while holding the
    order lock; the unique index on (order_id, product_id, reason) is the database-level backstop
    that makes a second restoration impossible."""
    items = sorted(order.items, key=lambda item: item.product_id)
    products = product_repo.lock_many(db, ctx.workspace_id, [item.product_id for item in items])
    for item in items:
        apply_stock_change(
            db,
            products[item.product_id],
            ctx=ctx,
            quantity_change=item.quantity,
            reason=AdjustmentReason.ORDER_CANCELLED,
            order_id=order.id,
        )


def _load(db: Session, ctx: WorkspaceContext, order_id: uuid.UUID) -> Order:
    order = order_repo.get(db, ctx.workspace_id, order_id)
    if order is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    return order
