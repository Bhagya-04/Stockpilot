from datetime import datetime, time, timedelta, timezone
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import DateRange, PageParams

T = TypeVar("T")


def paginate(db: Session, stmt: Select[Any], params: PageParams) -> tuple[list[Any], int]:
    """Run `stmt` with LIMIT/OFFSET and return (rows, total_matching)."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.limit(params.page_size).offset(params.offset)).unique().all()
    return list(rows), total


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so user input is matched literally (use with escape='\\')."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def utc_bounds(date_range: DateRange) -> tuple[datetime | None, datetime | None]:
    """Convert inclusive UTC calendar dates into a half-open [start, end) datetime window."""
    start = (
        datetime.combine(date_range.date_from, time.min, tzinfo=timezone.utc) if date_range.date_from else None
    )
    end = (
        datetime.combine(date_range.date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        if date_range.date_to
        else None
    )
    return start, end
