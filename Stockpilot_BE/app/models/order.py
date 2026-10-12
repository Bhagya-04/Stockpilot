import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.order_rules import OrderStatus, format_order_number
from app.models.user import User

_STATUSES = ", ".join(repr(s.value) for s in OrderStatus)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_orders_id_workspace_id"),
        CheckConstraint(f"status IN ({_STATUSES})", name="status_valid"),
        CheckConstraint("total_amount >= 0", name="total_non_negative"),
        # Lets clients safely retry "create order" with the same Idempotency-Key.
        Index(
            "uq_orders_workspace_id_idempotency_key",
            "workspace_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_orders_workspace_id_created_at", "workspace_id", "created_at"),
        Index("ix_orders_workspace_id_status", "workspace_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    # Human-friendly, globally unique, never reused: shown as ORD-000123.
    order_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.PENDING.value)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creator: Mapped[User] = relationship(lazy="joined")
    items: Mapped[list["OrderItem"]] = relationship(
        primaryjoin="Order.id == OrderItem.order_id",
        foreign_keys="OrderItem.order_id",
        order_by="OrderItem.product_name",
        lazy="selectin",
        viewonly=True,
    )

    @property
    def display_number(self) -> str:
        return format_order_number(self.order_number)


class OrderItem(Base):
    """A line item. product_name / sku / unit_price are immutable snapshots taken at order time."""

    __tablename__ = "order_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "workspace_id"],
            ["orders.id", "orders.workspace_id"],
            name="fk_order_items_order_workspace",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["product_id", "workspace_id"],
            ["products.id", "products.workspace_id"],
            name="fk_order_items_product_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_id_product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("line_total = unit_price * quantity", name="line_total_matches"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    product_name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(64))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
