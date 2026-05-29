"""Background tasks for periodic status polling."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.core.config import Settings
    from src.services.status_sync import StatusSyncService

logger = logging.getLogger(__name__)


class BackgroundPoller:
    """Background task for periodic status polling.

    Polls all active services at regular intervals and persists
    the results to the database.
    """

    def __init__(
        self,
        sync_service: StatusSyncService,
        session_factory: async_sessionmaker,
        settings: Settings,
    ) -> None:
        """Initialize background poller.

        Args:
            sync_service: Service for syncing status from providers.
            session_factory: Factory for creating database sessions.
            settings: Application settings.
        """
        self._sync_service = sync_service
        self._session_factory = session_factory
        self._interval = settings.status_poll_interval_seconds
        self._enabled = settings.background_polling_enabled
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start background polling."""
        if not self._enabled:
            logger.info("Background polling is disabled")
            return

        if self._running:
            logger.warning("Background poller already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "Background poller started (interval: %ds)",
            self._interval,
        )

    async def stop(self) -> None:
        """Stop background polling."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Background poller stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        # Initial delay to allow app startup
        await asyncio.sleep(5)

        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("Error in background polling")

            await asyncio.sleep(self._interval)

    async def _poll_once(self) -> None:
        """Execute one polling cycle."""
        async with self._session_factory() as session:
            results = await self._sync_service.sync_all_active_services(session)
            await session.commit()

            success_count = sum(
                1 for r in results.values() if not isinstance(r, Exception)
            )
            error_count = len(results) - success_count

            if results:
                logger.info(
                    "Background poll complete: %d succeeded, %d failed",
                    success_count,
                    error_count,
                )

    @property
    def is_running(self) -> bool:
        """Check if poller is running."""
        return self._running
