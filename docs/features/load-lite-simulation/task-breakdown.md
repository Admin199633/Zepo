# Task Breakdown — load-lite-simulation

> Gate: Implementation Gate (Gate 4)

---

## Milestone Map

| Milestone | Tasks | Deliverable |
|-----------|-------|-------------|
| M0 | T0–T2 | Core load-lite package skeleton |
| M1 | T3–T5 | LL1–LL3 scenarios (standard table) |
| M2 | T6–T7 | LL4–LL5 scenarios (reconnect + churn) |
| M3 | T8–T9 | LL6 + test file |

---

## Tasks

### T0 — `simulation/load_lite/__init__.py`

Exports: `TableScenarioResult`, `run_table_scenario`, `run_all_tables`.

```python
from .orchestrator import TableScenarioResult, run_table_scenario, run_all_tables

__all__ = ["TableScenarioResult", "run_table_scenario", "run_all_tables"]
```

### T1 — `simulation/load_lite/orchestrator.py`

Implement:
- `TableScenarioResult` dataclass (`table_index`, `table_id`, `passed`, `error`, `event_types`)
- `run_table_scenario(index, scenario_fn, http) -> TableScenarioResult`
- `run_all_tables(http, scenarios, timeout_per_thread=45.0) -> list[TableScenarioResult]`

Thread-per-scenario pattern, `threading.Lock` for result append, `thread.join(timeout)` + `is_alive()` check.

### T2 — `simulation/load_lite/table_scenario.py`

Implement:
- `PHONE_PREFIXES` list: `["+1557000", "+1557100", "+1557200"]`
- `run_standard_table(http, table_index) -> tuple[str, SimulatedClient, SimulatedClient, SimulatedClient]` — setup, connect, join, spectate, drive hand, return `(table_id, owner, joiner, spectator)`

### T3 — `simulation/load_lite/assertions.py`

Implement all 5 assertion helpers:
- `assert_hand_completed(owner, joiner, table_id)`
- `assert_event_ordering(player, table_id)`
- `assert_no_errors(*players, table_id)`
- `assert_spectator_isolation(spectator, expected_table_id)`
- `assert_all_results_passed(results)`

### T4 — `simulation/scenarios/load_lite/__init__.py`

Exports: `run_ll1`, `run_ll2`, `run_ll3`, `run_ll4`, `run_ll5`, `run_ll6`.

### T5 — `simulation/scenarios/load_lite/ll1_multi_table.py` + `ll2_concurrent_joins.py` + `ll3_spectator_isolation.py`

LL1, LL2, LL3 all use `run_standard_table` and `run_all_tables`. They differ only in which post-run assertions they apply:
- LL1: `assert_hand_completed`, `assert_event_ordering`, `assert_no_errors`
- LL2: adds snapshot player-count check
- LL3: adds `assert_spectator_isolation` per spectator

### T6 — `simulation/scenarios/load_lite/ll4_reconnect_concurrent.py`

Tables 1 and 2: `run_standard_table`. Table 0: inline reconnect scenario using prefixes `+1558000` (table 0), `+1558100` (table 1), `+1558200` (table 2). All 3 threads launched together via `run_all_tables`.

### T7 — `simulation/scenarios/load_lite/ll5_churn.py`

Single table (prefix `+1558300`). Joiner disconnects after BLINDS_POSTED. Owner drains HAND_RESULT with `max_msgs=200`.

### T8 — `simulation/scenarios/load_lite/ll6_completion_summary.py`

Re-runs LL1's 3-table scenario. Calls `assert_all_results_passed`. Returns summary string.

### T9 — `tests/test_load_lite.py`

6 test functions sharing the `http` fixture (`make_test_client(between_hands_delay=0.05)`):

```python
def test_ll1_multi_table(http): ...
def test_ll2_concurrent_joins(http): ...
def test_ll3_spectator_isolation(http): ...
def test_ll4_reconnect_concurrent(http): ...
def test_ll5_churn(http): ...
def test_ll6_completion_summary(http): ...
```

---

## Must Not Change

- `poker_engine/` — zero changes
- `backend/` — zero changes
- `simulation/scenarios/s1_*.py` through `s6_*.py` — zero changes
- `tests/test_simulation_scenarios.py` — zero changes
- `tests/test_simulation_deterministic.py` — zero changes
- `simulation/deck_control.py` — zero changes

---

## Deferred (Do Not Implement Now)

- Parametric N-table scaling (load-lite is fixed at 3 tables)
- Performance measurement / latency reporting
- `pytest-xdist` group markers for load-lite isolation
- CI lint step asserting no `backend/` imports in `simulation/`
