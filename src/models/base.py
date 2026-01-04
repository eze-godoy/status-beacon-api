"""SQLAlchemy base model with common fields and utilities."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Naming convention for constraints (important for Alembic migrations)
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides:
    - UUID primary keys
    - Automatic table naming
    - Naming convention for constraints
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Generate table name from class name (snake_case)."""
        name = cls.__name__
        return "".join(f"_{c.lower()}" if c.isupper() else c for c in name).lstrip("_")

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary.

        Returns:
            Dictionary representation of the model.
        """
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
