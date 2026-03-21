"""
RG1 — 3-Player Multi-Hand

3 players complete 3 consecutive hands.
Verifies: hand completion, blind rotation, event ordering.
"""
from __future__ import annotations

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.gameplay.action_driver import drive_n_player_hand


def run_rg1(http) -> tuple[list[dict], list]:
    """
    Returns (hand_results, players) where:
      hand_results: list of 3 HAND_RESULT payloads (one per hand)
      players: [owner, joiner, player3]
    """
    prefix = "+1559100"
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, prefix)

    player3 = make_client(http, f"{prefix}1003", "Player3")
    player3.join_club(club_id, invite_code)

    hand_results: list[dict] = []

    with owner.connect(table_id):
        owner.send_join(table_id, "player")
        owner.drain_until("STATE_SNAPSHOT")

        with joiner.connect(table_id):
            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            with player3.connect(table_id):
                player3.send_join(table_id, "player")
                player3.drain_until("STATE_SNAPSHOT")

                # drive_n_player_hand handles BLINDS_POSTED internally
                for hand_idx in range(3):
                    result = drive_n_player_hand(
                        owner,
                        [owner, joiner, player3],
                        table_id,
                        hand_index=hand_idx,
                    )
                    hand_results.append(result)

    players = [owner, joiner, player3]
    return hand_results, players
