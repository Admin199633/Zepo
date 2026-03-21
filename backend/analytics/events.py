"""
Analytics event definitions.
All events are fire-and-forget — never block game logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


class AnalyticsEventType(str, Enum):
    LOGIN          = "login"
    JOIN_TABLE     = "join_table"
    LEAVE_TABLE    = "leave_table"
    HAND_START     = "hand_start"
    HAND_END       = "hand_end"
    RECONNECT      = "reconnect"
    SIT_OUT        = "sit_out"
    CHAT_SENT      = "chat_sent"
    NOTIFICATION_OPENED = "notification_opened"


@dataclass
class AnalyticsEvent:
    event_type: AnalyticsEventType
    user_id: str
    properties: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    table_id: str | None = None
    club_id: str | None = None
