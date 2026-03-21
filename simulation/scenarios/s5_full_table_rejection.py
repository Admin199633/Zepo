"""
S5 — Full-Table Rejection

An extra player attempting to join a full table receives ERROR{TABLE_FULL}.
The WS connection remains open after the error.
The player can subsequently join as a spectator.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import make_client, setup_two_players


def run(http: TestClient) -> None:
    # Use a 2-player max table for speed (avoids creating 10 players)
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, "+1555500")

    # Reduce max_players to 2 so we hit TABLE_FULL with just 3 clients
    owner.patch_table_config(club_id, max_players=2)

    # Third client must be a club member to connect to the WS at all
    overflow = make_client(http, "+15555001003", "Overflow")
    overflow.join_club(club_id, invite_code)

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            with overflow.connect(table_id):
                # Table is now full (2/2) — overflow tries to join as player
                overflow.send_join(table_id, "player")
                error_msg = overflow.drain_until("ERROR")

                assert error_msg["payload"]["code"] == "TABLE_FULL", (
                    f"expected TABLE_FULL error, got: {error_msg['payload']['code']}"
                )

                # Connection must still be open — can join as spectator
                overflow.send_join(table_id, "spectator")
                snap = overflow.drain_until("STATE_SNAPSHOT")
                assert snap["payload"]["table_id"] == table_id, \
                    "overflow client must receive STATE_SNAPSHOT as spectator"
