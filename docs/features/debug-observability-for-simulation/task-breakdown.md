# Task Breakdown — debug-observability-for-simulation

> Gate: Implementation Gate (Gate 4)

---

## Milestone Map

| Milestone | Tasks | Deliverable |
|-----------|-------|-------------|
| M0 | T0–T3 | `simulation/debug/` package (4 files) |
| M1 | T4–T5 | Integration into `client.py` and `assertions.py` |
| M2 | T6 | `tests/test_debug_observability.py` |

---

## Tasks

### T0 — `simulation/debug/__init__.py`

Exports all public symbols:

```python
from .snapshot import ClientSummary, ScenarioSnapshot
from .report import FailureReport, stuck_diagnostic, format_ordering_failure, format_leakage_failure
from .summary import LoadLiteSummary

__all__ = [
    "ClientSummary", "ScenarioSnapshot",
    "FailureReport", "stuck_diagnostic",
    "format_ordering_failure", "format_leakage_failure",
    "LoadLiteSummary",
]
```

### T1 — `simulation/debug/snapshot.py`

Implement:
- `_HIDDEN`, `_SENSITIVE_KEYS`, `_MAX_PAYLOAD_CHARS`, `_MAX_TAIL_EVENTS`, `_MAX_LINES` constants
- `_mask_payload(payload, is_spectator) -> dict`
- `_truncate(s, max_chars) -> str`
- `ClientSummary` dataclass + `from_client(client, is_spectator, tail)` classmethod + `format()` method
- `ScenarioSnapshot` dataclass + `capture(scenario_name, clients, spectator_indices)` classmethod + `format()` method

### T2 — `simulation/debug/report.py`

Implement:
- `stuck_diagnostic(clients, drain_target, elapsed_seconds, spectator_indices) -> str`
- `format_ordering_failure(player, before, after, table_id) -> str`
- `format_leakage_failure(spectator, expected_table_id, offending_event_type, offending_table_id, offending_payload) -> str`
- `FailureReport` dataclass + `format()` + `raise_as(msg)` methods

### T3 — `simulation/debug/summary.py`

Implement:
- `LoadLiteSummary` dataclass + `format()` + `assert_all_passed()` methods
- Import: `from simulation.load_lite.orchestrator import TableScenarioResult`

### T4 — Enrich `simulation/client.py` — `drain_until`

Change the `raise AssertionError(...)` in `drain_until` to include a `ClientSummary`:

```python
# Before:
raise AssertionError(
    f"{event_type!r} not received within {max_msgs} messages. "
    f"Types received: {self.log.types()}"
)

# After:
from simulation.debug.snapshot import ClientSummary
raise AssertionError(
    f"{event_type!r} not received within {max_msgs} messages.\n"
    + ClientSummary.from_client(self).format()
)
```

Use a lazy import inside the method to avoid circular imports.

### T5 — Enrich `simulation/load_lite/assertions.py`

Three enrichments:

**a) `assert_event_ordering`** — replace bare `AssertionError` with `format_ordering_failure`:
```python
from simulation.debug.report import format_ordering_failure
raise AssertionError(format_ordering_failure(player, "BLINDS_POSTED", "HAND_RESULT", table_id))
```

**b) `assert_spectator_isolation`** — replace bare `AssertionError` (table_id mismatch path) with `format_leakage_failure`:
```python
from simulation.debug.report import format_leakage_failure
raise AssertionError(
    format_leakage_failure(spectator, expected_table_id, event.type, tid, event.payload)
)
```

**c) `assert_all_results_passed`** — replace inline formatting with `LoadLiteSummary`:
```python
from simulation.debug.summary import LoadLiteSummary
LoadLiteSummary(results).assert_all_passed()
```

### T6 — `tests/test_debug_observability.py`

Implement all unit tests from QA test plan sections 3–12:
- `ClientSummary` tests (3.1–3.7): 7 tests
- `stuck_diagnostic` tests (4.1–4.3): 3 tests
- `format_ordering_failure` tests (5.1–5.3): 3 tests
- `format_leakage_failure` tests (6.1–6.3): 3 tests
- `LoadLiteSummary` tests (7.1–7.4): 4 tests
- `drain_until` enrichment tests (8.1–8.2): 2 tests
- `assert_spectator_isolation` enrichment tests (9.1–9.2): 2 tests
- `assert_event_ordering` enrichment test (10.1): 1 test
- Hidden-card safety tests (11.1–11.3): 3 tests
- Output absence tests (12.1–12.2): 2 tests

**Total new tests: ~30**

---

## Must Not Change

- `poker_engine/` — zero changes
- `backend/` — zero changes
- `simulation/scenarios/s1_*.py` through `s6_*.py` — zero changes
- `simulation/scenarios/deterministic/` — zero changes
- `simulation/scenarios/load_lite/` — zero changes (only `assertions.py` in `load_lite/` changes, not scenarios)
- `tests/test_simulation_scenarios.py` — zero changes
- `tests/test_simulation_deterministic.py` — zero changes
- `tests/test_deck_control.py` — zero changes
- `tests/test_load_lite.py` — zero changes

---

## Deferred (Do Not Implement Now)

- File-based debug output (writing failure snapshots to disk)
- Structured JSON debug reports
- pytest plugin / fixture for automatic snapshot capture
- Timeline visualisation
- Integration with external error tracking
