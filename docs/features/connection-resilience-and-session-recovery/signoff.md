# Sign-off — connection-resilience-and-session-recovery

> Gate: Implementation Gate
> Status: APPROVED — READY FOR IMPLEMENTATION

---

## Feature Summary

Harden the existing reconnect implementation by fixing two concrete defects and adding comprehensive test coverage. The reconnect architecture (60-second reserve timer, `_do_reconnect` flow, `STATE_SNAPSHOT` resync) is correct. Changes are:
1. Fix `disconnect()` double-disconnect guard — prevent timer reset if player already disconnected
2. Wire `disconnect_reserve_seconds` through `TableSessionManager.__init__` and `TableSessionRegistry`
3. New `tests/test_connection_resilience.py` covering all reconnect scenarios
4. New simulation scenario S7 (reserve window expiry end-to-end)

---

## PM Approval

- [x] Feature goal defined: harden reconnect reliability under mobile-network conditions
- [x] 2 concrete defects identified and scoped (double-disconnect, config wire-up)
- [x] 10 acceptance criteria defined (AC-01 through AC-10)
- [x] 5 disconnect/reconnect scenarios explicitly defined (fresh, double, within-window, after-expiry, no-reconnect)
- [x] Out of scope explicitly listed (crash recovery, spectator reserve, hand replay, push notifications)
- [x] 5 risks documented with mitigations
- Approved by: Product Manager Agent
- Date: 2026-03-19

---

## Player Feedback Approval

- [x] 60-second reserve window: calibrated correctly for real play
- [x] Seat retention during window: essential, correct
- [x] STATE_SNAPSHOT on reconnect: right behavior
- [x] SIT_OUT after expiry (not kicked): proportionate
- [x] Double-disconnect timer reset: identified as exploitable — mandatory fix
- [x] reserve_until field: present in broadcast for client to display countdown
- Approved by: Poker Player Reviewer Agent
- Date: 2026-03-19
- Notes:
  - Double-disconnect fix is **mandatory** — timer exploit must be provably fixed with a test
  - Client-side display of reserve_until countdown is a known gap (client concern, not backend)

---

## Technical Design Approval

- [x] No new architecture — hardening only
- [x] Change 1: `if not player.is_connected: return` guard in `disconnect()` — exact code specified
- [x] Change 2: `disconnect_reserve_seconds: Optional[int] = None` param — exact code specified
- [x] `self._disconnect_reserve_seconds` replaces all `DISCONNECT_RESERVE_SECONDS` usages inside class
- [x] Module-level constant kept as fallback — existing test patching patterns preserved
- [x] `session_registry.py` change specified — passes `settings.disconnect_timeout_seconds`
- [x] S7 patching approach: `manager._disconnect_reserve_seconds = 0.1` after manager creation
- [x] Engine isolation: zero `poker_engine/` changes
- [x] Files to modify/create: 5 files listed; files NOT to change: 8 listed
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19

---

## QA Approval

- [x] 19 unit tests covering all ACs
- [x] TC-02, TC-03: double-disconnect guard proven by test (mandatory per player feedback)
- [x] TC-06, TC-07, TC-08: reconnect-after-expiry tested (previously untested behavior)
- [x] TC-11: `reserve_until` accuracy verified
- [x] TC-12, TC-13: SYNC_REQUEST coverage (previously untested)
- [x] TC-18: full lifecycle test (join → disconnect → expiry → reconnect → SIT_OUT → SIT_IN → WAITING)
- [x] TC-S7: simulation end-to-end scenario
- [x] Fast timer: `disconnect_reserve_seconds=0.05` for unit tests; `0.1` for S7 simulation
- [x] Module constant patching (TC-10) preserves compatibility with existing test patterns
- [x] 5 failure cases documented
- [x] Regression gate: 272 existing + 20 new = 292 minimum
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19
- Notes:
  - TC-17 (spectator disconnect) must assert no timer task is created
  - TC-16 (duplicate reconnect) must assert both calls return `success=True`
  - TC-S7 must patch `manager._disconnect_reserve_seconds` after first WS connect creates the manager

---

## What Is Approved for Implementation

**Implement now:**
- T1: Fix `backend/sessions/session_manager.py` — double-disconnect guard + `disconnect_reserve_seconds` param + replace constant usages
- T2: Fix `backend/session_registry.py` — pass `settings.disconnect_timeout_seconds`
- T3: Create `tests/test_connection_resilience.py` — 19 unit tests
- T4: Create `simulation/scenarios/s7_disconnect_reserve_expiry.py`
- T5: Update `tests/test_simulation_scenarios.py` — add `test_s7_disconnect_reserve_expiry`

**Must NOT change during implementation:**
- `backend/persistence/` — any file
- `poker_engine/` — zero engine changes
- `backend/realtime/ws_router.py`
- `tests/conftest.py`
- `tests/test_session_manager.py`
- All other existing test files except `tests/test_simulation_scenarios.py`

**Deferred:**
- Crash recovery (server restart with active disconnect timers lost)
- Spectator reserve windows
- Full hand-event replay after reconnect
- Push notifications

---

## Final Decision

- [x] **APPROVED — ready to implement**
- [x] **ALL GATES CLEARED — proceed with coding**
- [ ] **BLOCKED — do not implement**

Decision by: Product Manager Agent + Poker Player Reviewer Agent + Senior Mobile Game Developer Agent + Senior QA Reviewer Agent
Date: 2026-03-19

**GO — proceed with implementation.**

---

## Implementation Status

**COMPLETE — 2026-03-19**

All 5 tasks implemented. Test results:

- `tests/test_connection_resilience.py` — **24/24 passed** (1.63 s)
- `tests/test_simulation_scenarios.py::test_s7_disconnect_reserve_expiry` — **1/1 passed** (1.71 s)
- Full regression — **297/297 passed** (105 s)

### Implementation Notes

1. **Lazy constant reading**: `_disconnect_reserve_seconds` stored as `Optional[int]` with `None` as sentinel. A `_resolve_reserve_seconds()` helper reads the module-level constant lazily when no explicit value is set. This preserves backward compatibility with existing tests that patch `sm_module.DISCONNECT_RESERVE_SECONDS` after the fixture is created.

2. **Registry wiring**: `session_registry.py` now passes `settings.disconnect_timeout_seconds` to `TableSessionManager.__init__`, so the env var `DISCONNECT_TIMEOUT_SECONDS` takes effect in production.

3. **S7 patching approach**: The scenario patches `manager._disconnect_reserve_seconds = 0.1` directly on the manager instance after the first WS connect creates it (accessed via `http.app.state.registry.get(table_id)`).

### Files Created
- `tests/test_connection_resilience.py` — 24 new tests
- `simulation/scenarios/s7_disconnect_reserve_expiry.py` — new simulation scenario

### Files Modified
- `backend/sessions/session_manager.py` — added `disconnect_reserve_seconds` param; `_resolve_reserve_seconds()` helper; double-disconnect guard; use `_resolve_reserve_seconds()` in `disconnect()` and `_run_disconnect_timer()`
- `backend/session_registry.py` — added `from .config import settings`; passes `disconnect_reserve_seconds=settings.disconnect_timeout_seconds`
- `tests/test_simulation_scenarios.py` — added import of `s7_disconnect_reserve_expiry` and `test_s7_disconnect_reserve_expiry`
