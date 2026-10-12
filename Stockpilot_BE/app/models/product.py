import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        # SKU is unique per workspace, not globally.
        UniqueConstraint("workspace_id", "sku", name="uq_products_workspace_id_sku"),
        # Lets child tables use a composite FK (id, workspace_id) so a row can never point at
        # a product that belongs to a different workspace.
        UniqueConstraint("id", "workspace_id", name="uq_products_id_workspace_id"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="stock_non_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="low_stock_threshold_non_negative"),
        Index("ix_products_workspace_id_name", "workspace_id", "name"),
        Index("ix_products_workspace_id_is_active", "workspace_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Current stock. It only ever changes together with an inventory_adjustments row.
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def is_low_stock(self) -> bool:
        """Low stock = an ACTIVE product whose stock is at or below its threshold."""
        return self.is_active and self.stock_quantity <= self.low_stock_threshold
