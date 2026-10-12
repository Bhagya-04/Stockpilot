import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import Money, ORMModel, StockInt

_SKU_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/-]*$")


def _normalise_sku(value: str) -> str:
    sku = value.strip().upper()
    if not sku:
        raise ValueError("SKU is required")
    if len(sku) > 64:
        raise ValueError("SKU must be at most 64 characters")
    if not _SKU_PATTERN.match(sku):
        raise ValueError("SKU may only contain letters, digits and . _ / - (and must start with a letter or digit)")
    return sku


def _normalise_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("Name is required")
    return name


class ProductCreate(BaseModel):
    name: str = Field(max_length=200)
    sku: str
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Money
    # Opening balance. If > 0 it is recorded as an INITIAL_STOCK entry in the inventory history.
    stock_quantity: StockInt = 0
    low_stock_threshold: StockInt = 0
    is_active: bool = True

    _name = field_validator("name")(_normalise_name)
    _sku = field_validator("sku")(_normalise_sku)


class ProductUpdate(BaseModel):
    """Partial update. stock_quantity is intentionally NOT editable here - use the adjustment
    endpoint so every stock change is audited. Unknown fields are rejected with a 422."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    sku: str | None = None
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Money | None = None
    low_stock_threshold: StockInt | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_nulled(self) -> "ProductUpdate":
        for field in ("name", "sku", "unit_price", "low_stock_threshold", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _normalise_name(value)

    @field_validator("sku")
    @classmethod
    def _sku(cls, value: str | None) -> str | None:
        return None if value is None else _normalise_sku(value)


class ProductOut(ORMModel):
    id: UUID
    workspace_id: UUID
    name: str
    sku: str
    description: str | None
    unit_price: Decimal
    stock_quantity: int
    low_stock_threshold: int
    is_active: bool
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


class ProductSort(str, Enum):
    name = "name"
    sku = "sku"
    unit_price = "unit_price"
    stock_quantity = "stock_quantity"
    created_at = "created_at"
    updated_at = "updated_at"


class SortDir(str, Enum):
    asc = "asc"
    desc = "desc"


class ActiveFilter(str, Enum):
    active = "active"
    inactive = "inactive"
    all = "all"
