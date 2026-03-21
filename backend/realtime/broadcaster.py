"""
BroadcastService — interface for sending WebSocket messages.

The session manager depends on this interface, not on any specific WS framework.
In production this is implemented by the FastAPI WebSocket gateway.
In tests this is implemented by CapturingBroadcaster.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from .schemas import ServerEnvelope


@runtime_checkable
class BroadcastService(Protocol):

    async def send_to_player(
        self, table_id: str, user_id: str, envelope: ServerEnvelope
    ) -> None:
        """Send a message to a specific seated player."""
        ...

    async def broadcast_to_table(
        self,
        table_id: str,
        envelope: ServerEnvelope,
        exclude_user_id: Optional[str] = None,
    ) -> None:
        """Send to all connected players and spectators at the table."""
        ...

    async def broadcast_to_spectators(
        self, table_id: str, envelope: ServerEnvelope
    ) -> None:
        """Send to spectators only (used when player-specific events have
        a different payload, e.g. hole cards masked differently)."""
        ...


# ---------------------------------------------------------------------------
# In-memory capturing broadcaster (for tests)
# ---------------------------------------------------------------------------

class CapturingBroadcaster:
    """
    Records every message sent.
    Useful for asserting what events were emitted in tests.
    """

    def __init__(self) -> None:
        self.sent_to_player:   list[tuple[str, str, ServerEnvelope]] = []
        self.broadcasts:       list[tuple[str, ServerEnvelope]] = []
        self.spectator_broadcasts: list[tuple[str, ServerEnvelope]] = []

    async def send_to_player(
        self, table_id: str, user_id: str, envelope: ServerEnvelope
    ) -> None:
        self.sent_to_player.append((table_id, user_id, envelope))

    async def broadcast_to_table(
        self,
        table_id: str,
        envelope: ServerEnvelope,
        exclude_user_id: Optional[str] = None,
    ) -> None:
        self.broadcasts.append((table_id, envelope))

    async def broadcast_to_spectators(
        self, table_id: str, envelope: ServerEnvelope
    ) -> None:
        self.spectator_broadcasts.append((table_id, envelope))

    # --- helpers for assertions ---

    def all_event_types(self) -> list[str]:
        all_msgs = (
            [e for _, _, e in self.sent_to_player]
            + [e for _, e in self.broadcasts]
            + [e for _, e in self.spectator_broadcasts]
        )
        return [m.type.value for m in all_msgs]

    def broadcasts_of_type(self, event_type: str) -> list[ServerEnvelope]:
        return [e for _, e in self.broadcasts if e.type.value == event_type]

    def player_messages_of_type(
        self, user_id: str, event_type: str
    ) -> list[ServerEnvelope]:
        return [
            e for tid, uid, e in self.sent_to_player
            if uid == user_id and e.type.value == event_type
        ]

    def reset(self) -> None:
        self.sent_to_player.clear()
        self.broadcasts.clear()
        self.spectator_broadcasts.clear()
