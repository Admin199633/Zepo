"""
LL1 — Three Tables Active Concurrently

Three tables launch simultaneously. Each completes ≥1 full hand.
Assertions: HAND_RESULT in both player logs on each table; event ordering;
no ERROR events.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.load_lite.orchestrator import run_all_tables
from simulation.load_lite.table_scenario import run_standard_table
from simulation.load_lite.assertions import (
    assert_hand_completed,
    assert_event_ordering,
    assert_no_errors,
)


def _table_fn(http, table_index: int):
    table_id, owner, joiner, spectator = run_standard_table(http, table_index)
    return table_id, owner


def run(http: TestClient) -> None:
    results = run_all_tables(http, [_table_fn, _table_fn, _table_fn])

    for result in results:
        assert result.passed, (
            f"Table {result.table_index} failed: {result.error}\n"
            f"Events: {result.event_types}"
        )


def run_ll1(http: TestClient) -> list:
    """
    Run LL1 and return raw (table_id, owner, joiner, spectator) tuples
    so callers can apply their own assertions.
    """
    table_results = []
    errors = []

    import threading

    lock = threading.Lock()

    def run_one(idx):
        try:
            row = run_standard_table(http, idx)
            with lock:
                table_results.append((idx, row))
        except Exception as exc:
            with lock:
                errors.append((idx, exc))

    threads = [
        threading.Thread(target=run_one, args=(i,), daemon=True)
        for i in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=45.0)

    stuck = [t.name for t in threads if t.is_alive()]
    if stuck:
        raise AssertionError(f"Threads stuck: {stuck}")

    if errors:
        raise AssertionError(f"Table scenario errors: {errors}")

    # Return sorted by index
    table_results.sort(key=lambda x: x[0])
    return [row for _, row in table_results]
