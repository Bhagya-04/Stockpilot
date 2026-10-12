import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.api.deps import DbSession, require
from app.core.context import WorkspaceContext
from app.core.permissions import Permission
from app.domain.order_rules import OrderStatus
from app.schemas.common import DateRangeDep, Page, PageDep, make_page
from app.schemas.order import OrderCreate, OrderOut, OrderSort
from app.schemas.product import SortDir
from app.services import order_service

router = APIRouter(prefix="/workspaces/{workspace_id}/orders", tags=["orders"])

Reader = Annotated[WorkspaceContext, Depends(require(Permission.ORDER_READ))]
Creator = Annotated[WorkspaceContext, Depends(require(Permission.ORDER_CREATE))]
Updater = Annotated[WorkspaceContext, Depends(require(Permission.ORDER_UPDATE))]


@router.get("", response_model=Page[OrderOut])
def list_orders(
    ctx: Reader,
    db: DbSession,
    page: PageDep,
    dates: DateRangeDep,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=64, description="Order id (UUID) or number, e.g. ORD-000123")] = None,
    sort_by: OrderSort = OrderSort.created_at,
    sort_dir: SortDir = SortDir.desc,
) -> Page[OrderOut]:
    rows, total = order_service.list_orders(
        db, ctx, page, dates, status=status_filter, q=q, sort_by=sort_by, sort_dir=sort_dir
    )
    return make_page(rows, OrderOut, total, page)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    ctx: Creator,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=64,
            pattern=r"^[A-Za-z0-9_.:-]+$",
            description="Optional. Retrying with the same key returns the original order instead of creating a new one.",
        ),
    ] = None,
) -> OrderOut:
    order, created = order_service.create_order(db, ctx, data, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK  # replay of an earlier identical request
    return OrderOut.model_validate(order)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, ctx: Reader, db: DbSession) -> OrderOut:
    return OrderOut.model_validate(order_service.get_order(db, ctx, order_id))


def _transition(order_id: uuid.UUID, ctx: WorkspaceContext, db: DbSession, target: OrderStatus) -> OrderOut:
    return OrderOut.model_validate(order_service.change_status(db, ctx, order_id, target))


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order(order_id: uuid.UUID, ctx: Updater, db: DbSession) -> OrderOut:
    """PENDING -> CONFIRMED (no stock effect)."""
    return _transition(order_id, ctx, db, OrderStatus.CONFIRMED)


@router.post("/{order_id}/complete", response_model=OrderOut)
def complete_order(order_id: uuid.UUID, ctx: Updater, db: DbSession) -> OrderOut:
    """CONFIRMED -> COMPLETED (no stock effect; the reservation is kept)."""
    return _transition(order_id, ctx, db, OrderStatus.COMPLETED)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: uuid.UUID, ctx: Updater, db: DbSession) -> OrderOut:
    """PENDING/CONFIRMED -> CANCELLED. Restores reserved stock exactly once; repeating it returns 409."""
    return _transition(order_id, ctx, db, OrderStatus.CANCELLED)
