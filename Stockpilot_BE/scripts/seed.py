"""Seed SYNTHETIC demo data (no real people or businesses).

    python -m scripts.seed

Creates two unrelated workspaces so workspace isolation can be demonstrated:
  * "Acme Electronics"  - owner + staff, ~12 products, orders in every status
  * "Rival Traders"  - a separate owner with a couple of products

The demo logins are the plain, public, demo-only credentials listed in ACCOUNTS below. They must not be
used on any real account - do not seed a production database that holds real data.
Running it twice is safe: it does nothing if the demo admin already exists. Databases seeded by an
earlier version (owner@/staff@/rival@demo-stockpilot.com) are renamed to the accounts below.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.core.context import WorkspaceContext
from app.core.permissions import Role
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.domain.order_rules import OrderStatus
from app.repositories import users as user_repo
from app.repositories import workspaces as workspace_repo
from app.schemas.auth import RegisterRequest
from app.schemas.inventory import AdjustmentCreate
from app.schemas.order import OrderCreate, OrderItemIn
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.workspace import MemberAdd
from app.services import auth_service, inventory_service, order_service, product_service, workspace_service

# email, password, display name
ADMIN = ("admin@stockpilot.com", "Admin@123", "Admin")
STAFF = ("staff@stockpilot.com", "Staff@123", "Staff")
ADMIN_2 = ("admin2@stockpilot.com", "Admin2@123", "Admin 2")
ACCOUNTS = (ADMIN, STAFF, ADMIN_2)
ACCOUNT_LABELS = ("Admin (Acme Electronics)", "Staff (Acme Electronics)", "Admin (Rival Traders)")

# Accounts created by the first version of this script -> their replacements.
LEGACY_RENAMES = {
    "owner@demo-stockpilot.com": ADMIN,
    "staff@demo-stockpilot.com": STAFF,
    "rival@demo-stockpilot.com": ADMIN_2,
}

PRODUCTS = [
    # name, sku, price (INR), stock, low-stock threshold
    ("Wireless Mouse", "MOU-001", "599.00", 40, 10),
    ("Bluetooth Headphones", "HDP-002", "2499.00", 12, 5),
    ("USB-C Charger 65W", "CHG-003", "1299.00", 25, 8),
    ("HDMI Cable 2m", "HDM-004", "349.00", 60, 15),
    ("Mechanical Keyboard", "KEY-005", "3299.00", 18, 6),
    ("Smart Watch", "WCH-006", "4999.00", 4, 10),  # starts low on purpose
    ("Power Bank 20000mAh", "PWR-007", "1799.00", 30, 10),
    ("Memory Card 64GB", "MEM-008", "549.00", 150, 40),
    ("Webcam Full HD", "CAM-009", "1999.00", 7, 7),  # exactly at threshold => low stock
    ("Portable Speaker", "SPK-010", "2199.00", 22, 5),
    ("Laptop Stand", "LST-011", "899.00", 35, 10),
    ("Wired Earphones (discontinued)", "EAR-OLD", "299.00", 0, 2),  # will be deactivated
]

# Products created by the first (hardware) version of this script -> electronics replacements.
# Applied in place to the demo workspaces only, keeping every order and stock-history row.
LEGACY_PRODUCTS = {
    "HAM-016": ("Wireless Mouse", "MOU-001", "599.00"),
    "DRL-018": ("Bluetooth Headphones", "HDP-002", "2499.00"),
    "SCR-012": ("USB-C Charger 65W", "CHG-003", "1299.00"),
    "TAP-005": ("HDMI Cable 2m", "HDM-004", "349.00"),
    "WRN-010": ("Mechanical Keyboard", "KEY-005", "3299.00"),
    "SAF-001": ("Smart Watch", "WCH-006", "4999.00"),
    "GLV-L": ("Power Bank 20000mAh", "PWR-007", "1799.00"),
    "WSC-100": ("Memory Card 64GB", "MEM-008", "549.00"),
    "SAW-020": ("Webcam Full HD", "CAM-009", "1999.00"),
    "LVL-060": ("Portable Speaker", "SPK-010", "2199.00"),
    "PNT-005": ("Laptop Stand", "LST-011", "899.00"),
    "VGR-OLD": ("Wired Earphones (discontinued)", "EAR-OLD", "299.00"),
    "SPD-001": ("Phone Case", "CSE-001", "399.00"),
    "TRW-001": ("Tempered Glass Screen Protector", "GLS-001", "199.00"),
}


def _register(db, account: tuple[str, str, str], workspace: str | None = None):
    email, password, name = account
    existing = user_repo.get_by_email(db, email)
    if existing:
        return existing
    user, _ = auth_service.register(
        db, RegisterRequest(email=email, password=password, full_name=name, workspace_name=workspace)
    )
    return user


def _rename_legacy_accounts(db) -> int:
    """Upgrade demo users created by an earlier version of this script (keeps all their data)."""
    renamed = 0
    for old_email, (email, password, name) in LEGACY_RENAMES.items():
        user = user_repo.get_by_email(db, old_email)
        if user and not user_repo.get_by_email(db, email):
            user.email, user.full_name, user.password_hash = email, name, hash_password(password)
            renamed += 1
    db.commit()
    return renamed


def _upgrade_legacy_catalogue(db) -> int:
    """Rename the old hardware demo products to electronics in the demo workspaces, keeping history.

    Order lines are snapshots, so they are rewritten consistently (name, sku, price, line_total) and the
    order totals recomputed - the database CHECK (line_total = unit_price * quantity) still holds."""
    changed = 0
    admin = user_repo.get_by_email(db, ADMIN[0])
    admin_2 = user_repo.get_by_email(db, ADMIN_2[0])
    workspace_ids = [
        m.workspace_id
        for user in (admin, admin_2)
        if user
        for m in workspace_repo.list_memberships_for_user(db, user.id)
        if m.role == Role.OWNER.value and m.workspace.name in ("Acme Hardware", "Acme Electronics", "Rival Traders")
    ]
    for ws_id in workspace_ids:
        for old_sku, (name, sku, price) in LEGACY_PRODUCTS.items():
            row = db.execute(
                text("SELECT id FROM products WHERE workspace_id = :w AND sku = :s"), {"w": ws_id, "s": old_sku}
            ).first()
            if not row:
                continue
            args = {"id": row.id, "name": name, "sku": sku, "price": Decimal(price)}
            db.execute(text("UPDATE products SET name = :name, sku = :sku, unit_price = :price WHERE id = :id"), args)
            db.execute(
                text(
                    "UPDATE order_items SET product_name = :name, sku = :sku, unit_price = :price, "
                    "line_total = :price * quantity WHERE product_id = :id"
                ),
                args,
            )
            changed += 1
        db.execute(
            text(
                "UPDATE orders SET total_amount = (SELECT COALESCE(SUM(line_total), 0) FROM order_items "
                "WHERE order_items.order_id = orders.id) WHERE workspace_id = :w"
            ),
            {"w": ws_id},
        )
        db.execute(text("UPDATE workspaces SET name = 'Acme Electronics' WHERE id = :w AND name = 'Acme Hardware'"), {"w": ws_id})
    db.commit()
    return changed


def print_accounts() -> None:
    print("Demo logins (email / password):")
    for (email, password, _), label in zip(ACCOUNTS, ACCOUNT_LABELS):
        print(f"  {label:<24} {email:<26} {password}")


def _ctx(db, user, role: Role) -> WorkspaceContext:
    membership = workspace_repo.list_memberships_for_user(db, user.id)[0]
    return WorkspaceContext(user=user, workspace_id=membership.workspace_id, role=role)


def main() -> None:
    db = get_sessionmaker()()
    renamed = _rename_legacy_accounts(db)
    if renamed:
        print(f"Renamed {renamed} existing demo account(s) to the Admin/Staff logins.")
    upgraded = _upgrade_legacy_catalogue(db)
    if upgraded:
        print(f"Updated {upgraded} existing demo product(s) to the electronics catalogue.")
    if user_repo.get_by_email(db, ADMIN[0]):
        print_accounts()
        print("\nDemo data already present - nothing else to do.")
        return

    owner = _register(db, ADMIN, "Acme Electronics")
    staff = _register(db, STAFF)
    rival = _register(db, ADMIN_2, "Rival Traders")

    owner_ctx = _ctx(db, owner, Role.OWNER)
    workspace_service.add_member(db, owner_ctx, MemberAdd(email=STAFF[0], role=Role.STAFF))
    staff_ctx = WorkspaceContext(user=staff, workspace_id=owner_ctx.workspace_id, role=Role.STAFF)

    products = {}
    for name, sku, price, stock, threshold in PRODUCTS:
        products[sku] = product_service.create_product(
            db,
            owner_ctx,
            ProductCreate(name=name, sku=sku, unit_price=Decimal(price), stock_quantity=stock, low_stock_threshold=threshold),
        )

    # Some manual stock movements, performed by staff.
    inventory_service.adjust_stock(
        db, staff_ctx, products["WCH-006"].id, AdjustmentCreate(quantity_change=3, reason="RECEIVED", note="Delivery PO-1042")
    )
    inventory_service.adjust_stock(
        db, staff_ctx, products["PWR-007"].id, AdjustmentCreate(quantity_change=-2, reason="DAMAGED", note="Torn in storage")
    )
    inventory_service.adjust_stock(
        db, owner_ctx, products["MEM-008"].id, AdjustmentCreate(quantity_change=-5, reason="CORRECTION", note="Stock count")
    )

    # Orders in every state.
    def place(ctx, lines, final: OrderStatus | None):
        order, _ = order_service.create_order(
            db, ctx, OrderCreate(items=[OrderItemIn(product_id=products[s].id, quantity=q) for s, q in lines])
        )
        if final in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED):
            order_service.change_status(db, ctx, order.id, OrderStatus.CONFIRMED)
        if final is OrderStatus.COMPLETED:
            order_service.change_status(db, ctx, order.id, OrderStatus.COMPLETED)
        if final is OrderStatus.CANCELLED:
            order_service.change_status(db, ctx, order.id, OrderStatus.CANCELLED)
        return order

    scenarios = [
        ([("MOU-001", 2), ("HDM-004", 4)], OrderStatus.COMPLETED),
        ([("HDP-002", 1), ("CHG-003", 2), ("PWR-007", 4)], OrderStatus.COMPLETED),
        ([("MEM-008", 20), ("LST-011", 3)], OrderStatus.COMPLETED),
        ([("KEY-005", 2)], OrderStatus.CONFIRMED),
        ([("SPK-010", 3), ("WCH-006", 2)], OrderStatus.CONFIRMED),
        ([("CAM-009", 1)], OrderStatus.PENDING),
        ([("HDP-002", 2), ("MOU-001", 1)], OrderStatus.PENDING),
        ([("LST-011", 5)], OrderStatus.CANCELLED),
        ([("HDM-004", 10), ("MEM-008", 10)], OrderStatus.CANCELLED),
    ]
    placed = []
    for index, (lines, final) in enumerate(scenarios):
        placed.append(place(owner_ctx if index % 2 == 0 else staff_ctx, lines, final))

    product_service.update_product(db, owner_ctx, products["EAR-OLD"].id, ProductUpdate(is_active=False))

    # Spread order dates over the last two weeks so the dashboard date range is meaningful.
    rng = random.Random(7)
    now = datetime.now(timezone.utc)
    for order in placed:
        db.execute(
            text("UPDATE orders SET created_at = :ts WHERE id = :id"),
            {"ts": now - timedelta(days=rng.randint(0, 13), hours=rng.randint(0, 20)), "id": order.id},
        )
    db.commit()

    rival_ctx = _ctx(db, rival, Role.OWNER)
    for name, sku, price, stock, threshold in [("Phone Case", "CSE-001", "399.00", 15, 5), ("Tempered Glass Screen Protector", "GLS-001", "199.00", 40, 10)]:
        product_service.create_product(
            db, rival_ctx, ProductCreate(name=name, sku=sku, unit_price=Decimal(price), stock_quantity=stock, low_stock_threshold=threshold)
        )

    print("Demo data created.\n")
    print_accounts()


if __name__ == "__main__":
    main()
