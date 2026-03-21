"""Stats domain models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlayerStats:
    user_id: str
    club_id: str
    display_name: str
    hands_played: int = 0
    wins: int = 0
    total_won: int = 0      # net chips won (can be negative)
    total_lost: int = 0

    @property
    def win_rate(self) -> float:
        if self.hands_played == 0:
            return 0.0
        return self.wins / self.hands_played


@dataclass
class StatsDelta:
    """Applied atomically after each hand."""
    hands_played_delta: int = 1
    wins_delta: int = 0
    chips_won: int = 0
    chips_lost: int = 0
