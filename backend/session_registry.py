"""
TableSessionRegistry — singleton map of table_id → TableSessionManager.

Safety: asyncio.Lock wraps the full check-and-insert in get_or_create.
This prevents a race where two coroutines both see a missing entry and
each create a separate TableSessionManager for the same table.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from poker_engine.engine.models import TableConfig

from .config import settings
from .persistence.adapter import PersistenceAdapter
from .realtime.broadcaster import BroadcastService
from .sessions.session_manager import TableSessionManager


class TableSessionRegistry:
    """
    Holds all live TableSessionManager instances.
    Created once at app startup; lives for the process lifetime.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, TableSessionManager] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    async def get_or_create(
        self,
        table_id: str,
        club_id: str,
        config: TableConfig,
        persistence: PersistenceAdapter,
        broadcaster: BroadcastService,
    ) -> TableSessionManager:
        """
        Return the existing manager for table_id, or create one if absent.
        The check-and-insert is atomic under the lock.
        """
        async with self._lock:
            if table_id not in self._sessions:
                self._sessions[table_id] = TableSessionManager(
                    table_id=table_id,
                    club_id=club_id,
                    config=config,
                    persistence=persistence,
                    broadcaster=broadcaster,
                    disconnect_reserve_seconds=settings.disconnect_timeout_seconds,
                )
            return self._sessions[table_id]

    def get(self, table_id: str) -> Optional[TableSessionManager]:
        """Return the manager if it exists; None otherwise. No lock needed (read-only)."""
        return self._sessions.get(table_id)

    async def remove(self, table_id: str) -> None:
        async with self._lock:
            self._sessions.pop(table_id, None)
