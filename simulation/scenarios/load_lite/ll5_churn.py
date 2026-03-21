"""
LL5 — Join/Leave Churn

Joiner disconnects mid-hand without reconnecting.
Owner must still receive HAND_RESULT (engine auto-acts for absent player).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players

_CHURN_PREFIX = "+1558300"


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, _CHURN_PREFIX)

    with owner.connect(table_id):
        joiner_ctx = joiner.connect(table_id)
        joiner_ctx.__enter__()
        try:
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")
        finally:
            # Joiner disconnects without reconnecting — engine must resolve the hand
            joiner_ctx.__exit__(None, None, None)

        # Owner waits for hand to resolve (engine auto-acts / auto-folds absent joiner)
        owner.drain_until("HAND_RESULT", max_msgs=200)

    assert owner.log.has_type("HAND_RESULT"), (
        "owner must receive HAND_RESULT after joiner churn"
    )
    assert not owner.log.has_type("ERROR"), (
        f"unexpected ERROR in owner log: {owner.log.of_type('ERROR')}"
    )
