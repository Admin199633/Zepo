"""
Load-lite orchestrator: thread launcher, stuck detection, result collection.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class TableScenarioResult:
    table_index: int
    table_id: Optional[str]
    passed: bool
    error: Optional[str]
    event_types: list[str] = field(default_factory=list)


def run_table_scenario(
    index: int,
    scenario_fn: Callable,
    http,
) -> TableScenarioResult:
    """
    Run one table scenario function and capture pass/fail into a result.

    scenario_fn signature: (http, table_index: int) -> tuple[str, any]
      where the tuple is (table_id, owner_client).
    """
    try:
        table_id, owner = scenario_fn(http, index)
        return TableScenarioResult(
            table_index=index,
            table_id=table_id,
            passed=True,
            error=None,
            event_types=owner.log.types(),
        )
    except Exception as exc:
        return TableScenarioResult(
            table_index=index,
            table_id=None,
            passed=False,
            error=str(exc),
            event_types=[],
        )


def run_all_tables(
    http,
    scenarios: list[Callable],
    timeout_per_thread: float = 45.0,
) -> list[TableScenarioResult]:
    """
    Launch one thread per scenario, join with timeout, collect results.

    Raises AssertionError if any thread is still alive after timeout.
    Returns results sorted by table_index.
    """
    results: list[TableScenarioResult] = []
    lock = threading.Lock()

    def run_one(index: int, scenario_fn: Callable) -> None:
        result = run_table_scenario(index, scenario_fn, http)
        with lock:
            results.append(result)

    threads = [
        threading.Thread(
            target=run_one,
            args=(i, fn),
            name=f"load-lite-table-{i}",
            daemon=True,
        )
        for i, fn in enumerate(scenarios)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout_per_thread)

    stuck = [t.name for t in threads if t.is_alive()]
    if stuck:
        raise AssertionError(
            f"Load-lite threads did not finish within {timeout_per_thread}s: {stuck}"
        )

    return sorted(results, key=lambda r: r.table_index)
