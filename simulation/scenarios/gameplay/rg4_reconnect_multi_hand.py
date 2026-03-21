"""
RG4 — Reconnect in Multi-Hand Session

3 players complete hand 1. player3 disconnects after hand 1, reconnects
during the BETWEEN_HANDS_DELAY window, and participates in hand 2.
Verifies: STATE_SNAPSHOT on reconnect, CARDS_DEALT in hand 2 for rejoiner.
"""
from __future__ import annotations

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.gameplay.action_driver import drive_n_player_hand


def run_rg4(http) -> tuple[list[dict], object]:
    """
    Returns (hand_results, player3) where:
      hand_results: list of 2 HAND_RESULT payloads (one per hand)
      player3: the reconnected player (log contains STATE_SNAPSHOT + CARDS_DEALT)
    """
    prefix = "+1559400"
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

            # Hand 1: player3 connects, plays normally, then disconnects
            with player3.connect(table_id):
                player3.send_join(table_id, "player")
                player3.drain_until("STATE_SNAPSHOT")

                result1 = drive_n_player_hand(
                    owner,
                    [owner, joiner, player3],
                    table_id,
                    hand_index=0,
                )
                hand_results.append(result1)
            # player3's WS context exits → server broadcasts PLAYER_STATUS{disconnected}

            # Reconnect player3 during the BETWEEN_HANDS_DELAY (0.05 s window).
            # connect() clears the log — subsequent events start fresh.
            with player3.connect(table_id):
                # send_join on an existing player triggers _do_reconnect in server,
                # which sends STATE_SNAPSHOT and broadcasts PLAYER_STATUS{active}.
                player3.send_join(table_id, "player")
                player3.drain_until("STATE_SNAPSHOT")  # AC-06: must receive this

                result2 = drive_n_player_hand(
                    owner,
                    [owner, joiner, player3],
                    table_id,
                    hand_index=1,
                )
                hand_results.append(result2)
                # player3's log now has STATE_SNAPSHOT + BLINDS_POSTED + CARDS_DEALT
                # + all hand 2 events — CARDS_DEALT presence confirms participation

    return hand_results, player3
