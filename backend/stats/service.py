"""StatsService interface."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import PlayerStats, StatsDelta


@runtime_checkable
class StatsService(Protocol):
    async def record_hand_result(
        self,
        club_id: str,
        player_deltas: dict[str, StatsDelta],   # user_id → delta
    ) -> None: ...

    async def get_leaderboard(self, club_id: str, limit: int = 20) -> list[PlayerStats]: ...
    async def get_player_stats(self, club_id: str, user_id: str) -> PlayerStats | None: ...
