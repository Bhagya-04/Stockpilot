from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@contextmanager
def unit_of_work(db: Session) -> Iterator[Session]:
    """One database transaction. Everything inside commits together or not at all:
    any exception (including a failed commit) rolls the whole transaction back, which also
    releases the row locks taken inside it."""
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise


def violated_constraint(exc: IntegrityError) -> str | None:
    """Name of the constraint/index a PostgreSQL IntegrityError refers to (if known)."""
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)
