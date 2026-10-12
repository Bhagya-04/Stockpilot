import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.inventory_rules import AdjustmentReason
from app.models.product import Product
from app.models.user import User

_REASONS = ", ".join(repr(r.value) for r in AdjustmentReason)


class InventoryAdjustment(Base):
    """Append-only ledger of every stock change (manual adjustments AND order reservations/restores)."""

    __tablename__ = "inventory_adjustments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "workspace_id"],
            ["products.id", "products.workspace_id"],
            name="fk_inventory_adjustments_product_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["order_id", "workspace_id"],
            ["orders.id", "orders.workspace_id"],
            name="fk_inventory_adjustments_order_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity_change <> 0", name="quantity_change_non_zero"),
        CheckConstraint("resulting_stock >= 0", name="resulting_stock_non_negative"),
        CheckConstraint(f"reason IN ({_REASONS})", name="reason_valid"),
        # DB-level guarantee that an order reserves and restores each product at most once,
        # even if application code is retried or raced.
        Index(
            "uq_inventory_adjustments_order_product_reason",
            "order_id",
            "product_id",
            "reason",
            unique=True,
            postgresql_where=text("order_id IS NOT NULL"),
        ),
        Index("ix_inventory_adjustments_workspace_id_created_at", "workspace_id", "created_at"),
        Index("ix_inventory_adjustments_product_id_created_at", "product_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    quantity_change: Mapped[int] = mapped_column(Integer)
    resulting_stock: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship(
        primaryjoin="InventoryAdjustment.product_id == Product.id",
        foreign_keys=[product_id],
        lazy="joined",
    )
    user: Mapped[User] = relationship(lazy="joined")
