"""
LL6 — Completion Summary

Meta-scenario: re-runs the 3-table concurrent suite and asserts all
TableScenarioResult objects have passed=True. Provides a formatted
failure message if any table failed.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.load_lite.orchestrator import run_all_tables, TableScenarioResult
from simulation.load_lite.table_scenario import run_standard_table
from simulation.load_lite.assertions import assert_all_results_passed


def _table_fn(http, table_index: int):
    table_id, owner, joiner, spectator = run_standard_table(http, table_index)
    return table_id, owner


def run(http: TestClient) -> list[TableScenarioResult]:
    results = run_all_tables(http, [_table_fn, _table_fn, _table_fn])
    assert_all_results_passed(results)
    return results
