"""
RG6 — Session Continuity Summary

3 players, 4 consecutive hands. Structural continuity assertions:
  - hand_number increments (verified via post-session STATE_SNAPSHOT on reconnect)
  - chip conservation across hands
  - session completes within 90 seconds
"""
from __future__ import annotations

import time

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.gameplay.action_driver import drive_n_player_hand


def run_rg6(http) -> tuple[list[dict], list, float, dict]:
    """
    Returns (hand_results, players, elapsed_seconds, final_stacks) where:
      hand_results:      list of 4 HAND_RESULT payloads
      players:           [owner, joiner, player3]
      elapsed_seconds:   wall-clock time for the 4-hand session
      final_stacks:      {user_id: stack, "__hand_number__": N}
                         populated from a fresh STATE_SNAPSHOT via owner reconnect
    """
    prefix = "+1559600"
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, prefix)

    player3 = make_client(http, f"{prefix}1003", "Player3")
    player3.join_club(club_id, invite_code)

    hand_results: list[dict] = []
    start_time = time.time()

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
                for hand_idx in range(4):
                    result = drive_n_player_hand(
                        owner,
                        [owner, joiner, player3],
                        table_id,
                        hand_index=hand_idx,
                    )
                    hand_results.append(result)

    elapsed = time.time() - start_time

    # Reconnect owner to obtain a fresh STATE_SNAPSHOT with the authoritative
    # hand_number and all player stacks after 4 hands.
    # connect() clears the log, so hand_results (saved above) are unaffected.
    with owner.connect(table_id):
        owner.send_join(table_id, "player")
        snap = owner.drain_until("STATE_SNAPSHOT")
        snap_payload = snap["payload"]

        final_stacks: dict = {
            uid: p_data["stack"]
            for uid, p_data in snap_payload.get("players", {}).items()
        }
        final_stacks["__hand_number__"] = snap_payload.get("hand_number", -1)

    players = [owner, joiner, player3]
    return hand_results, players, elapsed, final_stacks
