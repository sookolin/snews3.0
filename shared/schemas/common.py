"""Common/shared schema helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base schema that reads attributes from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    """Standard pagination + ordering query parameters."""

    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=200)
    order_by: str | None = None
    order_dir: str = Field("desc", pattern="^(asc|desc)$")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PaginationParams) -> Page[T]:
        pages = (total + params.size - 1) // params.size if params.size else 0
        return cls(items=items, total=total, page=params.page, size=params.size, pages=pages)


class Message(BaseModel):
    """Simple message response."""

    detail: str
