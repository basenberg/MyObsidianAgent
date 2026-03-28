"""Shared Pydantic schemas for common patterns."""

import math
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standard pagination parameters for list endpoints.

    Example:
        @app.get("/products")
        def list_products(pagination: PaginationParams = Depends()):
            products = db.query(Product).offset(pagination.offset).limit(pagination.page_size).all()
            total = db.query(Product).count()
            return PaginatedResponse(
                items=products,
                total=total,
                page=pagination.page,
                page_size=pagination.page_size
            )
    """

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate the offset for database queries."""
        return (self.page - 1) * self.page_size


class PaginatedResponse[T](BaseModel):
    """Standard paginated response format.

    Generic response wrapper that works with any item type.

    Example:
        class ProductResponse(BaseModel):
            id: int
            name: str

        PaginatedResponse[ProductResponse](
            items=[...],
            total=100,
            page=1,
            page_size=20
        )
    """

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        if self.total == 0:
            return 0
        return math.ceil(self.total / self.page_size)


class ErrorResponse(BaseModel):
    """Standard error response format.

    Used by exception handlers to provide consistent error responses
    across the API.

    Example:
        @app.exception_handler(ValueError)
        def value_error_handler(request: Request, exc: ValueError):
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error=str(exc),
                    type="validation_error",
                    detail="Invalid input provided"
                ).model_dump()
            )
    """

    error: str
    type: str
    detail: str | None = None
