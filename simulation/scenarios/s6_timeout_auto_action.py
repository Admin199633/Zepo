"""
S6 — Timeout Auto-Action

When a player does not act within the turn timer, the engine auto-acts.
PLAYER_ACTED must be broadcast within a generous observation window.

Turn timer is set to 2 seconds via PATCH /table/config.
We wait up to 5 seconds (via drain_until with large max_msgs window).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


# How many messages to drain looking for PLAYER_ACTED.
# At ~2 s timer, the background asyncio loop fires the timeout; other events
# (TURN_CHANGED, CARDS_DEALT, BLINDS_POSTED) may arrive first.
_DRAIN_WINDOW = 50


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555600")

    # Set a short turn timer so the timeout fires quickly
    owner.patch_table_config(club_id, turn_timer_seconds=2)

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            # Wait for TURN_CHANGED — a player's turn has begun
            # We use joiner as the observer (they do NOT act)
            owner.drain_until("BLINDS_POSTED")
            turn_msg = joiner.drain_until("TURN_CHANGED", max_msgs=_DRAIN_WINDOW)

            acting_user_id = turn_msg["payload"]["user_id"]

            # If it's joiner's turn: joiner doesn't act → observe on owner
            # If it's owner's turn: owner doesn't act → observe on joiner
            observer = joiner if acting_user_id == owner.user_id else owner

            # Observer waits for PLAYER_ACTED — the timeout auto-action
            acted_msg = observer.drain_until("PLAYER_ACTED", max_msgs=_DRAIN_WINDOW)

            assert acted_msg["payload"]["user_id"] == acting_user_id, (
                f"expected auto-action for {acting_user_id}, "
                f"got {acted_msg['payload']['user_id']}"
            )
            assert acted_msg["payload"]["action"] in ("check", "fold", "call"), (
                f"auto-action must be check/fold/call, got {acted_msg['payload']['action']}"
            )

            # Game continues: observe another TURN_CHANGED or HAND_RESULT
            next_msg = observer.drain_until(
                "TURN_CHANGED" if _more_turns_expected(acted_msg) else "HAND_RESULT",
                max_msgs=_DRAIN_WINDOW,
            )
            assert next_msg["type"] in ("TURN_CHANGED", "HAND_RESULT"), (
                f"expected game continuation, got: {next_msg['type']}"
            )


def _more_turns_expected(acted_msg: dict) -> bool:
    """
    After a fold/all-in, hand may end immediately.
    After check/call, more turns typically follow.
    """
    action = acted_msg["payload"].get("action", "")
    return action in ("check", "call")
