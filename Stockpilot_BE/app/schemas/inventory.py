from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.inventory_rules import AdjustmentReason
from app.schemas.common import ORMModel, UserRef
from app.schemas.product import ProductOut


class AdjustmentCreate(BaseModel):
    quantity_change: int = Field(ge=-10_000_000, le=10_000_000, description="Positive adds stock, negative removes it")
    reason: AdjustmentReason
    note: str | None = Field(default=None, max_length=500)


class ProductRef(ORMModel):
    id: UUID
    name: str
    sku: str


class AdjustmentOut(ORMModel):
    id: UUID
    workspace_id: UUID
    product: ProductRef
    order_id: UUID | None
    user: UserRef
    quantity_change: int
    resulting_stock: int
    reason: AdjustmentReason
    note: str | None
    created_at: datetime


class AdjustmentResult(BaseModel):
    """Returned after a manual adjustment: the new ledger entry and the product's updated stock."""

    adjustment: AdjustmentOut
    product: ProductOut
