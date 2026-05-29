"""Add poll_interval_seconds to service table.

Revision ID: f31_poll_interval
Revises: dc218973530a
Create Date: 2026-01-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f31_poll_interval"
down_revision: str | None = "dc218973530a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add poll_interval_seconds column to service table."""
    op.add_column(
        "service",
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove poll_interval_seconds column from service table."""
    op.drop_column("service", "poll_interval_seconds")
