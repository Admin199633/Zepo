# Feature Spec — load-lite-simulation

> Agent: Product Manager
> Gate: Feature Spec (Gate 1)
> Status: DRAFT

---

## 1. Feature Goal

Load-lite is a lightweight concurrent-table validation suite that runs inside the existing simulation harness. Its purpose is to exercise the backend's multi-table handling — session registry, per-table locking, and broadcast isolation — under a realistic but bounded concurrent load, using real `threading.Thread` concurrency rather than sequential scenario execution. Unlike the existing single-table scenarios (S1–S6, DS1–DS5), load-lite drives three tables simultaneously in a single test run and asserts that no cross-table interference occurs.

Load-lite is not a performance or stress test. It makes no measurements of latency, throughput, or resource consumption. It exists purely to catch concurrency-related correctness bugs: events leaking between tables, sessions getting stuck when multiple tables start at the same time, reconnects failing under background table activity, and spectator isolation breaking when the broadcast service handles multiple concurrent subscribers. All assertions are structural (event ordering, absence of forbidden events, session liveness), not timing-based.

---

## 2. Scope

### Concurrent Envelope

| Dimension | Value |
|-----------|-------|
| Tables active simultaneously | 3 |
| Players per table | 2 (owner + joiner) |
| Spectators per table | 1 |
| Hands per table (minimum) | 1 |
| Reconnect scenarios | 1 (one player on one designated table) |
| Join/leave churn scenarios | 1 (one player on one designated table) |
| Total scenario types | 6 (LL1–LL6) |

### Scenario Types (LL1–LL6)

| ID | Name | Description |
|----|------|-------------|
| LL1 | Multi-table concurrent activity | 3 tables active simultaneously, each completes at least 1 full hand |
| LL2 | Concurrent player joins | Owner + joiner join all 3 tables at the same time (overlapping HTTP and WS connect calls across threads) |
| LL3 | Spectator cross-table isolation | Spectators on all 3 tables simultaneously; each spectator's event log must contain only events for its own table and must never contain CARDS_DEALT |
| LL4 | Reconnect during concurrent activity | One player on table 0 disconnects and reconnects while tables 1 and 2 continue running |
| LL5 | Join/leave churn | One player on a designated table disconnects mid-hand; the table must continue and the remaining player must receive HAND_RESULT |
| LL6 | Completion summary | All 3 tables reached HAND_RESULT without any thread being stuck; summary assertion across all TableScenarioResult objects |

### Deck Strategy

All load-lite scenarios use the real shuffle (nondeterministic decks). `simulation/deck_control.injected_deck()` patches a module-level global and is not safe for concurrent use across threads; it is therefore excluded from all load-lite scenarios. Assertions are structural only: event ordering, absence of forbidden events, and session liveness.

### Concurrency Model

One `threading.Thread` per table scenario. All threads share a single `fastapi.testclient.TestClient` instance (HTTP is thread-safe on `TestClient`). Each thread uses its own independent WebSocket connections (via `client.connect()`) — WS connections are per-client and not shared across threads.

---

## 3. Out of Scope

- **Performance benchmarking**: No latency measurements, no throughput metrics, no profiling output.
- **Infrastructure metrics**: No CPU, memory, or network monitoring.
- **Production load simulation**: Load-lite targets CI with an in-process `TestClient`; it is not a tool for production traffic.
- **`deck_control.injected_deck()` under threads**: The monkey-patch is not thread-safe. Deterministic deck injection is excluded from all load-lite scenarios.
- **More than 3 concurrent tables**: The load-lite envelope is fixed at 3 tables. Scaling to N tables is a separate feature.
- **`pytest-xdist` parallelism**: Load-lite test threads are Python-level threads within a single pytest worker; xdist multi-process parallelism is out of scope.
- **WS connection sharing across threads**: Each thread creates its own `SimulatedClient` instances with independent WS sessions; no shared WS context managers.
- **Mobile client integration**: Load-lite is backend-only, same as all existing simulation scenarios.
- **New gameplay features**: No changes to poker rules, betting logic, or engine behavior.
- **Modifications to `poker_engine/` or `backend/`**: Load-lite adds only simulation infrastructure.
- **Database persistence**: In-memory app state only, consistent with existing scenarios.

---

