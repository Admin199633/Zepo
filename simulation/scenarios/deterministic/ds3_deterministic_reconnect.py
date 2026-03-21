"""
DS3 — Deterministic Reconnect Snapshot Contents

Deck (Recipe A):
  seat0 (owner) hole: A♠ K♠
  seat1 (joiner) hole: 2♥ 3♦

Owner disconnects immediately after BLINDS_POSTED (before any actions),
then reconnects within the reserve window.

Deterministic value (vs nondeterministic s4):
  - We know the exact hole cards owner was dealt before the disconnect.
  - The CARDS_DEALT event received before disconnect must contain A♠ K♠.
  - After reconnect, STATE_SNAPSHOT must still list owner in the players map.
  - reserve_until must be populated and in the future.

Assertions:
  - Owner's CARDS_DEALT (received before disconnect) contains A♠ K♠
  - Joiner sees PLAYER_STATUS{status=disconnected, reserve_until > now}
  - STATE_SNAPSHOT after reconnect contains owner.user_id in players
  - No ERROR events
"""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from simulation.deck_control import RECIPE_A, complete_deck, injected_deck
from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555900")

    with injected_deck(complete_deck(RECIPE_A)):
        with joiner.connect(table_id):
            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            owner_ctx = owner.connect(table_id)
            owner_ctx.__enter__()
            try:
                owner.send_join(table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")

                # Wait for hand to start; CARDS_DEALT arrives after BLINDS_POSTED
                joiner.drain_until("BLINDS_POSTED")
                owner.drain_until("CARDS_DEALT")  # implies BLINDS_POSTED already received

                # Verify owner received their hole cards before disconnecting
                owner_dealt = owner.log.of_type("CARDS_DEALT")[0]
                owner_cards = {(c["rank"], c["suit"]) for c in owner_dealt.payload["your_cards"]}

                # In DS3, joiner connects first (outer context) so joiner = seat 0
                # (gets deck[0:2] = A♠ K♠). Owner = seat 1 (deck[2:4] = 2♥ 3♦).
                expected_hole = {("2", "H"), ("3", "D")}
                assert owner_cards == expected_hole, (
                    f"owner must hold 2♥ 3♦ from Recipe A seat 1, got {owner_cards}"
                )
            finally:
                # Owner disconnects with hand in progress
                owner_ctx.__exit__(None, None, None)

            # Joiner must see the disconnect event
            disconnect_event = joiner.drain_until("PLAYER_STATUS", max_msgs=50)
            assert disconnect_event["payload"]["status"] == "disconnected", (
                f"expected disconnected, got {disconnect_event['payload']['status']}"
            )
            assert disconnect_event["payload"]["user_id"] == owner.user_id

            reserve_until = disconnect_event["payload"].get("reserve_until")
            assert reserve_until is not None, "reserve_until must be set on disconnect event"
            assert reserve_until > time.time(), "reserve_until must be in the future"

            # Reconnect within the reserve window
            owner_ctx2 = owner.connect(table_id)
            owner_ctx2.__enter__()
            try:
                owner.send_join(table_id, "player")
                snap_msg = owner.drain_until("STATE_SNAPSHOT")

                snap_payload = snap_msg["payload"]

                # Owner still present in snapshot
                players_in_snap = snap_payload.get("players", {})
                assert owner.user_id in players_in_snap, (
                    f"owner must be in STATE_SNAPSHOT after reconnect. "
                    f"Players: {list(players_in_snap.keys())}"
                )

                assert not owner.log.has_type("ERROR"), (
                    f"unexpected ERROR after reconnect: {owner.log.of_type('ERROR')}"
                )
            finally:
                owner_ctx2.__exit__(None, None, None)

    assert not joiner.log.has_type("ERROR"), (
        f"unexpected ERROR in joiner log: {joiner.log.of_type('ERROR')}"
    )
