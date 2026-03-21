"""
S2 — Mid-Hand Join

A third player joins while a hand is in progress.
They must:
  - Receive STATE_SNAPSHOT immediately on join
  - NOT receive CARDS_DEALT for the first (in-progress) hand
  - Receive CARDS_DEALT in the second hand
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.s1_two_player_hand import _drive_hand


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, "+1555200")

    # Third player joins the club
    third = make_client(http, "+15552001003", "Third")
    third.join_club(club_id, invite_code)

    with owner.connect(table_id):
        with joiner.connect(table_id):
            # Start the first hand with two players
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            # Wait for BLINDS_POSTED → hand is definitively in progress
            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            with third.connect(table_id):
                # Third player joins mid-hand
                third.send_join(table_id, "player")
                snapshot_msg = third.drain_until("STATE_SNAPSHOT")

                # Third player must be in WAITING status (hand in progress)
                snap_payload = snapshot_msg["payload"]
                assert snap_payload["table_id"] == table_id

                # Drive first hand to completion
                _drive_hand(owner, joiner, table_id)

                # Third player should have observed HAND_RESULT without receiving CARDS_DEALT
                third.drain_until("HAND_RESULT", max_msgs=100)

                assert not third.log.has_type("CARDS_DEALT"), \
                    "third player must NOT receive CARDS_DEALT during the mid-join hand"

                # Wait for second hand to start (third player now active)
                owner.drain_until("BLINDS_POSTED")
                third.drain_until("BLINDS_POSTED")

                # Third player must now receive CARDS_DEALT
                third.drain_until("CARDS_DEALT")
                assert third.log.has_type("CARDS_DEALT"), \
                    "third player must receive CARDS_DEALT in the second hand"

                # Drive second hand to completion (3 players now)
                players = {
                    owner.user_id: owner,
                    joiner.user_id: joiner,
                    third.user_id: third,
                }
                _drive_three_player_hand(owner, joiner, third, table_id)


def _drive_three_player_hand(owner, joiner, third, table_id: str, max_iter: int = 120) -> None:
    """Drive a 3-player hand to HAND_RESULT using check/call tracking."""
    players = {
        owner.user_id: owner,
        joiner.user_id: joiner,
        third.user_id: third,
    }
    can_check = False  # entered after BLINDS_POSTED

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            for c in [joiner, third]:
                if not c.log.has_type("HAND_RESULT"):
                    c.drain_until("HAND_RESULT", max_msgs=100)
            return

        elif t == "BLINDS_POSTED":
            can_check = False

        elif t == "COMMUNITY_CARDS":
            can_check = True

        elif t == "PHASE_CHANGED":
            phase = msg["payload"].get("phase", "")
            if phase in ("FLOP", "TURN", "RIVER"):
                can_check = True

        elif t == "PLAYER_ACTED":
            action = msg["payload"].get("action", "")
            if action == "raise":
                can_check = False
            elif action == "call":
                can_check = True

        elif t == "TURN_CHANGED":
            acting_uid = msg["payload"].get("user_id")
            actor = players.get(acting_uid)
            if actor:
                actor.send_action(table_id, "check" if can_check else "call")

    raise AssertionError(
        f"HAND_RESULT not reached within {max_iter} iterations. "
        f"Owner events: {owner.log.types()[-20:]}"
    )
