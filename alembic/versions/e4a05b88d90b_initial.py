"""initial

Revision ID: e4a05b88d90b
Revises:
Create Date: 2025-10-29 14:12:36.619730

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e4a05b88d90b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
