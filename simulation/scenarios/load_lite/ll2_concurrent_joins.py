"""
LL2 — Concurrent Player Joins Across All Three Tables

Same as LL1 but focuses on the join phase. Each table's STATE_SNAPSHOT
must contain at least 1 player entry. No ERROR events.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.load_lite.table_scenario import run_standard_table
from simulation.load_lite.assertions import assert_no_errors
from simulation.scenarios.load_lite.ll1_multi_table import run_ll1


def run(http: TestClient) -> None:
    rows = run_ll1(http)

    for table_id, owner, joiner, spectator in rows:
        assert_no_errors(owner, joiner, spectator, table_id=table_id)
        # Both players must have received STATE_SNAPSHOT (captured in log)
        assert owner.log.has_type("STATE_SNAPSHOT"), (
            f"[{table_id}] owner never received STATE_SNAPSHOT"
        )
        assert joiner.log.has_type("STATE_SNAPSHOT"), (
            f"[{table_id}] joiner never received STATE_SNAPSHOT"
        )
        # Verify at least 1 player was in the snapshot payload
        snap = owner.log.of_type("STATE_SNAPSHOT")[0]
        players = snap.payload.get("players", {})
        assert len(players) >= 1, (
            f"[{table_id}] STATE_SNAPSHOT contained no players: {snap.payload}"
        )
