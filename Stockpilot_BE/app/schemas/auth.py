from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import NormalisedEmail, ORMModel

_MIN_PASSWORD = 8
_MAX_PASSWORD_BYTES = 72  # bcrypt ignores everything after 72 bytes, so we refuse longer passwords


def _check_password(value: str) -> str:
    if len(value) < _MIN_PASSWORD:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD} characters")
    if len(value.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {_MAX_PASSWORD_BYTES} bytes")
    return value


class RegisterRequest(BaseModel):
    email: NormalisedEmail
    password: str
    full_name: str = Field(min_length=1, max_length=120)
    # Optional: create a first workspace (the new user becomes its OWNER).
    workspace_name: str | None = Field(default=None, min_length=1, max_length=120)

    _password = field_validator("password")(_check_password)

    @field_validator("full_name", "workspace_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value


class LoginRequest(BaseModel):
    email: NormalisedEmail
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: UUID
    email: str
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