## 4. Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC-01 | LL1 passes: all 3 table threads complete at least 1 hand (HAND_RESULT received by both players on each table) without any thread raising an unhandled exception |
| AC-02 | LL2 passes: concurrent HTTP calls (create_club, join_club) and WS connects across all 3 tables do not cause any 4xx/5xx HTTP errors or connection failures |
| AC-03 | LL3 passes: each spectator's EventLog contains zero CARDS_DEALT events |
| AC-04 | LL3 passes: each event in a spectator's log where `payload.get("table_id")` is set must equal that spectator's expected table_id; no cross-table event leakage |
| AC-05 | LL4 passes: a player who disconnects on table 0 while tables 1 and 2 run concurrently can reconnect and receive STATE_SNAPSHOT with their seat still held |
| AC-06 | LL5 passes: after one player disconnects mid-hand on the churn table, the remaining player receives HAND_RESULT (the engine does not stall) |
| AC-07 | LL6 passes: all 3 `TableScenarioResult` objects have `passed=True`; no session is left in an unfinished state |
| AC-08 | Per-table event ordering: BLINDS_POSTED appears before HAND_RESULT in every player's EventLog for every table, asserted via `log.types().index("BLINDS_POSTED") < log.types().index("HAND_RESULT")` |
| AC-09 | Stuck detection: if any table thread does not complete within 45 seconds of being launched, the test raises AssertionError naming the stuck scenario(s) |
| AC-10 | Total runtime: the full load-lite suite (LL1–LL6) completes in under 60 seconds on a standard CI runner |
| AC-11 | No ERROR events appear in any player or spectator log across all 3 tables in LL1 |
| AC-12 | Phone-number namespace isolation: each table uses a unique phone-number prefix ("+1557000", "+1557100", "+1557200") so no two tables share a user account, even when tests run sequentially against a shared in-process backend |
| AC-13 | The `load_lite` package exports `TableScenarioResult`, `run_table_scenario`, and `run_all_tables`; LL1–LL6 scenario functions are importable from `simulation.scenarios.load_lite` |
| AC-14 | Load-lite does not modify any file under `poker_engine/`, `backend/`, or existing scenario modules (S1–S6, DS1–DS5) |
| AC-15 | A single pytest test file (`tests/test_load_lite.py`) is the sole entry point; each LL scenario is a separate `def test_ll*` function using the shared `http` fixture |

---

## 5. Dependencies

| Dependency | Kind | Status |
|-----------|------|--------|
| `simulation.client.SimulatedClient` | Existing simulation primitive | Available |
| `simulation.event_log.EventLog` | Existing event capture | Available |
| `simulation.helpers.setup_two_players`, `make_client` | Existing helpers | Available |
| `simulation.app_factory.make_test_client`, `restore_delays` | Existing test app factory | Available |
| `simulation.scenarios.s1_two_player_hand._drive_hand` | Existing hand driver (internal import) | Available |
| `fastapi.testclient.TestClient` | FastAPI test transport | Available |
| `threading` (Python stdlib) | Thread concurrency | Available — no new dependencies |
| `dataclasses` (Python stdlib) | `TableScenarioResult` dataclass | Available — no new dependencies |
| `backend.session_registry.TableSessionRegistry` | Indirectly exercised via HTTP/WS | Available |
| `backend.sessions.session_manager.TableSessionManager` | Indirectly exercised via WS | Available |

---

## 6. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | A `threading.Thread` blocks indefinitely waiting for a WS message that never arrives (e.g., because the table session stalled under concurrent load), causing the entire test suite to hang | High | `thread.join(timeout=45)` on every launched thread; any thread still alive after timeout → AssertionError naming the stuck scenario. The 45 s budget is well under the pytest default timeout and the 60 s suite budget. |
| R2 | Cross-table event leakage caused by a broadcast service bug surfaces only under concurrent multi-table load (the existing S3 scenario exercises spectator isolation on a single table) | High | LL3 asserts `payload.get("table_id") == expected_table_id` on every spectator event; CARDS_DEALT absence is also checked. Two independent assertion layers. |
| R3 | Phone-number collisions between load-lite threads and other test files running concurrently in the same pytest session | Medium | Load-lite uses "+1557xxx" and "+1558xxx" prefixes, distinct from existing scenarios ("+1555xxx", "+1556xxx"). Documented in the phone-prefix strategy. |
| R4 | `TestClient` HTTP thread-safety: the FastAPI `TestClient` runs the ASGI app in a background asyncio event loop in a separate thread; concurrent HTTP calls from multiple Python threads are forwarded into that event loop. If the backend has any non-asyncio-safe shared state (e.g., a dict mutated without locks), race conditions may appear only under load-lite | Medium | `TableSessionRegistry` and `TableSessionManager` both use `asyncio.Lock`. Load-lite will expose any unprotected shared state. If a failure appears, treat it as a backend bug to fix. |
| R5 | WS drain contention: `client.drain_until()` is a blocking synchronous call. If a spectator's drain loop is slow (e.g., waiting for HAND_RESULT after a long hand), the thread may lag significantly behind the player threads, creating apparent ordering issues | Low | Spectators drain passively with `max_msgs=100`; players drive the hand. Spectator drain is called after `_drive_hand` completes, so ordering is deterministic within each thread. |
| R6 | LL5 churn scenario: after one player disconnects, the engine's auto-fold or reserve-window logic must complete the hand. If the reserve window is longer than `BETWEEN_HANDS_DELAY` * max_actions, the hand may not resolve within the thread's slice of the 45 s budget | Low | `BETWEEN_HANDS_DELAY` is patched to 0.05 s by `make_test_client()`. The engine's auto-action timer under test mode is 2 s maximum. A full LL5 churn hand is expected to resolve in under 10 s. |
| R7 | `threading.Lock` contention on the shared `results` list in the orchestrator: with 3 threads appending `TableScenarioResult` objects, contention is negligible, but incorrect lock usage (e.g., appending outside the lock) could cause a lost result | Low | The orchestrator uses a single `threading.Lock` wrapping `results.append()`. The lock is held only for the append operation, minimising contention duration. |

