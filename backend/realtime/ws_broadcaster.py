"""
WebSocketBroadcaster — concrete BroadcastService backed by live WebSocket connections.

Connection map: dict[table_id, dict[user_id, ConnectionRecord]]

Safety rules:
  - asyncio.Lock guards all mutations to _connections
  - Broadcast methods copy the connection list inside the lock, then send outside it
    (avoids RuntimeError: dictionary changed size during iteration)
  - _safe_send catches all exceptions — a stale WS never crashes a broadcast
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from .schemas import ServerEnvelope

logger = logging.getLogger(__name__)


@dataclass
class ConnectionRecord:
    websocket: WebSocket
    user_id: str
    table_id: str
    role: str  # "player" | "spectator" | "unknown" (pre-JOIN_TABLE)


class WebSocketBroadcaster:
    """
    Implements BroadcastService Protocol.
    One singleton per server process; shared across all tables.
    """

    def __init__(self) -> None:
        # table_id → { user_id → ConnectionRecord }
        self._connections: dict[str, dict[str, ConnectionRecord]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def register(
        self, table_id: str, user_id: str, ws: WebSocket, role: str
    ) -> None:
        async with self._lock:
            if table_id not in self._connections:
                self._connections[table_id] = {}
            self._connections[table_id][user_id] = ConnectionRecord(
                websocket=ws,
                user_id=user_id,
                table_id=table_id,
                role=role,
            )

    async def update_role(self, table_id: str, user_id: str, role: str) -> None:
        async with self._lock:
            record = self._connections.get(table_id, {}).get(user_id)
            if record:
                record.role = role

    async def unregister(self, table_id: str, user_id: str) -> None:
        async with self._lock:
            table_conns = self._connections.get(table_id)
            if table_conns:
                table_conns.pop(user_id, None)
                if not table_conns:
                    del self._connections[table_id]

    # ------------------------------------------------------------------
    # BroadcastService Protocol implementation
    # ------------------------------------------------------------------

    async def send_to_player(
        self, table_id: str, user_id: str, envelope: ServerEnvelope
    ) -> None:
        async with self._lock:
            record = self._connections.get(table_id, {}).get(user_id)
        if record:
            await self._safe_send(record.websocket, envelope)

    async def broadcast_to_table(
        self,
        table_id: str,
        envelope: ServerEnvelope,
        exclude_user_id: Optional[str] = None,
    ) -> None:
        async with self._lock:
            records = list(self._connections.get(table_id, {}).values())
        for record in records:
            if record.user_id != exclude_user_id:
                await self._safe_send(record.websocket, envelope)

    async def broadcast_to_spectators(
        self, table_id: str, envelope: ServerEnvelope
    ) -> None:
        async with self._lock:
            records = [
                r for r in self._connections.get(table_id, {}).values()
                if r.role == "spectator"
            ]
        for record in records:
            await self._safe_send(record.websocket, envelope)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _safe_send(self, ws: WebSocket, envelope: ServerEnvelope) -> None:
        """Send to a single WebSocket. Swallows all errors — stale handles are normal."""
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_text(envelope.to_json())
        except Exception as exc:
            logger.warning("WebSocket send failed (stale handle): %s", exc)
