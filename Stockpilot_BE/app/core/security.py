"""Password hashing and JWT access tokens."""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

_ALGORITHM = "HS256"
# Used to burn the same CPU time when the e-mail is unknown, so login timing does not reveal accounts.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    candidate = password_hash or _DUMMY_HASH
    try:
        matches = bcrypt.checkpw(password.encode("utf-8"), candidate.encode())
    except ValueError:
        return False
    return matches and password_hash is not None


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id from a valid token, or None if it is invalid/expired."""
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key.get_secret_value(),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
