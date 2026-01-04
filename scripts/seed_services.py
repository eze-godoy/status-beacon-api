#!/usr/bin/env python3
"""Seed script for populating cloud services.

Usage:
    uv run python scripts/seed_services.py

This script is idempotent - running it multiple times will not create
duplicate services (checks by service name before inserting).

To add default services, define them in the DEFAULT_SERVICES list below.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.core.config import get_settings
from src.core.database import create_engine, create_session_factory
from src.models import Service

# Define services to seed here. Each service should have:
# name, provider, status_url, and is_active fields.
DEFAULT_SERVICES: list[dict[str, str | bool]] = []


async def seed_services() -> None:
    """Insert services into the database."""
    if not DEFAULT_SERVICES:
        print("No services defined in DEFAULT_SERVICES. Nothing to seed.")
        return

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    print(f"Connecting to database: {settings.database_url_masked}")

    async with session_factory() as session:
        # Check existing services
        result = await session.execute(select(Service.name))
        existing_names = set(result.scalars().all())

        # Filter to only new services
        new_services = [s for s in DEFAULT_SERVICES if s["name"] not in existing_names]

        if not new_services:
            print("All services already exist. Nothing to seed.")
            await engine.dispose()
            return

        # Insert new services
        for service_data in new_services:
            service = Service(**service_data)  # type: ignore[arg-type]
            session.add(service)
            print(f"  Adding: {service_data['name']}")

        await session.commit()
        print(f"\nSeeded {len(new_services)} new service(s).")

    await engine.dispose()


async def main() -> None:
    """Main entry point."""
    print("Starting service seed...\n")
    try:
        await seed_services()
        print("\nSeed completed successfully!")
    except Exception as e:
        print(f"\nError during seed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
