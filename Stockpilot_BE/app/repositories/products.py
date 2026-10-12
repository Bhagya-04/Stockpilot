import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Product
from app.repositories.common import escape_like, paginate
from app.schemas.common import PageParams
from app.schemas.product import ActiveFilter, ProductSort, SortDir

# Every query below is scoped by workspace_id: a product id from another workspace simply "does not exist".


def get(db: Session, workspace_id: uuid.UUID, product_id: uuid.UUID) -> Product | None:
    return db.scalar(select(Product).where(Product.id == product_id, Product.workspace_id == workspace_id))


def get_for_update(db: Session, workspace_id: uuid.UUID, product_id: uuid.UUID) -> Product | None:
    """Row-lock the product until the transaction ends. populate_existing makes sure we see the
    committed value that was current when the lock was granted, not a stale identity-map copy."""
    stmt = (
        select(Product)
        .where(Product.id == product_id, Product.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(stmt)


def lock_many(db: Session, workspace_id: uuid.UUID, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Product]:
    """Lock several products in a fixed (id) order so concurrent multi-item orders cannot deadlock."""
    stmt = (
        select(Product)
        .where(Product.workspace_id == workspace_id, Product.id.in_(list(product_ids)))
        .order_by(Product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {product.id: product for product in db.scalars(stmt).all()}


def sku_exists(db: Session, workspace_id: uuid.UUID, sku: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Product.id).where(Product.workspace_id == workspace_id, Product.sku == sku)
    if exclude_id:
        stmt = stmt.where(Product.id != exclude_id)
    return db.scalar(stmt.limit(1)) is not None


_SORT_COLUMNS = {
    ProductSort.name: Product.name,
    ProductSort.sku: Product.sku,
    ProductSort.unit_price: Product.unit_price,
    ProductSort.stock_quantity: Product.stock_quantity,
    ProductSort.created_at: Product.created_at,
    ProductSort.updated_at: Product.updated_at,
}


def search(
    db: Session,
    workspace_id: uuid.UUID,
    params: PageParams,
    *,
    q: str | None,
    sku: str | None,
    active: ActiveFilter,
    low_stock: bool | None,
    sort_by: ProductSort,
    sort_dir: SortDir,
) -> tuple[list[Product], int]:
    stmt = select(Product).where(Product.workspace_id == workspace_id)
    if q and q.strip():
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern, escape="\\"), Product.sku.ilike(pattern, escape="\\")))
    if sku and sku.strip():
        stmt = stmt.where(func.upper(Product.sku) == sku.strip().upper())
    if active is ActiveFilter.active:
        stmt = stmt.where(Product.is_active.is_(True))
    elif active is ActiveFilter.inactive:
        stmt = stmt.where(Product.is_active.is_(False))
    if low_stock is not None:
        # Same definition as Product.is_low_stock and the dashboard: active AND stock <= threshold.
        is_low = (Product.is_active.is_(True)) & (Product.stock_quantity <= Product.low_stock_threshold)
        stmt = stmt.where(is_low if low_stock else ~is_low)

    column = _SORT_COLUMNS[sort_by]
    ordering = column.asc() if sort_dir is SortDir.asc else column.desc()
    stmt = stmt.order_by(ordering, Product.id)  # id as a tie-breaker keeps pagination stable
    return paginate(db, stmt, params)


def count_active(db: Session, workspace_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(Product.workspace_id == workspace_id, Product.is_active.is_(True))
    return db.scalar(stmt) or 0


def count_low_stock(db: Session, workspace_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(
        Product.workspace_id == workspace_id,
        Product.is_active.is_(True),
        Product.stock_quantity <= Product.low_stock_threshold,
    )
    return db.scalar(stmt) or 0