---

## 7. Open Questions (Resolved)

| # | Question | Resolution |
|---|----------|------------|
| Q1 | What is the load-lite envelope? | 3 concurrent tables, each with 2 players + 1 spectator, 1 hand minimum, 1 reconnect scenario (on one table), 6 scenario types total |
| Q2 | What concurrency model should load-lite use? | Python `threading.Thread` — one thread per table scenario. Shared `TestClient` for HTTP (thread-safe). Separate WS context managers per thread (independent per `SimulatedClient.connect()`). Async primitives and `anyio` are unnecessary and would complicate the sync `TestClient` usage. |
| Q3 | How are per-table events ordered for assertions? | Within each table's player `EventLog`, assert `BLINDS_POSTED` before `HAND_RESULT` using `log.types().index("BLINDS_POSTED") < log.types().index("HAND_RESULT")`. |
| Q4 | How is cross-table event leakage detected? | Each spectator's EventLog is checked in two ways: (a) `assert not spectator.log.has_type("CARDS_DEALT")`, and (b) for every event `e` where `e.payload.get("table_id")` is non-None, assert `e.payload["table_id"] == expected_table_id`. |
| Q5 | How are stuck threads detected? | `threading.Thread.join(timeout=45)` is called on every launched thread after all threads are started. Any thread still alive (`thread.is_alive()`) after the join timeout causes `AssertionError` listing the names of stuck scenarios. |
| Q6 | Should load-lite use deterministic or nondeterministic decks? | All load-lite scenarios use real shuffle (nondeterministic). `deck_control.injected_deck()` patches a module-level global and is not thread-safe — concurrent use from multiple threads would corrupt the function reference permanently. Structural assertions (ordering, event presence/absence) are sufficient for load-lite's correctness goals. |
| Q7 | What is the total runtime budget? | Under 60 seconds for the full LL1–LL6 suite. Expected: ~15–25 s per table × 3 tables in parallel → ~25–35 s for LL1; remaining scenarios run sequentially against the same `TestClient` and are lighter (no full hand required for LL4/LL5 which reuse LL1's table setup pattern). |

---

## 8. Minimum Load-Lite Scenarios

### LL1 — Three Tables Active Concurrently

Three table setups are launched as simultaneous `threading.Thread` instances. Each thread: authenticates 2 players, creates a club, joins, connects WS, drives one full hand to HAND_RESULT. All 3 threads must complete before assertions run. Assertions: HAND_RESULT in both players' logs on each table; BLINDS_POSTED before HAND_RESULT; no ERROR events.

### LL2 — Concurrent Player Joins Across All Three Tables

Exercises the join-and-connect phase specifically: within each thread, the owner creates the club and the joiner calls `join_club` and WS-connects simultaneously with the same operation on the other 2 tables. Validates that `TableSessionRegistry.get_or_create` under its `asyncio.Lock` handles concurrent requests from 3 tables without deadlock or duplicate-session creation.

### LL3 — Spectators on All Three Tables with Cross-Table Isolation Verified

Each table has a spectator (3 spectators total). All spectators connect simultaneously (one per thread). After hands complete, every spectator log is inspected for CARDS_DEALT absence and for cross-table event leakage (events whose `table_id` does not match the spectator's table). This directly exercises the broadcast service's per-table subscriber filtering under concurrent subscriber sets.

### LL4 — Reconnect During Concurrent Table Activity

Table 0's owner disconnects (WS context exit) after BLINDS_POSTED, while tables 1 and 2 continue running their hands in separate threads. Table 0's owner then reconnects (second `connect()` + `send_join`). Assertions: STATE_SNAPSHOT received after reconnect; owner's seat still present in snapshot; tables 1 and 2 both reach HAND_RESULT unaffected.

### LL5 — Join/Leave Churn

On a designated churn table, the joiner disconnects mid-hand (exits WS context) without reconnecting. The owner must still receive HAND_RESULT — the engine must resolve the hand (via auto-fold or timeout action for the absent player) rather than stalling. Assertion: owner log contains HAND_RESULT; no ERROR events.

### LL6 — Completion Summary

A meta-scenario that runs after LL1–LL5 have executed. Aggregates all `TableScenarioResult` objects and asserts that every result has `passed=True`. Provides a single human-readable failure message if any table scenario failed, listing `table_id`, `error`, and the `event_types` sequence captured before failure.
