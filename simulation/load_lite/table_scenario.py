"""
Reusable per-table scenario: setup 2 players + 1 spectator, drive one full hand.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players, make_client
from simulation.scenarios.s1_two_player_hand import _drive_hand

# Phone prefix per table index — distinct from all existing scenario prefixes
PHONE_PREFIXES = ["+1557000", "+1557100", "+1557200"]


def run_standard_table(
    http: TestClient,
    table_index: int,
) -> tuple[str, object, object, object]:
    """
    Set up 2 players + 1 spectator on one table and drive to HAND_RESULT.

    Returns (table_id, owner, joiner, spectator).
    The owner and spectator are returned for assertion access after contexts close.
    """
    prefix = PHONE_PREFIXES[table_index]
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, prefix)

    spectator = make_client(http, f"{prefix}1003", f"Spectator-{table_index}")
    spectator.join_club(club_id, invite_code)

    with owner.connect(table_id):
        with joiner.connect(table_id):
            with spectator.connect(table_id):
                owner.send_join(table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")

                joiner.send_join(table_id, "player")
                joiner.drain_until("STATE_SNAPSHOT")

                spectator.send_join(table_id, "spectator")
                spectator.drain_until("STATE_SNAPSHOT")

                owner.drain_until("BLINDS_POSTED")
                joiner.drain_until("BLINDS_POSTED")

                _drive_hand(owner, joiner, table_id)

                if not spectator.log.has_type("HAND_RESULT"):
                    spectator.drain_until("HAND_RESULT", max_msgs=100)

    return table_id, owner, joiner, spectator
