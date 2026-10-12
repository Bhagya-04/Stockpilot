"""Authentication + authorization dependencies.

Every workspace route depends on `require(<Permission>)`, which:
  1. authenticates the caller from the bearer token (identity is NEVER taken from the request body),
  2. checks the caller is a member of the workspace in the URL (404 otherwise - no existence leak),
  3. checks that the member's role grants the permission (403 otherwise).
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.context import WorkspaceContext
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.permissions import Permission, Role, has_permission
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.repositories import users as user_repo
from app.repositories import workspaces as workspace_repo

_bearer = HTTPBearer(auto_error=False, description="JWT from /auth/login or /auth/register")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], db: DbSession
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication required", code="AUTH_REQUIRED")
    user_id = decode_access_token(credentials.credentials)
    user = user_repo.get_by_id(db, user_id) if user_id else None
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token", code="INVALID_TOKEN")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_workspace_context(workspace_id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkspaceContext:
    membership = workspace_repo.get_membership(db, user.id, workspace_id)
    if membership is None:
        # Identical response for "does not exist" and "exists but you are not a member".
        raise NotFoundError("Workspace not found", code="WORKSPACE_NOT_FOUND")
    return WorkspaceContext(user=user, workspace_id=workspace_id, role=Role(membership.role))


def require(permission: Permission) -> Callable[..., WorkspaceContext]:
    def dependency(ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)]) -> WorkspaceContext:
        if not has_permission(ctx.role, permission):
            raise ForbiddenError(
                "Your role does not allow this action", code="PERMISSION_DENIED",
                details=[{"required_permission": permission.value, "role": ctx.role.value}],
            )
        return ctx

    return dependency
