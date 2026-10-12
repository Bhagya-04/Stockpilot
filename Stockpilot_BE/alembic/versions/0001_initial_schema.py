"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")  # built into PostgreSQL 13+
_NOW = sa.text("now()")

_REASONS = "'RECEIVED', 'RETURNED', 'DAMAGED', 'CORRECTION', 'OTHER', 'INITIAL_STOCK', 'ORDER_RESERVED', 'ORDER_CANCELLED'"
_STATUSES = "'PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED'"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=_UUID_DEFAULT, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), server_default=_UUID_DEFAULT, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )

    op.create_table(
        "workspace_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("role IN ('OWNER', 'STAFF')", name=op.f("ck_workspace_memberships_role_valid")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_workspace_memberships_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_memberships_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "workspace_id", name=op.f("pk_workspace_memberships")),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), server_default=_UUID_DEFAULT, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_products_unit_price_non_negative")),
        sa.CheckConstraint("stock_quantity >= 0", name=op.f("ck_products_stock_non_negative")),
        sa.CheckConstraint("low_stock_threshold >= 0", name=op.f("ck_products_low_stock_threshold_non_negative")),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_products_workspace_id_workspaces"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("workspace_id", "sku", name="uq_products_workspace_id_sku"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_products_id_workspace_id"),
    )
    op.create_index("ix_products_workspace_id_name", "products", ["workspace_id", "name"])
    op.create_index("ix_products_workspace_id_is_active", "products", ["workspace_id", "is_active"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), server_default=_UUID_DEFAULT, nullable=False),
        sa.Column("order_number", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name=op.f("ck_orders_status_valid")),
        sa.CheckConstraint("total_amount >= 0", name=op.f("ck_orders_total_non_negative")),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_orders_workspace_id_workspaces"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_orders_created_by_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("order_number", name=op.f("uq_orders_order_number")),
        sa.UniqueConstraint("id", "workspace_id", name="uq_orders_id_workspace_id"),
    )
    op.create_index(
        "uq_orders_workspace_id_idempotency_key",
        "orders",
        ["workspace_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index("ix_orders_workspace_id_created_at", "orders", ["workspace_id", "created_at"])
    op.create_index("ix_orders_workspace_id_status", "orders", ["workspace_id", "status"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), server_default=_UUID_DEFAULT, nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_items_quantity_positive")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_order_items_unit_price_non_negative")),
        sa.CheckConstraint("line_total = unit_price * quantity", name=op.f("ck_order_items_line_total_matches")),
        sa.ForeignKeyConstraint(
            ["order_id", "workspace_id"],
            ["orders.id", "orders.workspace_id"],
            name="fk_order_items_order_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "workspace_id"],
            ["products.id", "products.workspace_id"],
            name="fk_order_items_product_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_order_items_workspace_id_workspaces"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_items_order_id_product_id"),
    )

    op.create_table(
        "inventory_adjustments",
        sa.Column("id", sa.Uuid(), server_default=_UUID_DEFAULT, nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_change", sa.Integer(), nullable=False),
        sa.Column("resulting_stock", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("quantity_change <> 0", name=op.f("ck_inventory_adjustments_quantity_change_non_zero")),
        sa.CheckConstraint("resulting_stock >= 0", name=op.f("ck_inventory_adjustments_resulting_stock_non_negative")),
        sa.CheckConstraint(f"reason IN ({_REASONS})", name=op.f("ck_inventory_adjustments_reason_valid")),
        sa.ForeignKeyConstraint(
            ["product_id", "workspace_id"],
            ["products.id", "products.workspace_id"],
            name="fk_inventory_adjustments_product_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id", "workspace_id"],
            ["orders.id", "orders.workspace_id"],
            name="fk_inventory_adjustments_order_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_inventory_adjustments_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_inventory_adjustments_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_adjustments")),
    )
    op.create_index(
        "uq_inventory_adjustments_order_product_reason",
        "inventory_adjustments",
        ["order_id", "product_id", "reason"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_adjustments_workspace_id_created_at", "inventory_adjustments", ["workspace_id", "created_at"]
    )
    op.create_index(
        "ix_inventory_adjustments_product_id_created_at", "inventory_adjustments", ["product_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("inventory_adjustments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("users")
