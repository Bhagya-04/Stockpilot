import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import Role
from app.models import WorkspaceMembership


def get_membership(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> WorkspaceMembership | None:
    return db.get(WorkspaceMembership, (user_id, workspace_id))


def list_memberships_for_user(db: Session, user_id: uuid.UUID) -> list[WorkspaceMembership]:
    stmt = select(WorkspaceMembership).where(WorkspaceMembership.user_id == user_id)
    return list(db.scalars(stmt).unique().all())


def list_members(db: Session, workspace_id: uuid.UUID) -> list[WorkspaceMembership]:
    stmt = select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == workspace_id)
    return sorted(db.scalars(stmt).unique().all(), key=lambda m: (m.role, m.user.full_name.lower()))


def count_owners(db: Session, workspace_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(
        WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.role == Role.OWNER.value
    )
    return db.scalar(stmt) or 0


def lock_owner_memberships(db: Session, workspace_id: uuid.UUID) -> None:
    """Serialise 'remove/demote an owner' operations so two requests cannot both strip the last owner."""
    stmt = (
        select(WorkspaceMembership.user_id)
        .where(WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.role == Role.OWNER.value)
        .with_for_update()
    )
    db.execute(stmt).all()
