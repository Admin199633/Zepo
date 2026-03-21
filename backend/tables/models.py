"""
Table domain models (persistence layer — distinct from engine's TableConfig).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from poker_engine.engine.models import TableConfig


@dataclass
class TableRecord:
    """Persisted table record. Owns the TableConfig and links to a club."""
    id: str
    club_id: str
    config: TableConfig
    created_by: str
    created_at: float = 0.0
    is_active: bool = True


@dataclass
class HandSummary:
    """Immutable record written at HAND_END for history and stats."""
    hand_id: str
    table_id: str
    club_id: str
    hand_number: int
    phase_reached: str          # last phase before end
    winner_ids: list[str]
    pot_total: int
    player_ids: list[str]
    stacks_before: dict[str, int]
    stacks_after: dict[str, int]
    community_cards: list[str]  # serialized card strings
    timestamp: float = 0.0
