import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import WorkspaceContext
from app.core.errors import ConflictError, NotFoundError
from app.db.unit_of_work import unit_of_work, violated_constraint
from app.domain.inventory_rules import AdjustmentReason
from app.models import InventoryAdjustment, Product
from app.repositories import products as product_repo
from app.schemas.common import PageParams
from app.schemas.product import ActiveFilter, ProductCreate, ProductSort, ProductUpdate, SortDir

_SKU_CONSTRAINT = "uq_products_workspace_id_sku"


def _duplicate_sku(sku: str) -> ConflictError:
    return ConflictError(
        f"A product with SKU {sku} already exists in this workspace",
        code="DUPLICATE_SKU",
        details=[{"field": "sku", "message": "SKU already exists in this workspace"}],
    )


def create_product(db: Session, ctx: WorkspaceContext, data: ProductCreate) -> Product:
    if product_repo.sku_exists(db, ctx.workspace_id, data.sku):
        raise _duplicate_sku(data.sku)
    product = Product(
        workspace_id=ctx.workspace_id,
        name=data.name,
        sku=data.sku,
        description=data.description,
        unit_price=data.unit_price,
        stock_quantity=data.stock_quantity,
        low_stock_threshold=data.low_stock_threshold,
        is_active=data.is_active,
    )
    try:
        with unit_of_work(db):
            db.add(product)
            db.flush()
            if data.stock_quantity > 0:
                # The opening balance is part of the audit trail like any other stock change.
                db.add(
                    InventoryAdjustment(
                        workspace_id=ctx.workspace_id,
                        product=product,
                        user_id=ctx.user.id,
                        quantity_change=data.stock_quantity,
                        resulting_stock=data.stock_quantity,
                        reason=AdjustmentReason.INITIAL_STOCK.value,
                        note="Opening balance",
                    )
                )
    except IntegrityError as exc:
        if violated_constraint(exc) == _SKU_CONSTRAINT:  # lost a race with a concurrent create
            raise _duplicate_sku(data.sku) from None
        raise
    return product


def get_product(db: Session, ctx: WorkspaceContext, product_id: uuid.UUID) -> Product:
    product = product_repo.get(db, ctx.workspace_id, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return product


def update_product(db: Session, ctx: WorkspaceContext, product_id: uuid.UUID, data: ProductUpdate) -> Product:
    changes = data.model_dump(exclude_unset=True)
    try:
        with unit_of_work(db):
            # Locked so a price/active change is serialised with in-flight order creation.
            product = product_repo.get_for_update(db, ctx.workspace_id, product_id)
            if product is None:
                raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
            new_sku = changes.get("sku")
            if new_sku and new_sku != product.sku and product_repo.sku_exists(
                db, ctx.workspace_id, new_sku, exclude_id=product.id
            ):
                raise _duplicate_sku(new_sku)
            for field, value in changes.items():
                setattr(product, field, value)
    except IntegrityError as exc:
        if violated_constraint(exc) == _SKU_CONSTRAINT:
            raise _duplicate_sku(changes.get("sku", "")) from None
        raise
    return product


def list_products(
    db: Session,
    ctx: WorkspaceContext,
    params: PageParams,
    *,
    q: str | None,
    sku: str | None,
    active: ActiveFilter,
    low_stock: bool | None,
    sort_by: ProductSort,
    sort_dir: SortDir,
) -> tuple[list[Product], int]:
    return product_repo.search(
        db,
        ctx.workspace_id,
        params,
        q=q,
        sku=sku,
        active=active,
        low_stock=low_stock,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
