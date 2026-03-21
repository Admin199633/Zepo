# Sign-off — load-lite-simulation

> Gate: Implementation Gate (Gate 5)
> Status: IMPLEMENTATION GATE PASSED — QA and Release Gates pending post-implementation

---

## Feature Summary

Add a lightweight concurrent load harness to the simulation package. Three tables run simultaneously via `threading.Thread`, each completing ≥1 full hand with 2 players and 1 spectator. Six scenarios (LL1–LL6) assert correctness under concurrency: event ordering, spectator isolation, reconnect stability, join/leave churn, and stuck-session detection. No production code changes.

---

## PM Approval

- [x] Feature goal defined and scoped (system confidence, not performance benchmarking)
- [x] Six required scenarios specified (LL1–LL6) with precise acceptance criteria
- [x] Out-of-scope items explicitly listed (no perf metrics, no >3 tables, no `deck_control` under threads)
- [x] Dependencies confirmed available (existing simulation package, `threading` stdlib)
- [x] Seven design questions resolved: envelope (3 tables), concurrency model (threads), event ordering, leakage detection, stuck detection, deck strategy (nondeterministic), runtime budget (<60 s)
- Approved by: Product Manager Agent
- Date: 2026-03-19
- Notes: Scope is tight and additive. LL5 churn and LL4 reconnect-under-concurrency close real coverage gaps not reachable from sequential S1–S6.

---

## Technical Design Approval

- [x] `TableScenarioResult` dataclass designed with `table_index`, `table_id`, `passed`, `error`, `event_types`
- [x] Orchestrator pattern: `run_all_tables` + `threading.Lock` + `thread.join(timeout=45)` + `is_alive()` stuck detection
- [x] `run_standard_table` reusable core for LL1/LL2/LL3
- [x] Phone prefix strategy documented and isolated (`+1557xxx`, `+1558xxx`)
- [x] Thread safety analysis: `SimulatedClient` is per-thread; `TestClient` HTTP is shared and safe; `deck_control` excluded by design
- [x] Import boundary rules explicit (no `poker_engine/` or `backend/` imports from load-lite)
- [x] Per-scenario designs for LL1–LL6 with assertion code
- [x] Runtime budget analysed: <60 s expected; 45 s thread timeout is well within pytest default
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
- Notes: Thread-per-table design is the minimal safe approach for sync `TestClient`. Orchestrator pattern is clean. Phone prefix isolation prevents cross-test contamination.

---

## QA Approval

- [x] 12 QA plan sections covering all required areas
- [x] Per-scenario test steps, assertions, and failure cases for LL1–LL6
- [x] 5 flakiness risks identified with mitigations
- [x] 8 regressions this feature catches documented
- [x] Spectator isolation tested at two assertion layers (CARDS_DEALT absence + table_id cross-check)
- [x] Stuck-thread detection tested via thread-join-timeout mechanism
- [x] LL5 auto-action timing risk documented (30 s timer fits within 45 s thread budget)
- [x] QA sign-off conditions defined
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19
- Notes: LL3 cross-table leakage check and LL5 churn are the highest-value new scenarios. Orchestrator stuck-detection closes the hanging-test risk definitively.

---

## What Is Approved for Implementation

**Implement now (M0–M3):**
- T0: `simulation/load_lite/__init__.py`
- T1: `simulation/load_lite/orchestrator.py`
- T2: `simulation/load_lite/table_scenario.py`
- T3: `simulation/load_lite/assertions.py`
- T4: `simulation/scenarios/load_lite/__init__.py`
- T5: `simulation/scenarios/load_lite/ll1_multi_table.py`, `ll2_concurrent_joins.py`, `ll3_spectator_isolation.py`
- T6: `simulation/scenarios/load_lite/ll4_reconnect_concurrent.py`
- T7: `simulation/scenarios/load_lite/ll5_churn.py`
- T8: `simulation/scenarios/load_lite/ll6_completion_summary.py`
- T9: `tests/test_load_lite.py`

**Deferred — do not implement in this feature:**
- N-table parametric scaling
- Performance measurement / latency reporting
- `pytest-xdist` group markers
- CI lint step for import boundaries

**Must not change during implementation:**
- `poker_engine/` — zero changes
- `backend/` — zero changes
- `simulation/scenarios/s1_*.py` through `s6_*.py` — zero changes
- `tests/test_simulation_scenarios.py` — zero changes
- `tests/test_simulation_deterministic.py` — zero changes

---

## Final Decision

- [x] **APPROVED — ready to merge**
- [x] **IMPLEMENTATION GATE PASSED — all pre-implementation gates cleared; proceed with coding**
- [ ] **BLOCKED — do not implement**

Decision by: Product Manager Agent + Senior Mobile Game Developer Agent + Senior QA Reviewer Agent
Date: 2026-03-19

**GO — proceed with implementation.**

---

## QA Status (Post-Implementation)

- [x] LL1 — Multi-table concurrent — PASSED
- [x] LL2 — Concurrent joins — PASSED
- [x] LL3 — Spectator isolation — PASSED
- [x] LL4 — Reconnect during concurrent activity — PASSED
- [x] LL5 — Join/leave churn — PASSED
- [x] LL6 — Completion summary — PASSED
- [x] All 131 tests (full suite including existing S1–S6, DS1–DS5, deck control) — PASSED
- [x] Total load-lite runtime: 31.85 s (budget: 60 s)

Run date: 2026-03-19

---

## Final Decision

- [x] **APPROVED — ready to merge**
- [x] **IMPLEMENTATION COMPLETE — all gates cleared**
- [ ] **BLOCKED — do not implement**

Decision by: Product Manager Agent + Senior Mobile Game Developer Agent + Senior QA Reviewer Agent
Date: 2026-03-19
