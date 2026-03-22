"""
GET   /clubs/{club_id}/table
PATCH /clubs/{club_id}/table/config
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth.models import User
from ..dependencies import get_current_user, get_persistence, http_error
from ..persistence.adapter import PersistenceAdapter
from ..tables.models import HandSummary, TableRecord
from poker_engine.engine.models import TableConfig

router = APIRouter(prefix="/clubs", tags=["tables"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TableConfigDTO(BaseModel):
    starting_stack: int
    small_blind: int
    big_blind: int
    turn_timer_seconds: int
    max_players: int
    house_rules: list[str]
    rule_params: dict = {}


class TableResponse(BaseModel):
    table_id: str
    config: TableConfigDTO
    recent_hands: list[dict]  # serialised HandSummary dicts


def _config_dto(config: TableConfig) -> TableConfigDTO:
    return TableConfigDTO(
        starting_stack=config.starting_stack,
        small_blind=config.small_blind,
        big_blind=config.big_blind,
        turn_timer_seconds=config.turn_timer_seconds,
        max_players=config.max_players,
        house_rules=list(config.house_rules),
        rule_params=dict(config.rule_params),
    )


def _summary_dict(s: HandSummary) -> dict:
    return {
        "hand_id": s.hand_id,
        "hand_number": s.hand_number,
        "pot_total": s.pot_total,
        "winner_ids": s.winner_ids,
        "phase_reached": s.phase_reached,
        "timestamp": s.timestamp,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{club_id}/table", response_model=TableResponse)
async def get_club_table(
    club_id: str,
    current_user: User = Depends(get_current_user),
    persistence: PersistenceAdapter = Depends(get_persistence),
) -> TableResponse:
    club = await persistence.get_club(club_id)
    if club is None:
        raise http_error("NOT_FOUND", "Club not found.", status=404)
    if not club.is_member(current_user.id):
        raise http_error("NOT_MEMBER", "You are not a member of this club.", status=403)

    table = await persistence.get_club_table(club_id)
    if table is None:
        raise http_error("NOT_FOUND", "Table not found.", status=404)

    history = await persistence.get_hand_history(table.id, limit=20)

    return TableResponse(
        table_id=table.id,
        config=_config_dto(table.config),
        recent_hands=[_summary_dict(h) for h in history],
    )


