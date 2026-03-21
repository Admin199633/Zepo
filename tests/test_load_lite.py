"""
Load-lite simulation tests.

Runs 3 tables concurrently to validate multi-table correctness under
real threading concurrency. Assertions are structural (event ordering,
absence of forbidden events, session liveness) — not timing-based.

Total runtime target: < 60 seconds.
"""
from __future__ import annotations

import pytest

from simulation.app_factory import make_test_client, restore_delays
from simulation.load_lite.assertions import (
    assert_hand_completed,
    assert_event_ordering,
    assert_no_errors,
    assert_spectator_isolation,
    assert_all_results_passed,
)
from simulation.scenarios.load_lite import (
    run_ll1,
    run_ll2,
    run_ll3,
    run_ll4,
    run_ll5,
    run_ll6,
)


@pytest.fixture
def http():
    """Live TestClient with fast delays and deterministic auth."""
    client = make_test_client(between_hands_delay=0.05)
    yield client
    try:
        client.__exit__(None, None, None)
    except Exception:
        pass
    restore_delays()


def test_ll1_multi_table(http):
    """Three tables complete ≥1 hand each concurrently; no cross-table errors."""
    from simulation.scenarios.load_lite.ll1_multi_table import run_ll1 as _run

    rows = _run(http)
    assert len(rows) == 3, f"Expected 3 table results, got {len(rows)}"

    for table_id, owner, joiner, spectator in rows:
        assert_hand_completed(owner, joiner, table_id)
        assert_event_ordering(owner, table_id)
        assert_no_errors(owner, joiner, spectator, table_id=table_id)


def test_ll2_concurrent_joins(http):
    """Concurrent joins across 3 tables; STATE_SNAPSHOT has ≥1 player; no errors."""
    run_ll2(http)


def test_ll3_spectator_isolation(http):
    """Spectators on 3 concurrent tables receive no CARDS_DEALT and no cross-table events."""
    run_ll3(http)


def test_ll4_reconnect_concurrent(http):
    """Owner reconnects on table 0 while tables 1 and 2 run concurrently."""
    run_ll4(http)


def test_ll5_churn(http):
    """Owner receives HAND_RESULT after joiner disconnects mid-hand."""
    run_ll5(http)


def test_ll6_completion_summary(http):
    """All TableScenarioResult objects pass; assert_all_results_passed formats errors correctly."""
    results = run_ll6(http)
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert_all_results_passed(results)
