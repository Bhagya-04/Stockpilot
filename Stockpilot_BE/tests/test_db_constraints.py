"""The database itself enforces the key invariants, independent of application code."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.session import get_engine


def exec_sql(db, sql, **params):
    return db.execute(text(sql), params)


def insert(db, sql, **params):
    """Run an INSERT ... RETURNING id and commit, so a later expected failure (which rolls back the
    failed statement's transaction) cannot undo the setup data."""
    value = exec_sql(db, sql, **params).scalar_one()
    db.commit()
    return value


def make_workspace(db, name="W"):
    return insert(db, "INSERT INTO workspaces (name) VALUES (:n) RETURNING id", n=name)


def make_user(db, email):
    return insert(db, "INSERT INTO users (email, full_name, password_hash) VALUES (:e, 'U', 'x') RETURNING id", e=email)


def make_product(db, ws, sku="S1", stock=5):
    return insert(
        db,
        "INSERT INTO products (workspace_id, name, sku, unit_price, stock_quantity) VALUES (:w, 'P', :s, 1.00, :q) RETURNING id",
        w=ws, s=sku, q=stock,
    )


def make_order(db, ws, user, total="1.00"):
    return insert(
        db,
        "INSERT INTO orders (workspace_id, created_by, status, total_amount) VALUES (:w, :u, 'PENDING', :t) RETURNING id",
        w=ws, u=user, t=total,
    )


def expect_integrity_error(db, sql, **params):
    with pytest.raises(IntegrityError):
        exec_sql(db, sql, **params)
    db.rollback()


def test_models_and_migrations_are_in_sync(_database):
    """`alembic upgrade head` must produce exactly the schema the models describe."""
    with get_engine().connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_stock_cannot_be_negative_at_database_level(db):
    ws = make_workspace(db)
    product = make_product(db, ws, stock=2)
    expect_integrity_error(db, "UPDATE products SET stock_quantity = -1 WHERE id = :i", i=product)


def test_sku_is_unique_per_workspace_only(db):
    ws1, ws2 = make_workspace(db, "A"), make_workspace(db, "B")
    make_product(db, ws1, "SAME")
    make_product(db, ws2, "SAME")  # fine
    expect_integrity_error(
        db, "INSERT INTO products (workspace_id, name, sku, unit_price) VALUES (:w, 'dup', 'SAME', 1)", w=ws1
    )


def test_money_and_integer_checks(db):
    ws = make_workspace(db)
    for sql in (
        "INSERT INTO products (workspace_id, name, sku, unit_price) VALUES (:w, 'n', 'A', -1)",
        "INSERT INTO products (workspace_id, name, sku, unit_price, low_stock_threshold) VALUES (:w, 'n', 'B', 1, -1)",
    ):
        expect_integrity_error(db, sql, w=ws)


def test_order_item_must_belong_to_the_same_workspace_as_its_order_and_product(db):
    ws_a, ws_b = make_workspace(db, "A"), make_workspace(db, "B")
    user = make_user(db, "u@example.com")
    order_a = make_order(db, ws_a, user)
    product_b = make_product(db, ws_b, "B1")
    # product from workspace B inside an order of workspace A (workspace_id says A) -> composite FK rejects it
    expect_integrity_error(
        db,
        "INSERT INTO order_items (order_id, workspace_id, product_id, product_name, sku, unit_price, quantity, line_total) "
        "VALUES (:o, :w, :p, 'x', 'x', 1, 1, 1)",
        o=order_a, w=ws_a, p=product_b,
    )


def test_order_item_checks(db):
    ws = make_workspace(db)
    user = make_user(db, "u@example.com")
    order = make_order(db, ws, user)
    product = make_product(db, ws)
    base = (
        "INSERT INTO order_items (order_id, workspace_id, product_id, product_name, sku, unit_price, quantity, line_total) "
        "VALUES (:o, :w, :p, 'x', 'x', 2.00, :q, :t)"
    )
    expect_integrity_error(db, base, o=order, w=ws, p=product, q=0, t=0)  # quantity must be positive
    expect_integrity_error(db, base, o=order, w=ws, p=product, q=3, t="5.00")  # line_total must equal price * qty
    exec_sql(db, base, o=order, w=ws, p=product, q=3, t="6.00")  # a consistent row is accepted
    db.commit()
    expect_integrity_error(db, base, o=order, w=ws, p=product, q=1, t="2.00")  # same product twice in one order


def test_invalid_order_status_is_rejected(db):
    ws = make_workspace(db)
    user = make_user(db, "u@example.com")
    expect_integrity_error(
        db, "INSERT INTO orders (workspace_id, created_by, status, total_amount) VALUES (:w, :u, 'SHIPPED', 1)", w=ws, u=user
    )


def test_stock_restoration_is_unique_per_order_line_in_the_database(db):
    """Even if application code were retried or raced, a second ORDER_CANCELLED row cannot be inserted."""
    ws = make_workspace(db)
    user = make_user(db, "u@example.com")
    product = make_product(db, ws)
    order = make_order(db, ws, user)
    sql = (
        "INSERT INTO inventory_adjustments (workspace_id, product_id, order_id, user_id, quantity_change, resulting_stock, reason) "
        "VALUES (:w, :p, :o, :u, 2, 7, :r)"
    )
    exec_sql(db, sql, w=ws, p=product, o=order, u=user, r="ORDER_CANCELLED")
    db.commit()
    expect_integrity_error(db, sql, w=ws, p=product, o=order, u=user, r="ORDER_CANCELLED")


def test_adjustment_checks(db):
    ws = make_workspace(db)
    user = make_user(db, "u@example.com")
    product = make_product(db, ws)
    base = (
        "INSERT INTO inventory_adjustments (workspace_id, product_id, user_id, quantity_change, resulting_stock, reason) "
        "VALUES (:w, :p, :u, :c, :r, :reason)"
    )
    expect_integrity_error(db, base, w=ws, p=product, u=user, c=0, r=5, reason="CORRECTION")
    expect_integrity_error(db, base, w=ws, p=product, u=user, c=-9, r=-1, reason="CORRECTION")
    expect_integrity_error(db, base, w=ws, p=product, u=user, c=1, r=6, reason="BOGUS")
    foreign_ws = make_workspace(db, "other")
    expect_integrity_error(db, base, w=foreign_ws, p=product, u=user, c=1, r=6, reason="CORRECTION")  # product not in that workspace


def test_email_must_be_lowercase_and_unique(db):
    make_user(db, "a@example.com")
    expect_integrity_error(db, "INSERT INTO users (email, full_name, password_hash) VALUES ('a@example.com', 'x', 'x')")
    expect_integrity_error(db, "INSERT INTO users (email, full_name, password_hash) VALUES ('B@example.com', 'x', 'x')")


def test_unknown_ids_are_not_found(db):
    ws = make_workspace(db)
    assert exec_sql(db, "SELECT count(*) FROM products WHERE id = :i AND workspace_id = :w", i=uuid.uuid4(), w=ws).scalar_one() == 0
