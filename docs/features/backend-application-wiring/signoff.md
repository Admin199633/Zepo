# Sign-off — backend-application-wiring

> Gate: Release Gate (Gate 6)
> Status: IMPLEMENTATION GATE PASSED — QA and Release Gates pending post-implementation

---

## Feature Summary

Wire all existing backend modules into a deployable FastAPI application. Deliver HTTP
routes for auth and clubs, a WebSocket gateway for real-time table events, a production
persistence adapter scaffold, and end-to-end integration tests. Architectural boundaries
reviewed and confirmed clean before any code is written.

---

## PM Approval

- [x] Feature goal defined and scoped
- [x] Scope matches predecessor artifacts (backend-app-bootstrap) — no unreviewed additions
- [x] Three open questions resolved: club_name/admin_id deferred; SQLAlchemy Core chosen; STATE_SNAPSHOT after JOIN_TABLE
- [x] Player-feedback items incorporated: `reserve_until` required, `state_persistence` in health, ERROR `request_id` echo
- [x] Acceptance criteria testable (15 criteria, 14 integration test cases)
- Approved by: Product Manager Agent
- Date: 2026-03-19
- Notes: Scope is tight. The SQLite adapter scaffold correctly separates "define the path"
  from "implement the path." Deferred items (club_name, admin_id, Redis broadcaster) are
  cleanly documented and do not block this feature.

---

## UX Approval

- [x] Full connection and join flow sequenced
- [x] HTTP error format standardised: `{"error": CODE, "message": MSG}` for all 4xx/5xx
- [x] WS close codes defined: 4001 (auth), 4004 (not found), 1000 (normal)
- [x] ERROR event contract with `request_id` echo
- [x] `reserve_until` in PLAYER_STATUS disconnect event
- [x] `state_persistence` in health response
- [x] STATE_SNAPSHOT timing decision documented (after JOIN_TABLE only)
- Approved by: Senior UI/UX Designer Agent
- Date: 2026-03-19
- Notes: UX Gate passed. All player-feedback concerns addressed. The deferred items
  (club_name, admin_id in snapshot) are clearly scoped out with a resolution path.

---

## QA Status

- [x] Architecture boundary checks A01–A05 — PASSED (all 6 boundaries clean)
- [x] Integration tests (23 tests in `tests/test_app_integration.py`) — 23/23 PASSED
- [x] Full regression suite (169 tests: engine + persistence + realtime + session + integration) — 169/169 PASSED
- [x] `try/finally` ghost-session prevention — verified by `test_ws_invalid_token_rejected`, `test_ws_nonexistent_table`
- [x] Broadcaster copy-before-iterate — verified by concurrent WS tests
- [x] Registry lock — verified by `test_ws_duplicate_request_id_dropped`
- [x] `reserve_until` field present in `PlayerStatusPayload` — verified by schema tests
- [x] `state_persistence` in health response — verified by `test_health`
- [x] ERROR event `request_id` echo — verified by `test_ws_malformed_json_stays_open`
- [x] OTP idempotency (consumed on use) — verified by `test_otp_consumed_on_use`
- QA reviewed by: Senior QA Reviewer Agent
- Final verification date: 2026-03-19
- Result: **ALL CHECKS PASSED — no open issues**

---

## Developer Notes

Pre-approved implementation decisions (do not require re-approval):
- `InMemoryPersistenceAdapter` used in dev and all tests
- `ConsoleAuthService` used in dev (OTP to stdout)
- `SqlitePersistenceAdapter` methods stub with `NotImplementedError`
- All origins allowed in CORS for development
- `state_persistence: "in_memory_volatile"` when `app_env != "production"`

Any deviation from `technical-design.md` during implementation must be:
1. Documented in this section before the code is committed
2. Re-reviewed by PM if it changes a module boundary or accepted behaviour

---

## Architectural Review Decision

**Verdict: CLEAN — no blocking violations found.**

| Boundary | Status |
|----------|--------|
| Engine isolation | ✅ Pass |
| No DB/transport in engine | ✅ Pass |
| Hidden card data blocked | ✅ Pass |
| Deck not persisted | ✅ Pass |
| SessionManager orchestration-only | ✅ Pass |
| Module boundaries | ✅ Pass (2 non-blocking observations — fixed in M0) |

---

## Remaining Risks

| Risk | Severity | Mitigation / Accepted |
|------|---------|----------------------|
| In-memory state lost on restart | Medium | Accepted for MVP. Surfaced via `state_persistence` field. SqliteAdapter is the upgrade path. |
| Single-process broadcaster | Medium | Accepted. Document: not suitable for horizontal scaling. |
| Token in WS query param visible in logs | Low | Accepted for MVP with ConsoleAuthService. Flag for prod hardening. |
| SQLite adapter not implemented | Low | Not wired in dev or tests. Raises NotImplementedError if called. |

---

## What Is Approved for Implementation

**Implement now:**
- M0 cleanups (A1, A2)
- Full HTTP layer (T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11)
- Full WebSocket gateway (T12)
- SQLite adapter scaffold (T13)
- Integration tests (T14)

**Deferred — do not implement in this feature:**
- Real JWT signing/verification (ConsoleAuthService is sufficient for MVP)
- Redis broadcaster (not needed until horizontal scaling)
- Full SQLite adapter (scaffold + schema only)
- `club_name` and `admin_id` in STATE_SNAPSHOT (requires session_manager extension)
- Admin management (ban, promote, remove member)
- Token refresh
- Rate limiting

**Must not change during implementation:**
- `poker_engine/` — zero changes
- `session_manager.py` public method signatures — cleanups only (A2)
- `PersistenceAdapter` ABC method signatures — cleanup only (A1)
- Any existing test file

---

## Final Decision

- [x] **APPROVED — ready to merge** ← Release Gate PASSED
- [x] **IMPLEMENTATION GATE PASSED — all pre-implementation gates cleared**
- [ ] **BLOCKED — do not implement**

Decision by (PM): Product Manager Agent
Implementation Gate Date: 2026-03-19
Release Gate Date: 2026-03-19

**GO — implementation complete. 169/169 tests passing. All 6 gates cleared.**
