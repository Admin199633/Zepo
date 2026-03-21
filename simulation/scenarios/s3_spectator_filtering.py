"""
S3 — Spectator Event Filtering

A spectator connects while a hand is in progress.
They must receive all broadcast events and NEVER receive CARDS_DEALT.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.s1_two_player_hand import _drive_hand


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, "+1555300")

    # Spectator joins the club (must be a member)
    spectator = make_client(http, "+15553001003", "Watcher")
    spectator.join_club(club_id, invite_code)

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            with spectator.connect(table_id):
                spectator.send_join(table_id, "spectator")
                spectator.drain_until("STATE_SNAPSHOT")

                # Drive the hand to completion, spectator drains passively
                _drive_hand(owner, joiner, table_id)

                # Spectator must see HAND_RESULT
                spectator.drain_until("HAND_RESULT", max_msgs=100)

    # Critical assertion: spectator NEVER received CARDS_DEALT
    assert not spectator.log.has_type("CARDS_DEALT"), (
        f"spectator MUST NOT receive CARDS_DEALT. "
        f"Got event types: {spectator.log.types()}"
    )

    # Spectator must have received expected broadcast events
    assert spectator.log.has_type("HAND_RESULT"), "spectator must receive HAND_RESULT"
    assert spectator.log.has_type("TURN_CHANGED"), "spectator must receive TURN_CHANGED"
    assert spectator.log.has_type("PLAYER_ACTED") or spectator.log.has_type("BLINDS_POSTED"), \
        "spectator must receive game events (PLAYER_ACTED or BLINDS_POSTED)"
