"""AnalyticsService interface — fire and forget."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .events import AnalyticsEvent, AnalyticsEventType


@runtime_checkable
class AnalyticsService(Protocol):
    async def track(self, event: AnalyticsEvent) -> None: ...


class NoopAnalyticsService:
    """Drop all events. Used in tests and when analytics is disabled."""
    async def track(self, event: AnalyticsEvent) -> None:
        pass


class LoggingAnalyticsService:
    """Print events to stdout — development only."""
    async def track(self, event: AnalyticsEvent) -> None:
        print(f"[ANALYTICS] {event.event_type} user={event.user_id} {event.properties}")
