# Sign-off — light-persistence-layer

> Gate: Implementation Gate
> Status: APPROVED — READY FOR IMPLEMENTATION

---

## Feature Summary

Implement `SqlitePersistenceAdapter` — fill all `NotImplementedError` stubs using SQLAlchemy Core and `aiosqlite`. Fix schema/model field mismatches. Wire conditional adapter selection into `main.py`. Prove restart safety with a new `tests/test_sqlite_persistence.py` test suite.

The interface (`PersistenceAdapter` ABC), the reference implementation (`InMemoryPersistenceAdapter`), and the schema skeleton (`SqlitePersistenceAdapter`) all already exist. This feature completes the SQLite path without touching engine code, gameplay logic, or existing tests.

---

## PM Approval

- [x] Feature goal defined: move core entities from in-memory-only to durable restart-safe state
- [x] Scope limited to implementing existing scaffold — no new abstractions
- [x] 13 acceptance criteria defined (AC-01 through AC-13)
- [x] Entities durable vs in-memory table explicit
- [x] Restart behavior in-scope vs deferred explicitly listed
- [x] 6 risks documented with mitigations
- [x] 5 open questions resolved
- Approved by: Product Manager Agent
- Date: 2026-03-19

---

## Technical Design Approval

- [x] SQLite chosen for this phase — justified (existing schema, aiosqlite, single-process, zero infra)
- [x] Schema corrections identified and specified (`player_stats`, `chat_messages`, `player_sessions`)
- [x] All 14 adapter methods designed with exact SQL and Python patterns
- [x] Transaction boundaries documented per operation
- [x] `use_sqlite: bool` flag added to `Settings` — in-memory remains default
- [x] `main.py` conditional adapter selection designed
- [x] `simulation/app_factory.py` — explicitly not changed
- [x] Engine isolation preserved — zero `poker_engine/` changes
- [x] Migration path to Postgres documented
- [x] 12 files-to-create-or-modify listed
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
- Notes:
  - `PlayerSession.timeout_count` and `disconnect_at` fields must be added to the schema (scaffold gap)
  - `ChatMessage.is_system` field must be added to the schema (scaffold gap)
  - Leaderboard sort key is `wins DESC` (consistent with `InMemoryPersistenceAdapter`)

---

## QA Approval

- [x] 33 test cases defined covering all adapter methods and restart safety
- [x] Restart simulation uses `tmp_path` temp file (CI-safe, portable)
- [x] Schema column name validation test (TC-22) included
- [x] Enum roundtrip test (TC-30) included
- [x] JSON field roundtrip test (TC-18) included
- [x] 9 failure cases documented
- [x] Regression gate: 235 existing + N new tests, all passing
- [x] Tests are `asyncio`-native (`asyncio_mode=auto` in `pytest.ini`)
- [x] No disk files in CI (all tests use `tmp_path` or `:memory:`)
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19
- Notes:
  - TC-26 (deck guard) must be tested: either assertion error or key stripped
  - TC-22 (schema column names) is a direct schema assertion — must run before any integration tests
  - If shared-cache `:memory:` is unstable, `tmp_path`-based restart tests are the fallback

---

## What Is Approved for Implementation

**Implement now:**
- T0: Research — read adapter, memory, models (no files written)
- T1: Fix schema column names (`player_stats`, `chat_messages`, `player_sessions`) + add `aiosqlite` to `requirements.txt`
- T2: Implement `initialize()`, `save_user()`, `get_user()`, `get_user_by_phone()`
- T3: Implement all club methods (`save_club`, `get_club`, `get_club_by_invite`, `get_clubs_for_user`, `save_membership`)
- T4: Implement all table/hand methods (`save_table`, `get_table`, `get_club_table`, `save_hand_summary`, `get_hand_history`)
- T5: Implement snapshot and player session methods
- T6: Implement stats and chat methods
- T7: Wire adapter into `backend/config.py` and `backend/main.py`
- T8: Create `tests/test_sqlite_persistence.py`
- T9: Run tests and verify regression baseline

**Must NOT change during implementation:**
- `backend/persistence/adapter.py` — interface is complete; do not add or remove methods
- `backend/persistence/memory.py` — reference implementation; existing tests depend on it
- `poker_engine/` — zero changes to engine
- `simulation/app_factory.py` — stays on `InMemoryPersistenceAdapter` for CI speed
- All existing test files — must pass without modification
- Any existing gameplay logic in `backend/sessions/session_manager.py`

**Deferred (not in this phase):**
- Live `TableSessionManager` re-hydration from persisted player sessions
- Active hand recovery from game snapshot after crash
- PostgreSQL adapter
- Schema migrations (ALTER TABLE)
- Redis caching layer
- End-to-end integration test with `USE_SQLITE=true` app wiring

---

## Design Questions — Resolved

| # | Question | Answer |
|---|----------|--------|
| 1 | Which entities become durable? | All 8 types the adapter interface defines |
| 2 | Which state remains in-memory? | Live session manager, WebSocket registry, active GameEngine, auth tokens |
| 3 | What exact restart behavior is supported? | User/club/table/hand/stats/snapshot/sessions loadable from fresh adapter instance |
| 4 | Hand history and stats persistence? | HandSummary append-only log; PlayerStats via delta accumulation upsert |
| 5 | Synchronous vs async writes? | All writes synchronous (awaited inline); non-blocking via aiosqlite |
| 6 | Transaction boundaries? | Single transaction for `save_club` + memberships, `upsert_player_stats`; implicit for others |
| 7 | Why SQLite? | Schema exists, aiosqlite, single-process, no infra, clear Postgres migration path |
| 8 | Deferred persistence behaviors? | Game state recovery, session re-hydration, schema migrations |

---

## Final Decision

- [x] **APPROVED — ready to implement**
- [x] **ALL GATES CLEARED — proceed with coding**
- [ ] **BLOCKED — do not implement**

Decision by: Product Manager Agent + Senior Mobile Game Developer Agent + Senior QA Reviewer Agent
Date: 2026-03-19

**GO — proceed with implementation.**

---

## Implementation Status

**COMPLETE — 2026-03-19**

All 10 tasks implemented. Test results:

- `tests/test_sqlite_persistence.py` — **37/37 passed** (3.43 s)
- Full regression — **272/272 passed** (104 s)

### Discovered During Implementation

1. **Schema gap — `chat_messages_table`**: missing `is_system` column. Added.
2. **Schema gap — `player_sessions_table`**: missing `timeout_count` and `disconnect_at`. Added.
3. **Existing test `test_sqlite_adapter_raises_not_implemented`**: tested scaffold's non-functional state. Updated to `test_sqlite_adapter_is_functional` — verifies `get_user()` returns `None` (not `NotImplementedError`) after `initialize()`. One existing test file changed; no other test files modified.

### Files Created
- `tests/test_sqlite_persistence.py` — 37 new tests

### Files Modified
- `backend/persistence/sqlite_adapter.py` — full implementation replacing all `NotImplementedError` stubs; schema fixes
- `backend/config.py` — added `use_sqlite: bool` field
- `backend/main.py` — conditional adapter selection; engine dispose on shutdown
- `tests/test_app_integration.py` — updated one test from `raises_not_implemented` to `is_functional`
