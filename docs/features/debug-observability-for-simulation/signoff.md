# Sign-off — debug-observability-for-simulation

> Gate: Implementation Gate (Gate 5)
> Status: IMPLEMENTATION COMPLETE — all gates cleared

---

## Feature Summary

Add `simulation/debug/` — a lightweight, bounded, CI-safe debug output package for simulation failures. Captures per-client event summaries, formats failure reports with annotated sequences, provides stuck-scenario diagnostics, and summarizes load-lite multi-table runs. Zero runtime cost on passing tests. Zero production code changes.

---

## PM Approval

- [x] Feature goal defined: structured failure visibility for simulation failures, not production monitoring
- [x] 7 debugging pain points resolved
- [x] Scope limited to `simulation/debug/` + 2 integration touch points
- [x] Out of scope explicitly listed (no dashboards, no file export, no production changes)
- [x] 12 acceptance criteria defined (including AC-07 hidden-card safety, AC-08 failure-only output, AC-09 ≤50ms runtime overhead)
- [x] 7 design questions resolved: artifacts (FailureReport), summaries (ClientSummary/TableSummary), always-on capture, hidden-card masking, stuck diagnostics (drain_target + elapsed), load-lite summary (LoadLiteSummary), runtime budget (≤50ms, ≤30 lines)
- [x] 5 risks documented with mitigations
- Approved by: Product Manager Agent
- Date: 2026-03-19
- Notes: Scope is tight and well-bounded. The key insight is that EventLog already captures everything — this feature only formats it better on the failure path. No risk of scope creep toward production observability.

---

## Technical Design Approval

- [x] 3-module `simulation/debug/` package designed (`snapshot.py`, `report.py`, `summary.py`)
- [x] `ClientSummary` with role-aware masking (`is_spectator` flag, `_SENSITIVE_KEYS`)
- [x] `ScenarioSnapshot` for multi-client capture
- [x] `stuck_diagnostic` showing last event per client + elapsed time
- [x] `format_ordering_failure` with annotated `>>>` markers
- [x] `format_leakage_failure` with spectator sequence + offending event
- [x] `LoadLiteSummary` with ≤10-line tabular format
- [x] Integration design for `client.py` and `assertions.py` (lazy import to avoid circular imports)
- [x] Hidden-card safety: two-layer protection (role-aware masking + engine broadcast isolation)
- [x] Output size budget documented and enforced by constants
- [x] Import boundary explicit: no `backend.*` or `poker_engine.*`
- [x] Zero production code changes
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
- Notes: The lazy-import pattern in `drain_until` is the correct approach to avoid circular imports. `_mask_payload` whitelist approach is safer than blacklist. `LoadLiteSummary` replaces the inline formatting in `assert_all_results_passed` cleanly.

---

## QA Approval

- [x] ~30 unit tests specified across 12 test sections
- [x] Hidden-card safety: 3 dedicated tests (spectator masking, `hand` masking, player unmasked)
- [x] Output absence on green runs: 2 dedicated tests
- [x] Output size budget: line-count assertions in `ClientSummary` and `LoadLiteSummary` tests
- [x] `drain_until` enrichment: 2 tests (failure has ClientSummary, success produces no output)
- [x] `assert_spectator_isolation` enrichment: 2 tests (leakage message, CARDS_DEALT message)
- [x] `assert_event_ordering` enrichment: 1 test (annotated sequence)
- [x] 4 flakiness risks documented with mitigations
- [x] Regression gate: 200 tests must continue to pass
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19
- Notes: Hidden-card safety tests are the highest-risk area — the 3 dedicated tests are necessary and sufficient. The `json.dumps(default=str)` approach eliminates the serialisation failure risk cleanly. The output-absence tests are important to prevent debug noise in CI.

---

## What Is Approved for Implementation

**Implement now (M0–M2):**
- T0: `simulation/debug/__init__.py`
- T1: `simulation/debug/snapshot.py`
- T2: `simulation/debug/report.py`
- T3: `simulation/debug/summary.py`
- T4: Enrich `simulation/client.py` `drain_until`
- T5: Enrich `simulation/load_lite/assertions.py` (3 enrichments)
- T6: `tests/test_debug_observability.py` (~30 tests)

**Deferred — do not implement in this feature:**
- File-based debug output / disk snapshots
- Structured JSON debug reports
- pytest plugin or fixture for automatic snapshot capture
- Timeline visualisation
- External error tracking integration

**Must not change during implementation:**
- `poker_engine/` — zero changes
- `backend/` — zero changes
- All existing scenario modules (S1–S6, DS1–DS5, LL1–LL6)
- `tests/test_simulation_scenarios.py`
- `tests/test_simulation_deterministic.py`
- `tests/test_deck_control.py`
- `tests/test_load_lite.py`

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

- [x] 29 new unit tests in `tests/test_debug_observability.py` — all PASSED (0.63 s)
- [x] Full regression: 229/229 tests passed (94.67 s) — +29 from baseline of 200
- [x] Hidden-card safety: spectator masking tests PASSED
- [x] Output absence on green runs: PASSED
- [x] `drain_until` enrichment: PASSED (mocked WS approach)
- [x] `assert_spectator_isolation` enrichment: PASSED
- [x] `assert_event_ordering` enrichment: PASSED
- [x] `LoadLiteSummary` integration: PASSED
- [x] Zero imports from `backend.*` or `poker_engine.*` in `simulation/debug/`

Run date: 2026-03-19

---

## Final Decision

- [x] **APPROVED — ready to merge**
- [x] **IMPLEMENTATION COMPLETE**
- [ ] **BLOCKED — do not implement**
