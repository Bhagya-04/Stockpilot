from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.order_rules import OrderStatus
from app.schemas.common import ORMModel, UserRef

MAX_LINE_QUANTITY = 1_000_000
MAX_ITEMS_PER_ORDER = 50


class OrderItemIn(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=MAX_LINE_QUANTITY)


class OrderCreate(BaseModel):
    """Only product ids + quantities are accepted. Prices and totals are always computed by the
    server; any `unit_price`, `total` etc. sent by the client is ignored."""

    items: list[OrderItemIn] = Field(min_length=1, max_length=MAX_ITEMS_PER_ORDER)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def _blank_notes_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class OrderItemOut(ORMModel):
    id: UUID
    product_id: UUID
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class OrderOut(ORMModel):
    id: UUID
    order_number: int
    display_number: str
    workspace_id: UUID
    status: OrderStatus
    total_amount: Decimal
    notes: str | None
    creator: UserRef
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    items: list[OrderItemOut]


class OrderSort(str, Enum):
    created_at = "created_at"
    total_amount = "total_amount"
    status = "status"
    order_number = "order_number"
