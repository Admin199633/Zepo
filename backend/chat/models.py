"""Chat domain models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatMessage:
    id: str
    table_id: str
    user_id: str
    display_name: str
    message: str                # UTF-8 including Hebrew
    timestamp: float = 0.0
    is_system: bool = False     # True for "X joined the table" etc.
