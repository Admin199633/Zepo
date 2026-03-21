"""
Session-layer models (above the engine layer).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class JoinErrorCode(str, Enum):
    TABLE_FULL          = "TABLE_FULL"
    ALREADY_SEATED      = "ALREADY_SEATED"
    NOT_MEMBER          = "NOT_MEMBER"
    USER_BLOCKED        = "USER_BLOCKED"
    TABLE_NOT_FOUND     = "TABLE_NOT_FOUND"
    INTERNAL_ERROR      = "INTERNAL_ERROR"


@dataclass
class JoinResult:
    success: bool
    role: Optional[Literal["player", "spectator"]] = None
    seat_index: Optional[int] = None
    error_code: Optional[JoinErrorCode] = None
    error_message: Optional[str] = None


@dataclass
class ReconnectResult:
    success: bool
    role: Optional[Literal["player", "spectator"]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class SpectatorInfo:
    user_id: str
    display_name: str
    connection_id: str
    joined_at: float = 0.0


@dataclass
class ConnectionInfo:
    """Maps a live connection to its role."""
    connection_id: str
    user_id: str
    role: Literal["player", "spectator"]
