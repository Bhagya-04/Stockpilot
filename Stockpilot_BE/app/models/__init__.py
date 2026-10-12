"""Import every model so Base.metadata (used by Alembic) is complete."""

from app.models.inventory import InventoryAdjustment
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership

__all__ = [
    "InventoryAdjustment",
    "Order",
    "OrderItem",
    "Product",
    "User",
    "Workspace",
    "WorkspaceMembership",
]
