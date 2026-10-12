import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require
from app.core.context import WorkspaceContext
from app.core.permissions import Permission
from app.domain.inventory_rules import AdjustmentReason
from app.schemas.common import DateRangeDep, Page, PageDep, make_page
from app.schemas.inventory import AdjustmentCreate, AdjustmentOut, AdjustmentResult
from app.schemas.product import (
    ActiveFilter,
    ProductCreate,
    ProductOut,
    ProductSort,
    ProductUpdate,
    SortDir,
)
from app.services import inventory_service, product_service

router = APIRouter(prefix="/workspaces/{workspace_id}/products", tags=["products"])

Reader = Annotated[WorkspaceContext, Depends(require(Permission.PRODUCT_READ))]
Writer = Annotated[WorkspaceContext, Depends(require(Permission.PRODUCT_WRITE))]


@router.get("", response_model=Page[ProductOut])
def list_products(
    ctx: Reader,
    db: DbSession,
    page: PageDep,
    q: Annotated[str | None, Query(max_length=100, description="Search name or SKU")] = None,
    sku: Annotated[str | None, Query(max_length=64, description="Exact SKU (case-insensitive)")] = None,
    active: ActiveFilter = ActiveFilter.all,
    low_stock: Annotated[bool | None, Query(description="true = only low-stock, false = only not-low-stock")] = None,
    sort_by: ProductSort = ProductSort.name,
    sort_dir: SortDir = SortDir.asc,
) -> Page[ProductOut]:
    rows, total = product_service.list_products(
        db, ctx, page, q=q, sku=sku, active=active, low_stock=low_stock, sort_by=sort_by, sort_dir=sort_dir
    )
    return make_page(rows, ProductOut, total, page)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, ctx: Writer, db: DbSession) -> ProductOut:
    return ProductOut.model_validate(product_service.create_product(db, ctx, data))


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: uuid.UUID, ctx: Reader, db: DbSession) -> ProductOut:
    return ProductOut.model_validate(product_service.get_product(db, ctx, product_id))


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: uuid.UUID, data: ProductUpdate, ctx: Writer, db: DbSession) -> ProductOut:
    """Edit details, change the price, or (de)activate with {"is_active": false}.
    Stock cannot be edited here - use POST .../adjustments."""
    return ProductOut.model_validate(product_service.update_product(db, ctx, product_id, data))


@router.post(
    "/{product_id}/adjustments", response_model=AdjustmentResult, status_code=status.HTTP_201_CREATED
)
def adjust_stock(
    product_id: uuid.UUID,
    data: AdjustmentCreate,
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.INVENTORY_ADJUST))],
    db: DbSession,
) -> AdjustmentResult:
    entry, product = inventory_service.adjust_stock(db, ctx, product_id, data)
    return AdjustmentResult(
        adjustment=AdjustmentOut.model_validate(entry), product=ProductOut.model_validate(product)
    )


@router.get("/{product_id}/adjustments", response_model=Page[AdjustmentOut])
def list_product_adjustments(
    product_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.INVENTORY_READ))],
    db: DbSession,
    page: PageDep,
    dates: DateRangeDep,
    reason: AdjustmentReason | None = None,
) -> Page[AdjustmentOut]:
    rows, total = inventory_service.list_adjustments(db, ctx, page, dates, product_id=product_id, reason=reason)
    return make_page(rows, AdjustmentOut, total, page)
