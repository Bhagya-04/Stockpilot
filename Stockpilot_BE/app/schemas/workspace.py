from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.permissions import Role
from app.schemas.common import NormalisedEmail, ORMModel


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value


class WorkspaceOut(BaseModel):
    id: UUID
    name: str
    role: Role


class MemberOut(ORMModel):
    user_id: UUID
    email: str
    full_name: str
    role: Role
    created_at: datetime


class MemberAdd(BaseModel):
    email: NormalisedEmail
    role: Role = Role.STAFF


class MemberRoleUpdate(BaseModel):
    role: Role
