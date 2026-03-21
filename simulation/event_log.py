"""
Per-client event capture.

All server envelopes received over WebSocket are stored here for later assertion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapturedEvent:
    type: str
    payload: dict[str, Any]
    seq: int
    ts: float


class EventLog:
    """Thread-safe append-only log of captured server envelopes."""

    def __init__(self) -> None:
        self._events: list[CapturedEvent] = []

    def append(self, raw: dict) -> None:
        self._events.append(CapturedEvent(
            type=raw.get("type", ""),
            payload=raw.get("payload", {}),
            seq=raw.get("seq", 0),
            ts=raw.get("ts", 0.0),
        ))

    def all(self) -> list[CapturedEvent]:
        return list(self._events)

    def of_type(self, event_type: str) -> list[CapturedEvent]:
        return [e for e in self._events if e.type == event_type]

    def has_type(self, event_type: str) -> bool:
        return any(e.type == event_type for e in self._events)

    def types(self) -> list[str]:
        return [e.type for e in self._events]

    def clear(self) -> None:
        self._events.clear()
