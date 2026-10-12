from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.unit_of_work import unit_of_work
from app.models import User
from app.repositories import users as user_repo
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import workspace_service


def register(db: Session, data: RegisterRequest) -> tuple[User, str]:
    if user_repo.get_by_email(db, data.email):
        raise _email_taken()
    user = User(email=data.email, full_name=data.full_name, password_hash=hash_password(data.password))
    try:
        with unit_of_work(db):
            db.add(user)
            db.flush()
            if data.workspace_name:
                workspace_service.create_workspace(db, user, data.workspace_name)
    except IntegrityError:
        # Two simultaneous registrations with the same e-mail: the unique constraint decides.
        raise _email_taken() from None
    return user, create_access_token(user.id)


def login(db: Session, data: LoginRequest) -> tuple[User, str]:
    user = user_repo.get_by_email(db, data.email)
    # verify_password does the same amount of work whether or not the account exists.
    if not verify_password(data.password, user.password_hash if user else None) or not user or not user.is_active:
        raise UnauthorizedError("Invalid email or password", code="INVALID_CREDENTIALS")
    return user, create_access_token(user.id)


def _email_taken() -> ConflictError:
    return ConflictError(
        "An account with this email already exists",
        code="EMAIL_TAKEN",
        details=[{"field": "email", "message": "Already registered"}],
    )
