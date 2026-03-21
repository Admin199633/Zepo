"""
LL3 — Spectator Cross-Table Isolation

Three spectators on three simultaneous tables. Each spectator:
- Must NOT receive CARDS_DEALT
- Must NOT receive events with a table_id from another table
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.load_lite.assertions import assert_spectator_isolation
from simulation.scenarios.load_lite.ll1_multi_table import run_ll1


def run(http: TestClient) -> None:
    rows = run_ll1(http)

    for table_id, owner, joiner, spectator in rows:
        assert_spectator_isolation(spectator, table_id)
