import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.domain.order_rules import VALUE_COUNTING_STATUSES, OrderStatus, parse_order_number
from app.models import Order
from app.repositories.common import paginate
from app.schemas.common import PageParams
from app.schemas.order import OrderSort
from app.schemas.product import SortDir

# Every query is scoped by workspace_id so an order id from another workspace is simply not found.


def get(db: Session, workspace_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.workspace_id == workspace_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(stmt)


def get_for_update(db: Session, workspace_id: uuid.UUID, order_id: uuid.UUID) -> Order | None:
    """Lock the order row. Concurrent confirm/complete/cancel requests on the same order queue up
    here, so each one sees the status written by the one before it."""
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.workspace_id == workspace_id)
        .with_for_update(of=Order)
        .execution_options(populate_existing=True)
    )
    return db.scalar(stmt)


def get_by_idempotency_key(db: Session, workspace_id: uuid.UUID, key: str) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.workspace_id == workspace_id, Order.idempotency_key == key)
        .execution_options(populate_existing=True)
    )
    return db.scalar(stmt)


_SORT_COLUMNS = {
    OrderSort.created_at: Order.created_at,
    OrderSort.total_amount: Order.total_amount,
    OrderSort.status: Order.status,
    OrderSort.order_number: Order.order_number,
}


def search(
    db: Session,
    workspace_id: uuid.UUID,
    params: PageParams,
    *,
    status: OrderStatus | None,
    start: datetime | None,
    end: datetime | None,
    q: str | None,
    sort_by: OrderSort,
    sort_dir: SortDir,
) -> tuple[list[Order], int]:
    stmt = select(Order).where(Order.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(Order.status == status.value)
    if start:
        stmt = stmt.where(Order.created_at >= start)
    if end:
        stmt = stmt.where(Order.created_at < end)
    if q and q.strip():
        stmt = stmt.where(_identifier_filter(q))

    column = _SORT_COLUMNS[sort_by]
    ordering = column.asc() if sort_dir is SortDir.asc else column.desc()
    stmt = stmt.order_by(ordering, Order.id)
    return paginate(db, stmt, params)


def _identifier_filter(q: str):
    """Match an order by UUID or by its human order number (ORD-000123 / 123)."""
    try:
        return Order.id == uuid.UUID(q.strip())
    except ValueError:
        pass
    number = parse_order_number(q)
    return Order.order_number == number if number is not None else false()


def recent(db: Session, workspace_id: uuid.UUID, limit: int) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.workspace_id == workspace_id)
        .order_by(Order.created_at.desc(), Order.id)
        .limit(limit)
    )
    return list(db.scalars(stmt).unique().all())


def counts_by_status(db: Session, workspace_id: uuid.UUID, start: datetime, end: datetime) -> dict[str, int]:
    stmt = (
        select(Order.status, func.count())
        .where(Order.workspace_id == workspace_id, Order.created_at >= start, Order.created_at < end)
        .group_by(Order.status)
    )
    counts = {status.value: 0 for status in OrderStatus}
    counts.update({status: count for status, count in db.execute(stmt).all()})
    return counts


def value_in_range(
    db: Session,
    workspace_id: uuid.UUID,
    start: datetime,
    end: datetime,
    statuses: tuple[OrderStatus, ...] = VALUE_COUNTING_STATUSES,
) -> Decimal:
    stmt = select(func.coalesce(func.sum(Order.total_amount), 0)).where(
        Order.workspace_id == workspace_id,
        Order.created_at >= start,
        Order.created_at < end,
        Order.status.in_([s.value for s in statuses]),
    )
    return Decimal(db.scalar(stmt) or 0)
