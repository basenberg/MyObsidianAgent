"""Tests for shared database models and mixins."""

import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


# Test model using the mixin (not a test class, just a model for testing)
class SampleModel(Base, TimestampMixin):
    """Sample model for testing TimestampMixin."""

    __tablename__ = "test_timestamp_model"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


def test_timestamp_mixin_creates_columns() -> None:
    """Test that TimestampMixin creates created_at and updated_at columns."""
    # Verify columns exist
    assert hasattr(SampleModel, "created_at")
    assert hasattr(SampleModel, "updated_at")

    # Verify column types
    assert SampleModel.created_at is not None
    assert SampleModel.updated_at is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_timestamp_mixin_sets_timestamps_on_creation(db_session: AsyncSession) -> None:
    """Test that timestamps are automatically set on model creation."""
    # Create test instance
    before = datetime.now(UTC)
    test_instance = SampleModel(name="Test")
    db_session.add(test_instance)
    await db_session.commit()
    await db_session.refresh(test_instance)
    after = datetime.now(UTC)

    # Verify timestamps were set
    assert test_instance.created_at is not None
    assert test_instance.updated_at is not None

    # Verify timestamps are within expected range
    assert before <= test_instance.created_at <= after  # pyright: ignore[reportGeneralTypeIssues]
    assert before <= test_instance.updated_at <= after  # pyright: ignore[reportGeneralTypeIssues]

    # Verify created_at and updated_at are approximately the same (within 1ms)
    time_diff = abs((test_instance.created_at - test_instance.updated_at).total_seconds())  # pyright: ignore[reportGeneralTypeIssues]
    assert time_diff < 0.001  # Less than 1 millisecond difference


@pytest.mark.asyncio
@pytest.mark.integration
async def test_timestamp_mixin_updates_updated_at_on_modification(
    db_session: AsyncSession,
) -> None:
    """Test that updated_at changes when the model is modified."""
    # Create test instance
    test_instance = SampleModel(name="Original")
    db_session.add(test_instance)
    await db_session.commit()
    await db_session.refresh(test_instance)

    original_created_at = test_instance.created_at
    original_updated_at = test_instance.updated_at

    # Wait a small amount to ensure timestamp difference
    time.sleep(0.01)

    # Update the instance
    test_instance.name = "Modified"
    await db_session.commit()
    await db_session.refresh(test_instance)

    # Verify created_at didn't change
    assert test_instance.created_at == original_created_at  # pyright: ignore[reportGeneralTypeIssues]

    # Verify updated_at changed
    assert test_instance.updated_at > original_updated_at  # pyright: ignore[reportGeneralTypeIssues]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_timestamp_mixin_timezone_aware(db_session: AsyncSession) -> None:
    """Test that timestamps are timezone-aware."""
    test_instance = SampleModel(name="Timezone Test")
    db_session.add(test_instance)
    await db_session.commit()
    await db_session.refresh(test_instance)

    # Verify timestamps have timezone information
    assert test_instance.created_at.tzinfo is not None  # type: ignore[attr-defined]
    assert test_instance.updated_at.tzinfo is not None  # type: ignore[attr-defined]

    # Verify they're in UTC
    assert test_instance.created_at.tzinfo.utcoffset(None) == UTC.utcoffset(None)  # type: ignore[attr-defined]
    assert test_instance.updated_at.tzinfo.utcoffset(None) == UTC.utcoffset(None)  # type: ignore[attr-defined]
