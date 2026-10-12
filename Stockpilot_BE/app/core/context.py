import uuid
from dataclasses import dataclass

from app.core.permissions import Role
from app.models import User


@dataclass(frozen=True)
class WorkspaceContext:
    """Who is acting, in which workspace, with which role. Built on the server from the verified
    token + a membership lookup - never from client-supplied identity."""

    user: User
    workspace_id: uuid.UUID
    role: Role
