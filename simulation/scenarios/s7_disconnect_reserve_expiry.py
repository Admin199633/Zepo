"""
S7 — Disconnect Reserve Expiry

A player disconnects and does NOT reconnect within the reserve window.
The reserve timer fires, moving them to SIT_OUT.
The player then reconnects and sees themselves as SIT_OUT in the snapshot.

The manager's _disconnect_reserve_seconds is patched to 0.1s after the
manager instance is created (on first WS connect), so the test runs fast.
"""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def _drain_until_player_status(client, target_status: str, owner_id: str, max_msgs: int = 50) -> dict:
    """Drain until PLAYER_STATUS{status=target_status} for owner_id is found."""
    for _ in range(max_msgs):
        msg = client.recv_one()
        if (
            msg["type"] == "PLAYER_STATUS"
            and msg["payload"].get("status") == target_status
            and msg["payload"].get("user_id") == owner_id
        ):
            return msg
    raise AssertionError(
        f"PLAYER_STATUS{{status={target_status!r}}} for {owner_id!r} "
        f"not received within {max_msgs} messages"
    )


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555700")

    with joiner.connect(table_id):
        joiner.send_join(table_id, "player")
        joiner.drain_until("STATE_SNAPSHOT")

        # Manager is now created — patch reserve seconds to 0.1s for fast expiry
        manager = http.app.state.registry.get(table_id)
        assert manager is not None, "Manager must exist after first WS connect"
        manager._disconnect_reserve_seconds = 0.1

        owner_ctx = owner.connect(table_id)
        owner_ctx.__enter__()
        try:
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            # Wait for hand to start
            joiner.drain_until("BLINDS_POSTED")
            owner.drain_until("BLINDS_POSTED")
        finally:
            # Owner disconnects — exit WS context triggers disconnect()
            owner_ctx.__exit__(None, None, None)

        # Joiner receives PLAYER_STATUS{disconnected}
        disconnect_event = _drain_until_player_status(joiner, "disconnected", owner.user_id)
        assert disconnect_event["payload"].get("reserve_until", 0) > time.time(), (
            "reserve_until must be in the future"
        )

        # Wait for reserve timer to fire (patched to 0.1s; sleep 0.5s for buffer)
        import time as _time
        _time.sleep(0.5)

        # Joiner receives PLAYER_STATUS{sit_out} — timer fired
        sit_out_event = _drain_until_player_status(joiner, "sit_out", owner.user_id)
        assert sit_out_event["payload"]["user_id"] == owner.user_id

        # Owner reconnects
        owner_ctx2 = owner.connect(table_id)
        owner_ctx2.__enter__()
        try:
            owner.send_join(table_id, "player")
            snap = owner.drain_until("STATE_SNAPSHOT")

            players = snap["payload"].get("players", {})
            assert owner.user_id in players, (
                f"Owner must still be in snapshot after reconnect. "
                f"Players: {list(players.keys())}"
            )
            assert players[owner.user_id]["status"] == "sit_out", (
                f"Owner should be sit_out in snapshot, got: "
                f"{players[owner.user_id]['status']}"
            )
        finally:
            owner_ctx2.__exit__(None, None, None)
