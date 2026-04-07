"""Shared pagination utilities."""
import math
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")


class PageParams:
    """Common pagination parameters."""

    def __init__(self, page: int = 1, page_size: int = 50):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 500)  # Cap at 500

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )
