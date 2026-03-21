"""
RG5 — Spectator Over Multi-Hand Session

3 players + 1 spectator. Spectator observes 3 consecutive hands.
Verifies: spectator sees HAND_RESULT for all hands, never receives CARDS_DEALT.
"""
from __future__ import annotations

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.gameplay.action_driver import drive_n_player_hand


def run_rg5(http) -> tuple[str, object]:
    """
    Returns (table_id, spectator) where:
      table_id: the table the spectator watched
      spectator: client whose log is asserted for AC-07 and AC-08
    """
    prefix = "+1559500"
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, prefix)

    player3 = make_client(http, f"{prefix}1003", "Player3")
    player3.join_club(club_id, invite_code)

    spectator = make_client(http, f"{prefix}1004", "Spectator")
    spectator.join_club(club_id, invite_code)

    with owner.connect(table_id):
        owner.send_join(table_id, "player")
        owner.drain_until("STATE_SNAPSHOT")

        with joiner.connect(table_id):
            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            with player3.connect(table_id):
                player3.send_join(table_id, "player")
                player3.drain_until("STATE_SNAPSHOT")

                with spectator.connect(table_id):
                    spectator.send_join(table_id, "spectator")
                    spectator.drain_until("STATE_SNAPSHOT")

                    for hand_idx in range(3):
                        # drive_n_player_hand drains BLINDS_POSTED from the
                        # players; spectator receives it too (broadcast) but
                        # does not need to drain it explicitly — it will
                        # accumulate in the spectator's buffer and be
                        # consumed by the later drain_until("HAND_RESULT").
                        drive_n_player_hand(
                            owner,
                            [owner, joiner, player3],
                            table_id,
                            hand_index=hand_idx,
                        )
                        # Drain spectator through all buffered events up to
                        # HAND_RESULT (large max_msgs to absorb full hand).
                        spectator.drain_until("HAND_RESULT", max_msgs=300)

    return table_id, spectator
