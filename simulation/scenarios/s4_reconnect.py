"""
S4 — Reconnect Within 60 Seconds

A player disconnects and reconnects within the reserve window.
The seat must be held and STATE_SNAPSHOT received on reconnect.
Player B must receive PLAYER_STATUS{status=disconnected} with reserve_until populated.
"""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555400")

    with joiner.connect(table_id):
        joiner.send_join(table_id, "player")
        joiner.drain_until("STATE_SNAPSHOT")

        # Owner connects first time
        owner_ctx = owner.connect(table_id)
        owner_ctx.__enter__()
        try:
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            # Wait for hand to start (both players seated)
            joiner.drain_until("BLINDS_POSTED")
            owner.drain_until("BLINDS_POSTED")
        finally:
            # Owner disconnects — exit the WS context
            owner_ctx.__exit__(None, None, None)

        # Joiner must receive PLAYER_STATUS{disconnected}
        disconnect_event = joiner.drain_until("PLAYER_STATUS")
        assert disconnect_event["payload"]["status"] == "disconnected", (
            f"expected disconnected, got {disconnect_event['payload']['status']}"
        )
        assert disconnect_event["payload"]["user_id"] == owner.user_id

        # reserve_until must be populated and in the future
        reserve_until = disconnect_event["payload"].get("reserve_until")
        assert reserve_until is not None, "reserve_until must be set on disconnect event"
        assert reserve_until > time.time(), "reserve_until must be in the future"

        # Reconnect within 1 second (well within 60 s window)
        owner_ctx2 = owner.connect(table_id)
        owner_ctx2.__enter__()
        try:
            # JOIN_TABLE on a player already in state → triggers _do_reconnect
            owner.send_join(table_id, "player")
            snap = owner.drain_until("STATE_SNAPSHOT")

            # Seat is held — player is still in the snapshot
            players_in_snap = snap["payload"].get("players", {})
            assert owner.user_id in players_in_snap, (
                f"owner must still be in STATE_SNAPSHOT after reconnect. "
                f"Players in snap: {list(players_in_snap.keys())}"
            )
        finally:
            owner_ctx2.__exit__(None, None, None)
