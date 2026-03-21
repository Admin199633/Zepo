"""
LL4 — Reconnect During Concurrent Table Activity

Table 0: owner disconnects after BLINDS_POSTED then reconnects.
Tables 1 and 2: run standard full hand in parallel.

All 3 threads launch simultaneously so table 0's reconnect happens
while the backend is concurrently handling tables 1 and 2.
"""
from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players
from simulation.load_lite.table_scenario import run_standard_table
from simulation.load_lite.assertions import assert_hand_completed, assert_no_errors

# Separate prefix namespace from LL1-LL3 to avoid phone collisions when
# both sets of tests run in the same pytest session.
_RECONNECT_TABLE_PREFIX = "+1558000"
_SIDE_PREFIXES = ["+1558100", "+1558200"]


def _run_reconnect_table(http) -> tuple[str, object, object]:
    """
    Table 0: two players join, hand starts, owner disconnects, then reconnects.
    Returns (table_id, owner, joiner).
    """
    owner, joiner, club_id, table_id, _ = setup_two_players(
        http, _RECONNECT_TABLE_PREFIX
    )

    with joiner.connect(table_id):
        joiner.send_join(table_id, "player")
        joiner.drain_until("STATE_SNAPSHOT")

        owner_ctx = owner.connect(table_id)
        owner_ctx.__enter__()
        try:
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.drain_until("BLINDS_POSTED")
            owner.drain_until("BLINDS_POSTED")
        finally:
            owner_ctx.__exit__(None, None, None)

        # Joiner must see PLAYER_STATUS{disconnected}
        disconnect_event = joiner.drain_until("PLAYER_STATUS", max_msgs=50)
        assert disconnect_event["payload"]["status"] == "disconnected", (
            f"expected status=disconnected, got {disconnect_event['payload']['status']}"
        )
        assert disconnect_event["payload"]["user_id"] == owner.user_id
        reserve_until = disconnect_event["payload"].get("reserve_until")
        assert reserve_until is not None, "reserve_until must be set on disconnect event"
        assert reserve_until > time.time(), "reserve_until must be in the future"

        # Reconnect
        owner_ctx2 = owner.connect(table_id)
        owner_ctx2.__enter__()
        try:
            owner.send_join(table_id, "player")
            snap = owner.drain_until("STATE_SNAPSHOT")
            players_in_snap = snap["payload"].get("players", {})
            assert owner.user_id in players_in_snap, (
                f"owner must be in STATE_SNAPSHOT after reconnect. "
                f"Players: {list(players_in_snap.keys())}"
            )
        finally:
            owner_ctx2.__exit__(None, None, None)

    return table_id, owner, joiner


def run(http: TestClient) -> None:
    side_results = []
    errors = []
    lock = threading.Lock()

    def run_side(idx: int) -> None:
        try:
            # Use idx+1 for side table to map to prefix index 1 or 2
            from simulation.helpers import setup_two_players, make_client
            from simulation.scenarios.s1_two_player_hand import _drive_hand

            prefix = _SIDE_PREFIXES[idx]
            owner, joiner, club_id, table_id, _ = setup_two_players(http, prefix)
            with owner.connect(table_id):
                with joiner.connect(table_id):
                    owner.send_join(table_id, "player")
                    owner.drain_until("STATE_SNAPSHOT")
                    joiner.send_join(table_id, "player")
                    joiner.drain_until("STATE_SNAPSHOT")
                    owner.drain_until("BLINDS_POSTED")
                    joiner.drain_until("BLINDS_POSTED")
                    _drive_hand(owner, joiner, table_id)
            with lock:
                side_results.append((table_id, owner, joiner))
        except Exception as exc:
            with lock:
                errors.append((idx, exc))

    # Launch all 3 threads together
    reconnect_result = {}

    def run_reconnect() -> None:
        try:
            table_id, owner, joiner = _run_reconnect_table(http)
            with lock:
                reconnect_result["data"] = (table_id, owner, joiner)
        except Exception as exc:
            with lock:
                errors.append(("reconnect", exc))

    threads = [
        threading.Thread(target=run_reconnect, daemon=True, name="ll4-reconnect"),
        threading.Thread(target=run_side, args=(0,), daemon=True, name="ll4-side-0"),
        threading.Thread(target=run_side, args=(1,), daemon=True, name="ll4-side-1"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=45.0)

    stuck = [t.name for t in threads if t.is_alive()]
    if stuck:
        raise AssertionError(f"LL4 threads stuck: {stuck}")

    if errors:
        raise AssertionError(f"LL4 errors: {errors}")

    # Side tables completed full hands
    assert len(side_results) == 2, f"Expected 2 side table results, got {len(side_results)}"
    for table_id, owner, joiner in side_results:
        assert_hand_completed(owner, joiner, table_id)
        assert_no_errors(owner, joiner, table_id=table_id)
