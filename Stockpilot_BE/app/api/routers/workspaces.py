import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, DbSession, require
from app.core.context import WorkspaceContext
from app.core.permissions import Permission, Role
from app.schemas.workspace import (
    MemberAdd,
    MemberOut,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceOut,
)
from app.services import workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceOut])
def list_my_workspaces(user: CurrentUser, db: DbSession) -> list[WorkspaceOut]:
    """Only the caller's own workspaces are ever returned."""
    return [
        WorkspaceOut(id=m.workspace_id, name=m.workspace.name, role=Role(m.role))
        for m in workspace_service.list_memberships(db, user)
    ]


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(data: WorkspaceCreate, user: CurrentUser, db: DbSession) -> WorkspaceOut:
    workspace = workspace_service.create_workspace_committed(db, user, data.name)
    return WorkspaceOut(id=workspace.id, name=workspace.name, role=Role.OWNER)


def _member_out(membership) -> MemberOut:
    return MemberOut(
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=Role(membership.role),
        created_at=membership.created_at,
    )


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.MEMBER_READ))], db: DbSession
) -> list[MemberOut]:
    return [_member_out(m) for m in workspace_service.list_members(db, ctx)]


@router.post("/{workspace_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    data: MemberAdd, ctx: Annotated[WorkspaceContext, Depends(require(Permission.MEMBER_MANAGE))], db: DbSession
) -> MemberOut:
    return _member_out(workspace_service.add_member(db, ctx, data))


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberOut)
def change_member_role(
    user_id: uuid.UUID,
    data: MemberRoleUpdate,
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.MEMBER_MANAGE))],
    db: DbSession,
) -> MemberOut:
    return _member_out(workspace_service.change_role(db, ctx, user_id, data.role))


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require(Permission.MEMBER_MANAGE))],
    db: DbSession,
) -> Response:
    workspace_service.remove_member(db, ctx, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
