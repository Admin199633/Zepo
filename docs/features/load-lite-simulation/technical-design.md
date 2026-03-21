# Technical Design: load-lite-simulation

**Feature ID:** load-lite-simulation
**Status:** Engineering Design
**Author:** Senior Engineer Agent
**Last Updated:** 2026-03-19

---

## Table of Contents

1. [Concurrency Strategy](#1-concurrency-strategy)
2. [Module Layout](#2-module-layout)
3. [TableScenarioResult Dataclass](#3-tablescenarioresult-dataclass)
4. [orchestrator.py Design](#4-orchestratorpy-design)
5. [table_scenario.py Design](#5-table_scenariopy-design)
6. [assertions.py Design](#6-assertionspy-design)
7. [Phone Prefix Strategy](#7-phone-prefix-strategy)
8. [Per-Scenario Design: LL1–LL6](#8-per-scenario-design-ll1ll6)
9. [Thread Safety](#9-thread-safety)
10. [CI Runtime Estimate](#10-ci-runtime-estimate)

---

## 1. Concurrency Strategy

### Why `threading.Thread` Over asyncio or multiprocessing

**asyncio**: The existing simulation harness is built on synchronous `fastapi.testclient.TestClient`. `TestClient` is not an async object — it runs the ASGI application in a background thread (via `anyio`'s thread portal). Writing load-lite as async coroutines would require either an async test runner (`pytest-asyncio`) or an `anyio` portal, neither of which integrates cleanly with the synchronous `client.drain_until()` and `connect()` context managers that the existing scenarios depend on. Retrofitting all scenario helpers with async versions is out of scope and would break backward compatibility with S1–S6.

**multiprocessing**: Each process would need its own `TestClient` and its own in-memory backend state. Processes cannot share the same running ASGI app, so cross-table interactions (e.g., events leaking between tables that share one backend) would not be exercised. Multiprocessing also introduces pickle requirements for inter-process result passing that add complexity without benefit.

**`threading.Thread` (chosen)**: Threads share a single Python process and a single `TestClient` instance. All 3 table threads drive the same live ASGI backend simultaneously, which is exactly what load-lite needs to exercise: the session registry's `asyncio.Lock`, the per-table session locks, and the broadcast service's concurrent subscriber handling. The existing synchronous `drain_until`, `send_action`, and `connect()` helpers work without modification inside threads.

### How `TestClient` Handles Concurrent HTTP

`fastapi.testclient.TestClient` wraps the ASGI application in a background asyncio event loop running in a dedicated thread (via `anyio`'s blocking portal). HTTP requests from `SimulatedClient._http.post(...)` / `.get(...)` are forwarded through the portal to the event loop. The HTTPX transport layer used internally by `TestClient` is thread-safe for concurrent callers — multiple Python threads can issue HTTP requests simultaneously, and each request is dispatched to the asyncio event loop in a thread-safe manner. No external locking is required at the `TestClient` level.

### How Multiple WebSocket Connections Coexist

`client.connect(table_id)` opens an independent WebSocket context via `self._http.websocket_connect(...)`. Each call returns a distinct `WebSocketTestSession` object owned exclusively by the calling `SimulatedClient`. Multiple `websocket_connect` contexts can be open simultaneously across threads; they are independent transport streams with independent receive buffers. The backend's WS router accepts each connection as a separate `WebSocket` object; the broadcast service maintains a per-table subscriber registry keyed by `WebSocket` identity. No WS connection is shared between threads.

---

## 2. Module Layout

```
simulation/
  load_lite/
    __init__.py           # exports TableScenarioResult, run_table_scenario, run_all_tables
    orchestrator.py       # thread launcher, stuck detection, result aggregation
    table_scenario.py     # single-table scenario: 2 players + 1 spectator, 1 hand
    assertions.py         # per-table and cross-table assertion helpers
  scenarios/
    load_lite/
      __init__.py         # exports run_ll1 through run_ll6
      ll1_multi_table.py
      ll2_concurrent_joins.py
      ll3_spectator_isolation.py
      ll4_reconnect_concurrent.py
      ll5_join_leave_churn.py
      ll6_completion_summary.py
tests/
  test_load_lite.py
```

### `simulation/load_lite/__init__.py`

```python
"""
simulation/load_lite
--------------------
Lightweight concurrent-table simulation.

Exports:
    TableScenarioResult  — result dataclass for one table's scenario run
    run_table_scenario   — drives one table's full scenario in a thread
    run_all_tables       — launches threads, collects results, detects stuck threads
"""
from .table_scenario import TableScenarioResult, run_table_scenario
from .orchestrator import run_all_tables

__all__ = ["TableScenarioResult", "run_table_scenario", "run_all_tables"]
```

### `simulation/scenarios/load_lite/__init__.py`

```python
"""
Load-lite simulation scenarios (LL1–LL6).

Each module exposes a single run(http: TestClient) -> None function
compatible with direct pytest invocation and ScenarioRunner.
"""
from .ll1_multi_table import run as run_ll1
from .ll2_concurrent_joins import run as run_ll2
from .ll3_spectator_isolation import run as run_ll3
from .ll4_reconnect_concurrent import run as run_ll4
from .ll5_join_leave_churn import run as run_ll5
from .ll6_completion_summary import run as run_ll6

__all__ = ["run_ll1", "run_ll2", "run_ll3", "run_ll4", "run_ll5", "run_ll6"]
```

---

## 3. `TableScenarioResult` Dataclass

Defined in `simulation/load_lite/table_scenario.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TableScenarioResult:
    """
    Outcome of one table's concurrent scenario run.

    Fields:
        table_id    — The backend table_id for this table (from create_club response).
                      Falls back to the TableSetup.label if club creation failed.
        passed      — True if the scenario completed without exceptions.
        error       — Empty string on success; repr(exception) on failure.
        event_types — Ordered list of event type strings from the owner's EventLog,
                      captured at the end of the scenario (or at failure point).
                      Used for diagnosing stuck or partially-completed hands.
    """
    table_id: str
    passed: bool
    error: str
    event_types: list[str] = field(default_factory=list)
```

### Design Notes

- `table_id` is captured from the backend response (the `create_club` return value), not from a test-side constant, so it reflects the true session identity used by the backend.
- `error` stores `repr(exception)` when `passed=False`. This captures both the exception type and its message in a single string without requiring the `Exception` object to be pickle-safe.
- `event_types` is a snapshot of `owner.log.types()` taken at scenario completion. When a scenario is stuck, this records how far the hand progressed before the thread's timeout, aiding diagnosis.
- The dataclass is intentionally minimal. Assertion helpers that need richer data (e.g., spectator `SimulatedClient` references for LL3) receive those objects directly via an extended result tuple, not through this dataclass.

---

## 4. `orchestrator.py` Design

### Public API

```python
def run_all_tables(
    http: TestClient,
    table_setups: list[TableSetup],
    timeout_seconds: float = 45.0,
) -> list[TableScenarioResult]:
    ...
```

### `TableSetup` Dataclass

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from .table_scenario import TableScenarioResult


@dataclass
class TableSetup:
    """
    Configuration for one table's concurrent scenario.

    Fields:
        phone_prefix — Phone number prefix for this table's users (e.g., "+1557000").
                       Owner receives prefix + "1001", joiner prefix + "1002",
                       spectator prefix + "1003".
        label        — Human-readable name for stuck-detection error messages
                       (e.g., "ll1-table-0", "ll4-reconnect").
        scenario_fn  — Callable(http, TableSetup) -> TableScenarioResult.
                       Encapsulates the full per-table scenario logic for this setup.
        club_id      — Populated by scenario_fn after create_club. Empty at construction.
        table_id     — Populated by scenario_fn after create_club. Empty at construction.
        invite_code  — Populated by scenario_fn after create_club. Empty at construction.
    """
    phone_prefix: str
    label: str
    scenario_fn: Callable[["TestClient", "TableSetup"], "TableScenarioResult"]
    club_id: str = field(default="")
    table_id: str = field(default="")
    invite_code: str = field(default="")
```

### Full `run_all_tables` Implementation Sketch

```python
import threading
from fastapi.testclient import TestClient
from .table_scenario import TableScenarioResult


def run_all_tables(
    http: TestClient,
    table_setups: list[TableSetup],
    timeout_seconds: float = 45.0,
) -> list[TableScenarioResult]:
    """
    Launch one thread per TableSetup, wait for completion, detect stuck threads.

    All threads are started before any join() is called, ensuring true
    concurrent execution from the moment the first thread starts.

    Returns:
        List of TableScenarioResult objects in arrival order (not necessarily
        setup order, due to concurrency).

    Raises:
        AssertionError — if any thread is still alive after timeout_seconds,
                         naming the stuck scenario labels.
    """
    results: list[TableScenarioResult] = []
    results_lock = threading.Lock()

    def _thread_target(setup: TableSetup) -> None:
        try:
            result = setup.scenario_fn(http, setup)
        except Exception as exc:
            result = TableScenarioResult(
                table_id=setup.label,   # table_id unavailable if setup failed
                passed=False,
                error=repr(exc),
                event_types=[],
            )
        with results_lock:
            results.append(result)

    threads = [
        threading.Thread(
            target=_thread_target,
            args=(setup,),
            name=setup.label,
            daemon=True,   # daemon threads do not block process exit
        )
        for setup in table_setups
    ]

    # Start all threads before joining any — ensures true concurrency.
    # Joining thread 0 before starting threads 1 and 2 would serialise execution.
    for t in threads:
        t.start()

    # Join each thread with timeout; collect names of any threads still alive.
    for t in threads:
        t.join(timeout=timeout_seconds)

    stuck = [t.name for t in threads if t.is_alive()]
    if stuck:
        raise AssertionError(
            f"Load-lite stuck: the following scenario threads did not complete "
            f"within {timeout_seconds}s: {stuck}"
        )

    return results
```

### Design Notes

- All threads are `start()`ed in a first pass, then joined in a second pass. This is essential: joining thread 0 before starting threads 1 and 2 would serialise execution, eliminating the concurrency that load-lite is designed to exercise.
- `daemon=True` ensures that if stuck detection fires and pytest exits, orphaned threads waiting in `drain_until` are cleaned up automatically and do not prevent process exit.
- Exceptions in `_thread_target` are caught and converted to `TableScenarioResult(passed=False, error=repr(exc))`. This allows all threads to complete (or time out) before the orchestrator raises, giving a complete picture of which tables failed.
- `results_lock` is held only for `results.append()` — a near-instantaneous operation. Contention across 3 threads is negligible.

---

## 5. `table_scenario.py` Design

### `run_table_scenario` Signature

```python
def run_table_scenario(
    http: TestClient,
    setup: TableSetup,
) -> TableScenarioResult:
    """
    Drive one table's standard load-lite scenario.

    Steps:
      1. Authenticate owner, joiner, spectator (HTTP OTP flow via make_client).
      2. Owner creates club — populates setup.club_id, setup.table_id, setup.invite_code.
      3. Joiner and spectator join the club via invite_code.
      4. Owner and joiner open WS connections and join as players.
      5. Both drain to STATE_SNAPSHOT, then BLINDS_POSTED.
      6. Spectator opens WS, joins as spectator, drains to STATE_SNAPSHOT.
      7. _drive_hand() drives owner's turn stream to HAND_RESULT; joiner drains passively.
      8. Spectator drains to HAND_RESULT.
      9. Return TableScenarioResult(passed=True) with owner.log.types().

    All three WS contexts (owner, joiner, spectator) are open simultaneously
    within the same thread, mirroring production multi-connection behaviour.

    On any exception, returns TableScenarioResult(passed=False, error=repr(exc)).
    Does not re-raise — exception handling is the orchestrator's responsibility.
    """
```

### Hand-Driving Strategy

Load-lite reuses `_drive_hand` from `simulation.scenarios.s1_two_player_hand`. That function:

- Reads from the owner's event stream as the oracle for turn progression.
- Tracks `can_check` state to send `"check"` vs `"call"` on every `TURN_CHANGED`. This avoids engine validation errors from calling when no bet is outstanding.
- Initial state after consuming `BLINDS_POSTED` is `can_check=False`, because the big blind's bet is outstanding and the small blind must call first.
- Updates `can_check` on: `COMMUNITY_CARDS` (new street → True), `PHASE_CHANGED` with phase in `("FLOP", "TURN", "RIVER")` (→ True), `PLAYER_ACTED` with action `"raise"` (→ False) or `"call"` (→ True).
- Drains the joiner to `HAND_RESULT` with `max_msgs=100` after the owner's `HAND_RESULT` is seen, to accommodate the larger message buffer that accumulates during full-hand broadcast.

The spectator is drained to `HAND_RESULT` after `_drive_hand` returns, using `spectator.drain_until("HAND_RESULT", max_msgs=100)`. The spectator drain does not block the hand — `_drive_hand` completes the hand first, and then the spectator drain consumes already-queued messages.

### Full Scenario Skeleton

```python
from __future__ import annotations

from dataclasses import dataclass, field
from fastapi.testclient import TestClient

from simulation.helpers import make_client
from simulation.scenarios.s1_two_player_hand import _drive_hand


def run_table_scenario(http: TestClient, setup: "TableSetup") -> "TableScenarioResult":
    owner_phone     = f"{setup.phone_prefix}1001"
    joiner_phone    = f"{setup.phone_prefix}1002"
    spectator_phone = f"{setup.phone_prefix}1003"

    owner     = make_client(http, owner_phone,     "Owner")
    joiner    = make_client(http, joiner_phone,    "Joiner")
    spectator = make_client(http, spectator_phone, "Spectator")

    data = owner.create_club("LoadLite Club")
    setup.club_id     = data["club_id"]
    setup.table_id    = data["table_id"]
    setup.invite_code = data["invite_code"]

    joiner.join_club(setup.club_id, setup.invite_code)
    spectator.join_club(setup.club_id, setup.invite_code)

    try:
        with owner.connect(setup.table_id):
            with joiner.connect(setup.table_id):
                owner.send_join(setup.table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")

                joiner.send_join(setup.table_id, "player")
                joiner.drain_until("STATE_SNAPSHOT")

                owner.drain_until("BLINDS_POSTED")
                joiner.drain_until("BLINDS_POSTED")

                with spectator.connect(setup.table_id):
                    spectator.send_join(setup.table_id, "spectator")
                    spectator.drain_until("STATE_SNAPSHOT")

                    _drive_hand(owner, joiner, setup.table_id)

                    spectator.drain_until("HAND_RESULT", max_msgs=100)

        return TableScenarioResult(
            table_id=setup.table_id,
            passed=True,
            error="",
            event_types=owner.log.types(),
        )
    except Exception as exc:
        return TableScenarioResult(
            table_id=setup.table_id or setup.label,
            passed=False,
            error=repr(exc),
            event_types=owner.log.types(),
        )
```

---

## 6. `assertions.py` Design

All assertion helpers operate on `EventLog` objects and `TableScenarioResult` objects. No helper imports from `backend/` or `poker_engine/`. All helpers raise `AssertionError` with diagnostic context on failure.

### `assert_table_completed`

```python
from simulation.load_lite.table_scenario import TableScenarioResult


def assert_table_completed(result: TableScenarioResult) -> None:
    """Assert that a table scenario ran to completion without exceptions."""
    assert result.passed, (
        f"Table {result.table_id!r} scenario failed.\n"
        f"Error: {result.error}\n"
        f"Event types captured: {result.event_types}"
    )
```

### `assert_event_order`

```python
from simulation.event_log import EventLog


def assert_event_order(
    log: EventLog,
    before: str,
    after: str,
    label: str = "",
) -> None:
    """
    Assert that event type `before` appears before event type `after`
    in the log's ordered sequence, using the first occurrence of each type.

    Both event types must be present; missing events produce a clear diagnostic.

    Primary use: assert BLINDS_POSTED before HAND_RESULT.

    Args:
        log    — EventLog from a SimulatedClient.
        before — Event type string that must appear earlier in the sequence.
        after  — Event type string that must appear later in the sequence.
        label  — Optional context string (e.g., table label) for error messages.
    """
    prefix = f"{label}: " if label else ""
    types = log.types()
    assert before in types, (
        f"{prefix}expected {before!r} in log but not found. "
        f"Types seen: {types}"
    )
    assert after in types, (
        f"{prefix}expected {after!r} in log but not found. "
        f"Types seen: {types}"
    )
    idx_before = types.index(before)
    idx_after  = types.index(after)
    assert idx_before < idx_after, (
        f"{prefix}expected {before!r} (idx={idx_before}) before "
        f"{after!r} (idx={idx_after}). Full sequence: {types}"
    )
```

### `assert_no_cross_table_leakage`

```python
from simulation.client import SimulatedClient


def assert_no_cross_table_leakage(
    spectator_logs: list[tuple[SimulatedClient, str]],
) -> None:
    """
    Assert cross-table isolation for each spectator.

    For each (spectator_client, expected_table_id) pair, enforces two rules:

    Rule 1 — CARDS_DEALT absence:
        The spectator's log must contain zero CARDS_DEALT events.
        CARDS_DEALT is a unicast event sent only to the player who owns the
        hole cards. Any CARDS_DEALT in a spectator log indicates a broadcast
        filtering bug.

    Rule 2 — No cross-table events:
        For every event in the spectator's log where payload.get("table_id")
        is not None, that table_id must equal expected_table_id.
        An event with a different table_id indicates that the broadcast service
        delivered a message from another table to this spectator's WS connection.

    Args:
        spectator_logs — List of (SimulatedClient, expected_table_id_str) pairs,
                         one per table. expected_table_id is the backend table_id
                         returned by create_club for that table.
    """
    for spectator, expected_tid in spectator_logs:
        log = spectator.log

        # Rule 1: spectators must never receive hole-card events
        assert not log.has_type("CARDS_DEALT"), (
            f"Spectator on table {expected_tid!r} received CARDS_DEALT. "
            f"This indicates a broadcast filtering bug. "
            f"Full event sequence: {log.types()}"
        )

        # Rule 2: no events from a different table
        for event in log.all():
            tid = event.payload.get("table_id")
            if tid is not None:
                assert tid == expected_tid, (
                    f"Spectator on table {expected_tid!r} received event "
                    f"{event.type!r} with table_id={tid!r}. "
                    f"Cross-table event leakage detected. "
                    f"Full event sequence: {log.types()}"
                )
```

### `assert_no_stuck_tables`

```python
def assert_no_stuck_tables(results: list[TableScenarioResult]) -> None:
    """
    Assert that all TableScenarioResult objects report passed=True.

    Produces a combined failure message listing all failed tables with
    their error strings and captured event_types sequences. This single
    combined assertion is preferred over per-result assertions because it
    surfaces all failures in one pytest output rather than stopping at
    the first failure.
    """
    failures = [r for r in results if not r.passed]
    if failures:
        lines = [
            f"  table_id={r.table_id!r}\n"
            f"    error: {r.error}\n"
            f"    event_types: {r.event_types}"
            for r in failures
        ]
        raise AssertionError(
            f"{len(failures)} of {len(results)} table scenario(s) failed:\n"
            + "\n".join(lines)
        )
```

---

## 7. Phone Prefix Strategy

Each table and each special scenario uses a unique phone-number prefix to prevent user-account collisions across concurrent threads and across sequential test runs against the same in-process backend.

| Table / Scenario | Prefix | Owner phone | Joiner phone | Spectator phone |
|-----------------|--------|-------------|--------------|-----------------|
| LL1/LL2/LL3 Table 0 | `+1557000` | `+15570001001` | `+15570001002` | `+15570001003` |
| LL1/LL2/LL3 Table 1 | `+1557100` | `+15571001001` | `+15571001002` | `+15571001003` |
| LL1/LL2/LL3 Table 2 | `+1557200` | `+15572001001` | `+15572001002` | `+15572001003` |
| LL4 Reconnect Table | `+1558000` | `+15580001001` | `+15580001002` | `+15580001003` |
| LL5 Churn Table | `+1558100` | `+15581001001` | `+15581001002` | (none) |

**Rationale for the `+1557xxx` / `+1558xxx` namespace:**

- Existing S1–S6 scenarios use `+1555100` through `+1555600`.
- Existing DS1–DS5 scenarios use `+1555700` through `+1556100`.
- Load-lite concurrent tables: `+1557000`, `+1557100`, `+1557200` — clear gap.
- Load-lite special single-table scenarios: `+1558000` (LL4), `+1558100` (LL5).

**Construction rule (consistent with `simulation/helpers.py`):**

```python
owner_phone     = f"{phone_prefix}1001"
joiner_phone    = f"{phone_prefix}1002"
spectator_phone = f"{phone_prefix}1003"
```

Each prefix yields exactly 3 accounts per table. The `1001`/`1002`/`1003` suffix is identical to the `setup_two_players` convention in `helpers.py`.

**Why LL4 and LL5 use dedicated prefixes:** LL4 and LL5 may run in the same test session as LL1. If they shared `+1557xxx` prefixes, the phone numbers would already have user accounts from LL1's execution, and `create_club` would succeed but the user's state would be non-fresh. Dedicated `+1558xxx` prefixes guarantee clean user state for each scenario regardless of test ordering.

---

## 8. Per-Scenario Design: LL1–LL6

### LL1 — `ll1_multi_table.py` — Three Tables Active Concurrently

**Purpose:** Verify that 3 table sessions can be created, played, and concluded simultaneously without cross-session interference or session-registry deadlock under concurrent `asyncio.Lock` acquisition in `TableSessionRegistry`.

**Setup:**

```python
TABLE_SETUPS = [
    TableSetup(phone_prefix="+1557000", label="ll1-table-0", scenario_fn=run_table_scenario),
    TableSetup(phone_prefix="+1557100", label="ll1-table-1", scenario_fn=run_table_scenario),
    TableSetup(phone_prefix="+1557200", label="ll1-table-2", scenario_fn=run_table_scenario),
]

def run(http: TestClient) -> None:
    results = run_all_tables(http, TABLE_SETUPS, timeout_seconds=45)
    assert_no_stuck_tables(results)
    for result in results:
        assert_table_completed(result)
        assert "HAND_RESULT" in result.event_types, (
            f"Table {result.table_id!r} did not reach HAND_RESULT. "
            f"Event sequence: {result.event_types}"
        )
        assert "BLINDS_POSTED" in result.event_types, (
            f"Table {result.table_id!r} did not reach BLINDS_POSTED. "
            f"Event sequence: {result.event_types}"
        )
        bp_idx = result.event_types.index("BLINDS_POSTED")
        hr_idx = result.event_types.index("HAND_RESULT")
        assert bp_idx < hr_idx, (
            f"Table {result.table_id!r}: BLINDS_POSTED must precede HAND_RESULT. "
            f"indices: BLINDS_POSTED={bp_idx}, HAND_RESULT={hr_idx}"
        )
    assert not any("ERROR" in r.event_types for r in results), (
        "ERROR event found in at least one table's event log"
    )
```

**Key actions per thread:** authenticate owner + joiner + spectator, create club, join club, WS-connect as players, drain to `BLINDS_POSTED`, drive hand via `_drive_hand`, spectator drains passively, collect result.

---

### LL2 — `ll2_concurrent_joins.py` — Concurrent Player Joins Across All Three Tables

**Purpose:** Validate that `TableSessionRegistry.get_or_create` under its `asyncio.Lock` handles simultaneous club-creation and join requests from 3 threads without creating duplicate sessions or returning HTTP errors. The join phase is the primary concurrent-stress axis.

**Setup:** Identical `TABLE_SETUPS` as LL1. The concurrency stress is inherent in `run_all_tables` launching all 3 threads simultaneously — the first thing each thread does is authenticate users and create a club, so HTTP calls for create_club and join_club are all in flight concurrently across threads.

**Additional Assertion after `run_all_tables`:**

```python
# Each table must have a unique backend table_id
table_ids = [r.table_id for r in results]
assert len(set(table_ids)) == len(table_ids), (
    f"Duplicate table_ids across concurrent threads: {table_ids}. "
    "Indicates a session-registry race condition."
)
```

---

### LL3 — `ll3_spectator_isolation.py` — Spectators on All Three Tables with Cross-Table Isolation

**Purpose:** Verify that the broadcast service does not deliver events from one table to spectators subscribed on a different table, when all 3 spectators are active simultaneously.

**Extended Result Collection:** `assert_no_cross_table_leakage` requires `SimulatedClient` references after all threads complete. LL3 uses a thread-local extended tuple list:

```python
extended_results: list[tuple[TableScenarioResult, SimulatedClient, str]] = []
extended_lock = threading.Lock()

def _ll3_scenario(http: TestClient, setup: TableSetup) -> TableScenarioResult:
    """Runs run_table_scenario and also stores the spectator reference."""
    result, spectator = _run_with_spectator_ref(http, setup)
    with extended_lock:
        extended_results.append((result, spectator, setup.table_id))
    return result
```

**Assertions after `run_all_tables`:**

```python
assert_no_stuck_tables(results)
spectator_logs = [
    (spec_client, expected_tid)
    for (_, spec_client, expected_tid) in extended_results
]
assert_no_cross_table_leakage(spectator_logs)
```

`assert_no_cross_table_leakage` checks for each spectator:
1. `CARDS_DEALT` is absent from the spectator's log.
2. Every event with a `table_id` payload field matches the spectator's expected table.

---

### LL4 — `ll4_reconnect_concurrent.py` — Reconnect During Concurrent Table Activity

**Purpose:** Verify that a player reconnect on one table (table 0) does not interfere with ongoing hands on tables 1 and 2, and that the reconnecting player receives a valid `STATE_SNAPSHOT` with their seat still held.

**Thread setup:**

```python
TABLE_SETUPS = [
    TableSetup(phone_prefix="+1558000", label="ll4-reconnect", scenario_fn=_run_ll4_reconnect_table),
    TableSetup(phone_prefix="+1557100", label="ll4-table-1",   scenario_fn=run_table_scenario),
    TableSetup(phone_prefix="+1557200", label="ll4-table-2",   scenario_fn=run_table_scenario),
]
```

**`_run_ll4_reconnect_table` key actions:**

```python
from simulation.helpers import setup_two_players

def _run_ll4_reconnect_table(http: TestClient, setup: TableSetup) -> TableScenarioResult:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, setup.phone_prefix)
    setup.table_id = table_id

    try:
        with joiner.connect(table_id):
            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            # First connection: owner joins, hand starts
            owner_ctx = owner.connect(table_id)
            owner_ctx.__enter__()
            try:
                owner.send_join(table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")
                joiner.drain_until("BLINDS_POSTED")
                owner.drain_until("BLINDS_POSTED")
            finally:
                owner_ctx.__exit__(None, None, None)   # owner disconnects

            # Joiner sees PLAYER_STATUS{disconnected}
            disconnect_evt = joiner.drain_until("PLAYER_STATUS")
            assert disconnect_evt["payload"]["status"] == "disconnected"
            assert disconnect_evt["payload"]["user_id"] == owner.user_id

            # Second connection: owner reconnects
            owner_ctx2 = owner.connect(table_id)
            owner_ctx2.__enter__()
            try:
                owner.send_join(table_id, "player")
                snap = owner.drain_until("STATE_SNAPSHOT")
                players_in_snap = snap["payload"].get("players", {})
                assert owner.user_id in players_in_snap, (
                    f"owner must still be in STATE_SNAPSHOT after reconnect. "
                    f"Players: {list(players_in_snap.keys())}"
                )
            finally:
                owner_ctx2.__exit__(None, None, None)

        return TableScenarioResult(
            table_id=table_id,
            passed=True,
            error="",
            event_types=owner.log.types(),
        )
    except Exception as exc:
        return TableScenarioResult(
            table_id=table_id or setup.label,
            passed=False,
            error=repr(exc),
            event_types=owner.log.types(),
        )
```

**Assertions:**
- Table 0: `STATE_SNAPSHOT` received after reconnect; owner's seat held.
- Tables 1 and 2 (via `run_table_scenario`): `assert_table_completed` and `"HAND_RESULT" in result.event_types`.
- `assert_no_stuck_tables(results)`.

---

### LL5 — `ll5_join_leave_churn.py` — Join/Leave Churn

**Purpose:** Verify that after one player (joiner) disconnects mid-hand without reconnecting, the engine resolves the hand (via auto-fold when the reserve window expires or the turn timer fires on the absent player's turn) and the remaining player (owner) receives `HAND_RESULT`. The table must not stall.

**Design:** LL5 runs as a single-threaded scenario against one dedicated table (`+1558100`). `run_all_tables` is not used; the scenario function is called directly from `test_ll5_join_leave_churn` in `tests/test_load_lite.py`.

**Key actions:**

```python
def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1558100")

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
            # Joiner exits mid-hand — no reconnect
            joiner_ctx.__exit__(None, None, None)

        # Owner must still reach HAND_RESULT.
        # The engine auto-folds the disconnected player on the next
        # TURN_CHANGED targeting joiner (reserve-window expiry or turn timer).
        hand_result = owner.drain_until("HAND_RESULT", max_msgs=200)
        assert hand_result["payload"]["pot_total"] > 0

    assert owner.log.has_type("HAND_RESULT"), "hand must resolve after joiner churn"
    assert not owner.log.has_type("ERROR"), (
        f"unexpected ERROR in owner log: {owner.log.of_type('ERROR')}"
    )
    assert_event_order(owner.log, "BLINDS_POSTED", "HAND_RESULT", label="ll5-churn")
```

---

### LL6 — `ll6_completion_summary.py` — Completion Summary

**Purpose:** A final correctness gate that runs 3 tables concurrently and applies all structural assertions in one pass. Serves as the human-readable "all-green" summary for the load-lite suite.

```python
def run(http: TestClient) -> None:
    """
    LL6: Run 3 concurrent tables and apply all structural assertions.
    Uses the same envelope as LL1 (3 tables, 2 players + 1 spectator, 1 hand).
    """
    setups = [
        TableSetup(phone_prefix="+1557000", label="ll6-table-0", scenario_fn=run_table_scenario),
        TableSetup(phone_prefix="+1557100", label="ll6-table-1", scenario_fn=run_table_scenario),
        TableSetup(phone_prefix="+1557200", label="ll6-table-2", scenario_fn=run_table_scenario),
    ]
    results = run_all_tables(http, setups, timeout_seconds=45)

    # Gate 1: no stuck threads (run_all_tables raises on stuck; this provides
    # a richer per-result summary if all threads completed but some failed)
    assert_no_stuck_tables(results)

    # Gate 2: each table reached HAND_RESULT
    for result in results:
        assert_table_completed(result)
        assert "HAND_RESULT" in result.event_types, (
            f"Table {result.table_id!r} did not reach HAND_RESULT. "
            f"Captured sequence: {result.event_types}"
        )

    # Gate 3: all table_ids are unique (no session deduplication failure)
    table_ids = [r.table_id for r in results]
    assert len(set(table_ids)) == len(table_ids), (
        f"Non-unique table_ids in LL6 results: {table_ids}"
    )
```

**Note on prefix reuse:** LL6 reuses `+1557xxx` prefixes. If `test_ll1` and `test_ll6` share the same pytest session against the same in-memory backend, `create_club` will succeed normally — OTP auth is idempotent for existing users (phone-based lookup, not re-creation), and each `create_club` call creates a new club regardless. No state collision occurs.

---

## 9. Thread Safety

### What Is Shared (Safe)

| Shared Resource | Safety Basis |
|----------------|--------------|
| `TestClient http` instance | Thread-safe: HTTPX transport forwards HTTP calls to the asyncio event loop via a thread-safe blocking portal. Multiple threads may call `http.post()` and `http.get()` simultaneously without external locking. |
| `TestClient.websocket_connect()` call site | Each call returns an independent `WebSocketTestSession`. The `TestClient` reference is shared, but the resulting WS session objects are exclusively owned by the calling thread's `SimulatedClient`. |
| `results: list[TableScenarioResult]` in orchestrator | Protected by `results_lock: threading.Lock()`. Lock is acquired only for `results.append()` — near-zero duration. |
| `BETWEEN_HANDS_DELAY` module constant | Patched once by `make_test_client()` before any thread is launched. No thread modifies it during concurrent execution. |

### What Must Not Be Shared (Excluded)

| Resource | Reason | Mitigation |
|----------|--------|------------|
| `deck_control.injected_deck()` context manager | Patches `poker_engine.engine.game_engine.fresh_shuffled_deck` — a module-level attribute in a shared Python module object. Concurrent patches from two threads produce a broken reference: thread A's `finally` restores thread B's lambda (not the true original), permanently corrupting the attribute for the rest of the process. | Excluded from all load-lite scenarios. All hands use real shuffle. Documented in feature-spec Section 3 (Out of Scope) and Open Question Q6. |
| `SimulatedClient` instances | Not thread-safe: `_ws`, `log`, `token` are plain instance attributes with no locking. | Each thread creates its own `SimulatedClient` objects using unique phone-number prefixes. No `SimulatedClient` is ever passed between threads or accessed from more than one thread. |
| `EventLog` objects | `EventLog.append()` is called synchronously from one thread (the owner thread). Not thread-safe for concurrent appends from multiple threads. | `EventLog` is owned exclusively by one thread via its `SimulatedClient`. Never shared. |

### `threading.Lock` Acquisition Discipline

Load-lite uses at most two `threading.Lock` instances per scenario:

```
results_lock      → protects: results list       → held for: results.append() only
extended_lock     → protects: extended_results   → held for: extended_results.append() only (LL3 only)
```

No nested locking occurs anywhere in load-lite. No thread holds more than one lock at a time. Deadlock is not possible under this discipline.

### The `daemon=True` Thread Flag

All threads are created with `daemon=True`. Python daemon threads are stopped when the main thread exits. If pytest's timeout kills the test process after stuck detection fires, daemon threads blocked in `drain_until` are cleaned up automatically rather than keeping the process alive indefinitely.

---

## 10. CI Runtime Estimate

| Scenario | Concurrency | Estimated Wall-Clock Duration | Notes |
|----------|-------------|-------------------------------|-------|
| LL1 | 3 tables in parallel | 15–25 s | Hand execution dominates. `BETWEEN_HANDS_DELAY=0.05 s` (patched). WS round-trips add ~0.5–1 s per message. Three hands run in parallel so wall-clock ≈ slowest thread. |
| LL2 | 3 tables in parallel | 15–25 s | Structurally identical to LL1. Join-phase HTTP calls are concurrent — no additional wall-clock cost. |
| LL3 | 3 tables + 3 spectators in parallel | 15–25 s | Spectator drain is passive and does not extend the critical path beyond `_drive_hand`. |
| LL4 | 3 tables in parallel (1 reconnect) | 15–25 s | Reconnect adds ~2–3 s on table 0; tables 1 and 2 run in parallel and complete independently. |
| LL5 | 1 table, sequential | 5–10 s | Single table. Reserve-window expiry or turn-timer auto-action adds ~3–5 s in test mode. |
| LL6 | 3 tables in parallel | 15–25 s | Same envelope as LL1. |
| **Total (sequential test functions, thread-parallel within each)** | | **35–55 s** | Well within the 60 s suite budget on a standard CI runner. |

**Key runtime driver:** `BETWEEN_HANDS_DELAY` is patched to `0.05 s` by `make_test_client()`. Without this patch, each between-hands pause alone would add `3.0 s × (hands per table) × (number of sequential hands)` to runtime, making the suite infeasible within 60 s.

**Stuck detection timeout:** `45 s` per scenario. Chosen to be:
- Well above the worst-case expected runtime (~25 s per scenario), providing ample headroom for slow CI runners.
- Low enough to allow stuck-detection error reporting and pytest teardown within the 60 s suite budget.
- Consistent with the `join(timeout=45)` pattern used in `run_all_tables`.

**`pytest.ini` note:** Load-lite test functions must not run with `pytest-xdist` parallelism (`-n auto`). Each `test_ll*` function achieves its own in-process parallelism via `threading.Thread`. Running multiple `test_ll*` functions in parallel via xdist would create competing thread pools against the same backend state and exceed the 60 s budget unpredictably. The existing `pytest.ini` omits `-n` from `addopts`; this must remain unchanged.
