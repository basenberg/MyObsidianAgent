"""Tests for shared Pydantic schemas."""

import pytest
from pydantic import BaseModel, ValidationError

from app.shared.schemas import ErrorResponse, PaginatedResponse, PaginationParams


# Test schema for PaginatedResponse
class ProductSchema(BaseModel):
    """Mock product schema for testing."""

    id: int
    name: str


def test_pagination_params_defaults() -> None:
    """Test that PaginationParams has correct default values."""
    params = PaginationParams()

    assert params.page == 1
    assert params.page_size == 20


def test_pagination_params_custom_values() -> None:
    """Test that PaginationParams accepts custom values."""
    params = PaginationParams(page=3, page_size=50)

    assert params.page == 3
    assert params.page_size == 50


def test_pagination_params_page_validation() -> None:
    """Test that page must be >= 1."""
    # Valid page
    params = PaginationParams(page=1)
    assert params.page == 1

    # Invalid page (< 1)
    with pytest.raises(ValidationError) as exc_info:
        PaginationParams(page=0)
    assert "greater than or equal to 1" in str(exc_info.value).lower()

    # Invalid page (negative)
    with pytest.raises(ValidationError) as exc_info:
        PaginationParams(page=-1)
    assert "greater than or equal to 1" in str(exc_info.value).lower()


def test_pagination_params_page_size_validation() -> None:
    """Test that page_size must be between 1 and 100."""
    # Valid page_size (minimum)
    params = PaginationParams(page_size=1)
    assert params.page_size == 1

    # Valid page_size (maximum)
    params = PaginationParams(page_size=100)
    assert params.page_size == 100

    # Invalid page_size (< 1)
    with pytest.raises(ValidationError) as exc_info:
        PaginationParams(page_size=0)
    assert "greater than or equal to 1" in str(exc_info.value).lower()

    # Invalid page_size (> 100)
    with pytest.raises(ValidationError) as exc_info:
        PaginationParams(page_size=101)
    assert "less than or equal to 100" in str(exc_info.value).lower()


def test_pagination_params_offset_calculation() -> None:
    """Test that offset is calculated correctly."""
    # Page 1
    params = PaginationParams(page=1, page_size=20)
    assert params.offset == 0

    # Page 2
    params = PaginationParams(page=2, page_size=20)
    assert params.offset == 20

    # Page 3
    params = PaginationParams(page=3, page_size=20)
    assert params.offset == 40

    # Different page_size
    params = PaginationParams(page=5, page_size=10)
    assert params.offset == 40


def test_paginated_response_structure() -> None:
    """Test PaginatedResponse structure with mock data."""
    products = [
        ProductSchema(id=1, name="Product 1"),
        ProductSchema(id=2, name="Product 2"),
        ProductSchema(id=3, name="Product 3"),
    ]

    response = PaginatedResponse[ProductSchema](
        items=products,
        total=50,
        page=1,
        page_size=20,
    )

    assert len(response.items) == 3
    assert response.items[0].id == 1
    assert response.items[0].name == "Product 1"
    assert response.total == 50
    assert response.page == 1
    assert response.page_size == 20


def test_paginated_response_total_pages_calculation() -> None:
    """Test that total_pages is calculated correctly."""
    # Exact division (100 items, 20 per page = 5 pages)
    response = PaginatedResponse[ProductSchema](
        items=[],
        total=100,
        page=1,
        page_size=20,
    )
    assert response.total_pages == 5

    # Round up (105 items, 20 per page = 6 pages)
    response = PaginatedResponse[ProductSchema](
        items=[],
        total=105,
        page=1,
        page_size=20,
    )
    assert response.total_pages == 6

    # Single page (15 items, 20 per page = 1 page)
    response = PaginatedResponse[ProductSchema](
        items=[],
        total=15,
        page=1,
        page_size=20,
    )
    assert response.total_pages == 1

    # Empty results (0 items = 0 pages)
    response = PaginatedResponse[ProductSchema](
        items=[],
        total=0,
        page=1,
        page_size=20,
    )
    assert response.total_pages == 0

    # Edge case: 1 item, 1 per page = 1 page
    response = PaginatedResponse[ProductSchema](
        items=[],
        total=1,
        page=1,
        page_size=1,
    )
    assert response.total_pages == 1


def test_error_response_structure() -> None:
    """Test ErrorResponse structure."""
    error = ErrorResponse(
        error="Invalid input",
        type="validation_error",
        detail="The provided email is not valid",
    )

    assert error.error == "Invalid input"
    assert error.type == "validation_error"
    assert error.detail == "The provided email is not valid"


def test_error_response_optional_detail() -> None:
    """Test that ErrorResponse detail is optional."""
    error = ErrorResponse(
        error="Server error",
        type="internal_error",
    )

    assert error.error == "Server error"
    assert error.type == "internal_error"
    assert error.detail is None
