import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.inventory_rules import AdjustmentReason
from app.models import InventoryAdjustment
from app.repositories.common import paginate, utc_bounds
from app.schemas.common import DateRange, PageParams


def list_adjustments(
    db: Session,
    workspace_id: uuid.UUID,
    params: PageParams,
    date_range: DateRange,
    *,
    product_id: uuid.UUID | None = None,
    reason: AdjustmentReason | None = None,
) -> tuple[list[InventoryAdjustment], int]:
    stmt = select(InventoryAdjustment).where(InventoryAdjustment.workspace_id == workspace_id)
    if product_id:
        stmt = stmt.where(InventoryAdjustment.product_id == product_id)
    if reason:
        stmt = stmt.where(InventoryAdjustment.reason == reason.value)
    start, end = utc_bounds(date_range)
    if start:
        stmt = stmt.where(InventoryAdjustment.created_at >= start)
    if end:
        stmt = stmt.where(InventoryAdjustment.created_at < end)
    stmt = stmt.order_by(InventoryAdjustment.created_at.desc(), InventoryAdjustment.id)
    return paginate(db, stmt, params)


def recent(db: Session, workspace_id: uuid.UUID, limit: int) -> list[InventoryAdjustment]:
    stmt = (
        select(InventoryAdjustment)
        .where(InventoryAdjustment.workspace_id == workspace_id)
        .order_by(InventoryAdjustment.created_at.desc(), InventoryAdjustment.id)
        .limit(limit)
    )
    return list(db.scalars(stmt).unique().all())
