"""Create initial tables

Revision ID: dc218973530a
Revises:
Create Date: 2026-01-03 20:04:48.395426

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "dc218973530a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial tables."""
    # Service table
    op.create_table(
        "service",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("status_url", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_service"),
    )
    op.create_index("ix_service_name", "service", ["name"], unique=True)
    op.create_index("ix_service_provider", "service", ["provider"], unique=False)
    op.create_index(
        "ix_service_provider_active", "service", ["provider", "is_active"], unique=False
    )

    # Service status table
    op.create_table(
        "service_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name="fk_service_status_service_id_service",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_service_status"),
    )
    op.create_index("ix_service_status_service_id", "service_status", ["service_id"], unique=False)
    op.create_index("ix_service_status_status", "service_status", ["status"], unique=False)
    op.create_index("ix_service_status_checked_at", "service_status", ["checked_at"], unique=False)
    op.create_index(
        "ix_service_status_service_checked",
        "service_status",
        ["service_id", "checked_at"],
        unique=False,
    )
    op.create_index(
        "ix_service_status_status_checked",
        "service_status",
        ["status", "checked_at"],
        unique=False,
    )

    # Incident table
    op.create_table(
        "incident",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("impact", sa.String(20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            name="fk_incident_service_id_service",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incident"),
    )
    op.create_index("ix_incident_service_id", "incident", ["service_id"], unique=False)
    op.create_index("ix_incident_status", "incident", ["status"], unique=False)
    op.create_index("ix_incident_impact", "incident", ["impact"], unique=False)
    op.create_index(
        "uq_incident_service_external",
        "incident",
        ["service_id", "external_id"],
        unique=True,
    )
    op.create_index(
        "ix_incident_status_created",
        "incident",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_incident_service_status",
        "incident",
        ["service_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("incident")
    op.drop_table("service_status")
    op.drop_table("service")
