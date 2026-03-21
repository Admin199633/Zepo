"""
RG2 — 4-Player Mixed Actions

4 players, 2 consecutive hands with scripted fold + raise injection.
Verifies: all 4 action types appear in the event log.
"""
from __future__ import annotations

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.gameplay.action_driver import ActionScript, drive_n_player_hand


def run_rg2(http) -> tuple[list[dict], list]:
    """
    Returns (hand_results, players) where:
      hand_results: list of 2 HAND_RESULT payloads
      players: [owner, joiner, player3, player4]
    """
    prefix = "+1559200"
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, prefix)

    player3 = make_client(http, f"{prefix}1003", "Player3")
    player3.join_club(club_id, invite_code)

    player4 = make_client(http, f"{prefix}1004", "Player4")
    player4.join_club(club_id, invite_code)

    # player3 (index 2) folds on their first turn in each hand
    # player4 (index 3) raises on their first turn in each hand (when legal)
    scripts = {
        2: ActionScript(fold_on_turns={(0, 0), (1, 0)}),
        3: ActionScript(raise_on_turns={(0, 0), (1, 0)}),
    }

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

                with player4.connect(table_id):
                    player4.send_join(table_id, "player")
                    player4.drain_until("STATE_SNAPSHOT")

                    for hand_idx in range(2):
                        result = drive_n_player_hand(
                            owner,
                            [owner, joiner, player3, player4],
                            table_id,
                            hand_index=hand_idx,
                            scripts=scripts,
                        )
                        hand_results.append(result)

    players = [owner, joiner, player3, player4]
    return hand_results, players
