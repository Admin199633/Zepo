"""Test helpers: build minimal GameState fixtures."""
from __future__ import annotations

from ..engine.models import (
    GameState, HandPhase, PlayerSession, PlayerStatus, TableConfig,
)


def make_config(**kwargs) -> TableConfig:
    defaults = dict(
        starting_stack=1000,
        small_blind=10,
        big_blind=20,
        turn_timer_seconds=30,
        max_players=10,
        house_rules=[],
    )
    defaults.update(kwargs)
    return TableConfig(**defaults)


def make_player(
    user_id: str,
    display_name: str,
    seat_index: int,
    stack: int = 1000,
    status: PlayerStatus = PlayerStatus.ACTIVE,
) -> PlayerSession:
    return PlayerSession(
        user_id=user_id,
        display_name=display_name,
        seat_index=seat_index,
        stack=stack,
        status=status,
    )


def make_game_state(
    n_players: int = 2,
    stack: int = 1000,
    house_rules: list[str] | None = None,
    **config_kwargs,
) -> GameState:
    """Build a WAITING_FOR_PLAYERS GameState with n_players."""
    config = make_config(house_rules=house_rules or [], **config_kwargs)
    names = ["alice", "bob", "carol", "dave", "eve",
             "frank", "grace", "heidi", "ivan", "judy"]

    players: dict[str, PlayerSession] = {}
    seat_map: dict[int, str] = {}

    for i in range(n_players):
        uid = names[i]
        p = make_player(uid, uid.capitalize(), seat_index=i, stack=stack)
        players[uid] = p
        seat_map[i] = uid

    return GameState(
        table_id="table-1",
        club_id="club-1",
        config=config,
        phase=HandPhase.WAITING_FOR_PLAYERS,
        players=players,
        seat_map=seat_map,
        hand=None,
        hand_number=0,
    )
