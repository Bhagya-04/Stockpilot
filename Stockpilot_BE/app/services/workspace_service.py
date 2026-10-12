import uuid

from sqlalchemy.orm import Session

from app.core.context import WorkspaceContext
from app.core.errors import ConflictError, NotFoundError
from app.core.permissions import Role
from app.db.unit_of_work import unit_of_work
from app.models import User, Workspace, WorkspaceMembership
from app.repositories import users as user_repo
from app.repositories import workspaces as workspace_repo
from app.schemas.workspace import MemberAdd


def create_workspace(db: Session, owner: User, name: str) -> Workspace:
    """Add a workspace + OWNER membership to the *caller's* transaction (caller commits)."""
    workspace = Workspace(name=name)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMembership(user_id=owner.id, workspace_id=workspace.id, role=Role.OWNER.value))
    db.flush()
    return workspace


def create_workspace_committed(db: Session, owner: User, name: str) -> Workspace:
    with unit_of_work(db):
        return create_workspace(db, owner, name)


def list_memberships(db: Session, user: User) -> list[WorkspaceMembership]:
    memberships = workspace_repo.list_memberships_for_user(db, user.id)
    return sorted(memberships, key=lambda m: m.workspace.name.lower())


def list_members(db: Session, ctx: WorkspaceContext) -> list[WorkspaceMembership]:
    return workspace_repo.list_members(db, ctx.workspace_id)


def add_member(db: Session, ctx: WorkspaceContext, data: MemberAdd) -> WorkspaceMembership:
    target = user_repo.get_by_email(db, data.email)
    if target is None or not target.is_active:
        raise NotFoundError(
            "No registered user with that email. Ask them to register first.",
            code="USER_NOT_FOUND",
            details=[{"field": "email", "message": "No registered user with this email"}],
        )
    if workspace_repo.get_membership(db, target.id, ctx.workspace_id):
        raise ConflictError(
            "That user is already a member of this workspace",
            code="ALREADY_MEMBER",
            details=[{"field": "email", "message": "Already a member"}],
        )
    with unit_of_work(db):
        membership = WorkspaceMembership(user_id=target.id, workspace_id=ctx.workspace_id, role=data.role.value)
        db.add(membership)
    return workspace_repo.get_membership(db, target.id, ctx.workspace_id)  # type: ignore[return-value]


def change_role(db: Session, ctx: WorkspaceContext, user_id: uuid.UUID, role: Role) -> WorkspaceMembership:
    with unit_of_work(db):
        membership = _locked_membership(db, ctx, user_id)
        if membership.role == Role.OWNER.value and role is not Role.OWNER:
            _ensure_not_last_owner(db, ctx.workspace_id)
        membership.role = role.value
    return membership


def remove_member(db: Session, ctx: WorkspaceContext, user_id: uuid.UUID) -> None:
    with unit_of_work(db):
        membership = _locked_membership(db, ctx, user_id)
        if membership.role == Role.OWNER.value:
            _ensure_not_last_owner(db, ctx.workspace_id)
        db.delete(membership)


def _locked_membership(db: Session, ctx: WorkspaceContext, user_id: uuid.UUID) -> WorkspaceMembership:
    # Serialises concurrent owner changes so two requests cannot each remove "the other" owner.
    workspace_repo.lock_owner_memberships(db, ctx.workspace_id)
    membership = workspace_repo.get_membership(db, user_id, ctx.workspace_id)
    if membership is None:
        raise NotFoundError("Member not found", code="MEMBER_NOT_FOUND")
    return membership


def _ensure_not_last_owner(db: Session, workspace_id: uuid.UUID) -> None:
    if workspace_repo.count_owners(db, workspace_id) <= 1:
        raise ConflictError("A workspace must keep at least one owner", code="LAST_OWNER")
