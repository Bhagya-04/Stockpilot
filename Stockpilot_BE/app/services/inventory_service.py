import uuid

from sqlalchemy.orm import Session

from app.core.context import WorkspaceContext
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.db.unit_of_work import unit_of_work
from app.domain.inventory_rules import AdjustmentReason, manual_adjustment_problem, new_stock_level
from app.models import InventoryAdjustment, Product
from app.repositories import inventory as inventory_repo
from app.repositories import products as product_repo
from app.schemas.common import DateRange, PageParams
from app.schemas.inventory import AdjustmentCreate


def apply_stock_change(
    db: Session,
    product: Product,
    *,
    ctx: WorkspaceContext,
    quantity_change: int,
    reason: AdjustmentReason,
    note: str | None = None,
    order_id: uuid.UUID | None = None,
) -> InventoryAdjustment:
    """The ONLY place stock is mutated. It changes products.stock_quantity and appends the matching
    ledger row in the same unit of work, so current stock and history can never disagree.

    Precondition: `product` was loaded with SELECT ... FOR UPDATE inside the current transaction.
    """
    new_stock = new_stock_level(product.stock_quantity, quantity_change)
    if new_stock < 0:
        raise ConflictError(
            f"Insufficient stock for {product.sku}: {product.stock_quantity} available, "
            f"change of {quantity_change} would make stock negative",
            code="INSUFFICIENT_STOCK",
            details=[
                {
                    "product_id": str(product.id),
                    "sku": product.sku,
                    "available": product.stock_quantity,
                    "requested": -quantity_change,
                }
            ],
        )
    product.stock_quantity = new_stock
    entry = InventoryAdjustment(
        workspace_id=product.workspace_id,
        product=product,
        order_id=order_id,
        user_id=ctx.user.id,
        quantity_change=quantity_change,
        resulting_stock=new_stock,
        reason=reason.value,
        note=note,
    )
    db.add(entry)
    return entry


def adjust_stock(
    db: Session, ctx: WorkspaceContext, product_id: uuid.UUID, data: AdjustmentCreate
) -> tuple[InventoryAdjustment, Product]:
    problem = manual_adjustment_problem(data.reason, data.quantity_change, data.note)
    if problem:
        raise ValidationFailedError(
            problem, code="INVALID_ADJUSTMENT", details=[{"field": "quantity_change", "message": problem}]
        )
    note = data.note.strip() if data.note and data.note.strip() else None
    with unit_of_work(db):
        product = product_repo.get_for_update(db, ctx.workspace_id, product_id)
        if product is None:
            raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
        entry = apply_stock_change(
            db, product, ctx=ctx, quantity_change=data.quantity_change, reason=data.reason, note=note
        )
    return entry, product


def list_adjustments(
    db: Session,
    ctx: WorkspaceContext,
    params: PageParams,
    date_range: DateRange,
    *,
    product_id: uuid.UUID | None = None,
    reason: AdjustmentReason | None = None,
) -> tuple[list[InventoryAdjustment], int]:
    if product_id and product_repo.get(db, ctx.workspace_id, product_id) is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return inventory_repo.list_adjustments(
        db, ctx.workspace_id, params, date_range, product_id=product_id, reason=reason
    )
