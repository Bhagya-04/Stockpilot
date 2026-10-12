"""Role -> permission matrix. This is the single source of truth; it is enforced by API dependencies."""

from enum import Enum


class Role(str, Enum):
    OWNER = "OWNER"
    STAFF = "STAFF"


class Permission(str, Enum):
    PRODUCT_READ = "product:read"
    PRODUCT_WRITE = "product:write"  # create / edit / (de)activate
    INVENTORY_READ = "inventory:read"
    INVENTORY_ADJUST = "inventory:adjust"
    ORDER_READ = "order:read"
    ORDER_CREATE = "order:create"
    ORDER_UPDATE = "order:update"  # confirm / complete / cancel
    DASHBOARD_READ = "dashboard:read"
    MEMBER_READ = "member:read"
    MEMBER_MANAGE = "member:manage"


_STAFF_PERMISSIONS = frozenset(
    {
        Permission.PRODUCT_READ,
        Permission.INVENTORY_READ,
        Permission.INVENTORY_ADJUST,
        Permission.ORDER_READ,
        Permission.ORDER_CREATE,
        Permission.ORDER_UPDATE,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),  # owners can do everything
    Role.STAFF: _STAFF_PERMISSIONS,
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
