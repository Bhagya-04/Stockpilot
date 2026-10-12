import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.core.errors import ValidationFailedError

T = TypeVar("T")

MAX_PAGE_SIZE = 100

# Reusable validated types.
Money = Annotated[Decimal, Field(ge=0, max_digits=9, decimal_places=2)]
StockInt = Annotated[int, Field(ge=0, le=10_000_000)]
NormalisedEmail = Annotated[EmailStr, StringConstraints(strip_whitespace=True, to_lower=True)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRef(ORMModel):
    id: UUID
    full_name: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        return cls(items=items, total=total, page=page, page_size=page_size, pages=math.ceil(total / page_size))


def make_page(items: list[Any], out_type: type[T], total: int, params: "PageParams") -> Page[T]:
    """Serialise ORM rows into `out_type` and wrap them with pagination metadata."""
    return Page.build([out_type.model_validate(item) for item in items], total, params.page, params.page_size)  # type: ignore[attr-defined]


@dataclass
class PageParams:
    page: int = Query(1, ge=1, le=1_000_000, description="1-based page number")
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass
class DateRange:
    """Inclusive calendar dates, interpreted as UTC days (see README: timezone convention)."""

    date_from: date | None = Query(None, description="YYYY-MM-DD (UTC), inclusive")
    date_to: date | None = Query(None, description="YYYY-MM-DD (UTC), inclusive")

    def __post_init__(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationFailedError(
                "date_from must not be after date_to",
                details=[{"field": "date_from", "message": "date_from must not be after date_to"}],
            )


PageDep = Annotated[PageParams, Depends()]
DateRangeDep = Annotated[DateRange, Depends()]
