# Sign-off — deterministic-simulation-scenarios

> Gate: Implementation Gate (Gate 5)
> Status: IMPLEMENTATION GATE PASSED — QA and Release Gates pending post-implementation

---

## Feature Summary

Extend the simulation harness with deterministic deck injection and 5 new scenario variants (DS1–DS5) that assert exact, repeatable outcomes. Mechanism: monkey-patch `poker_engine.engine.game_engine.fresh_shuffled_deck` via a context manager in `simulation/deck_control.py`. No production code changes.

---

## PM Approval

- [x] Feature goal defined and scoped
- [x] Five required deterministic scenarios specified (DS1–DS5) with precise acceptance criteria
- [x] Out-of-scope items explicitly listed (no production changes, no seeded RNG, no property-based testing)
- [x] Dependencies confirmed available (existing simulation package, poker_engine models)
- [x] Five design questions resolved: deck injection via module-level patch; test-only module; additive scenarios; payload-only assertions; context manager isolation
- Approved by: Product Manager Agent
- Date: 2026-03-19
- Notes: Scope is tight and additive. Existing s1–s6 are unaffected. All five ACs are mechanically verifiable.

---

## Technical Design Approval

- [x] Deterministic strategy chosen: module-level monkey-patch with `finally`-guarded restoration
- [x] Three alternatives compared and rejected (seeded RNG, constructor injection, full replay)
- [x] Full `deck_control.py` implementation provided (actual runnable code)
- [x] Two deck recipes documented with exact card positions and expected winners
- [x] `complete_deck()` padding helper designed
- [x] Per-scenario design for DS1–DS5 with exact assertion code
- [x] Assertion strategy: payload-only, no internal engine state accessed
- [x] Test isolation via context manager scope documented
- [x] Module boundary rules explicit (no import from production)
- [x] Thread-safety risk documented; mitigation: no `pytest-xdist` parallelism
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
- Notes: Design is clean and minimal. The monkey-patch approach is established Python test practice. Zero production files modified.

---

## QA Approval

- [x] Twelve QA plan sections covering all required areas
- [x] Per-scenario test steps, assertions, and failure cases for DS1–DS5
- [x] Deterministic replay verification strategy defined
- [x] Four deck patch isolation tests specified (normal exit, exception exit, sequential, invalid input)
- [x] Hidden card filtering assertions are exact under deterministic conditions
- [x] Duplicate request (DS5) failure modes and assertions specified
- [x] Reconnect snapshot exact card comparison (DS3) specified
- [x] Event ordering assertions (COMMUNITY_CARDS before HAND_RESULT) specified
- [x] Five flakiness risks identified with mitigations
- [x] Eight regressions this feature catches documented
- [x] QA sign-off conditions defined
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19
- Notes: Deterministic scenarios materially strengthen the regression suite. DS5 (duplicate request) has no nondeterministic equivalent and closes a real coverage gap.

---

## QA Status (Post-Implementation)

- [x] DS1 — Known winner — PASSED
- [x] DS2 — Known board — PASSED
- [x] DS3 — Deterministic reconnect — PASSED
- [x] DS4 — Deterministic spectator — PASSED
- [x] DS5 — Duplicate request — PASSED
- [x] Patch isolation tests (14) — PASSED
- [x] All 6 existing s1–s6 scenarios still pass — PASSED
- [x] Full regression 194 tests — PASSED (194 passed in 59.83 s)

Run date: 2026-03-19

---

## What Is Approved for Implementation

**Implement now (M0–M3):**
- T0: `simulation/deck_control.py`
- T1: `simulation/scenarios/deterministic/__init__.py`
- T2–T6: DS1–DS5 scenario modules
- T7: `tests/test_simulation_deterministic.py`
- T8: `tests/test_deck_control.py`

**Deferred — do not implement in this feature:**
- Replay consistency test (DS1 run twice, winners compared) — can be added as a follow-up
- `pytest-xdist` group isolation guard — deferred until parallelism is introduced
- CI lint step asserting no `from simulation` imports in production code — deferred
- Property-based / Hypothesis integration

**Must not change during implementation:**
- `poker_engine/` — zero changes
- `backend/` — zero changes
- `simulation/scenarios/s1_*.py` through `s6_*.py` — zero changes
- `tests/test_simulation_scenarios.py` — zero changes

---

## Final Decision

- [x] **APPROVED — ready to merge**
- [x] **IMPLEMENTATION GATE PASSED — all pre-implementation gates cleared; proceed with coding**
- [ ] **BLOCKED — do not implement**

Decision by: Product Manager Agent + Senior Mobile Game Developer Agent + Senior QA Reviewer Agent
Date: 2026-03-19

**GO — proceed with implementation.**
