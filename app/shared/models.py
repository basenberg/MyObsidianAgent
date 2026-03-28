"""Shared database models and mixins."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(UTC)


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps.

    All models should inherit this mixin to automatically track
    when records are created and updated.

    Example:
        class Product(Base, TimestampMixin):
            __tablename__ = "products"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(200))
    """

    @declared_attr.directive
    def created_at(cls) -> Mapped[datetime]:
        """Timestamp when the record was created."""
        return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    @declared_attr.directive
    def updated_at(cls) -> Mapped[datetime]:
        """Timestamp when the record was last updated."""
        return mapped_column(
            DateTime(timezone=True),
            default=utcnow,
            onupdate=utcnow,
            nullable=False,
        )
