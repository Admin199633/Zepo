"""ChatService interface."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ChatMessage


@runtime_checkable
class ChatService(Protocol):
    async def send_message(
        self, table_id: str, user_id: str, display_name: str, text: str
    ) -> ChatMessage: ...

    async def get_recent(self, table_id: str, limit: int = 50) -> list[ChatMessage]: ...
    async def send_system_message(self, table_id: str, text: str) -> ChatMessage: ...
