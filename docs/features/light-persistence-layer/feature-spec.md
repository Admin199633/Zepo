# Feature Spec — light-persistence-layer

> Agent: Product Manager
> Date: 2026-03-19

---

## Feature Goal

Move the backend from purely in-memory state to a durable, restart-safe persistence layer for core product entities and basic gameplay records.

This is **not** a full production architecture build-out. It is the minimum persistence investment needed to make the system behave like a real product: user accounts, clubs, table configurations, hand records, and stats survive a server restart.

---

## Problem Statement

The backend currently uses `InMemoryPersistenceAdapter` for all state. Every restart wipes all users, clubs, memberships, tables, hand history, and stats. This is acceptable for gameplay simulation and CI, but it prevents the system from functioning as a real product — a user cannot register, rejoin their club, or review their history after a server restart.

The system already has:
- A complete `PersistenceAdapter` ABC defining every required contract
- A fully-working `InMemoryPersistenceAdapter` used for tests and development
- A `SqlitePersistenceAdapter` scaffold with the full SQLAlchemy Core schema defined but all methods raising `NotImplementedError`
- `settings.database_url` defaulting to `sqlite+aiosqlite:///./poker.db`
- `main.py` hardcoded to instantiate `InMemoryPersistenceAdapter`

The work is bounded: implement the SQLite adapter, wire it into the app, and validate restart safety with tests.

---

## Scope

### In Scope

1. **Implement `SqlitePersistenceAdapter`** — fill all `NotImplementedError` stubs using the SQLAlchemy Core schema already defined in the scaffold.
2. **Fix schema/model discrepancy** — the scaffold's `player_stats` table uses `hands_won`, `total_winnings`, `biggest_pot` but the Python `PlayerStats` model uses `wins`, `total_won`, `total_lost`. Align the schema to the Python model.
3. **Wire the adapter into `main.py`** — add a `USE_SQLITE` setting to `Settings`; when `True`, instantiate `SqlitePersistenceAdapter` instead of `InMemoryPersistenceAdapter`.
4. **Startup/bootstrap behaviour** — `initialize()` runs `CREATE TABLE IF NOT EXISTS` at app startup.
5. **Test restart safety** — new `tests/test_sqlite_persistence.py` proving all entity types survive an adapter restart using SQLite `:memory:` shared connections.
6. **Keep existing tests unchanged** — all existing tests continue using `InMemoryPersistenceAdapter`; no existing test file is modified.

### Out of Scope

- Game state recovery after mid-hand crash (snapshot persists, but active hand reconstruction is deferred)
- Player session recovery after crash (player sessions persist, but live session re-hydration into `TableSessionManager` is deferred)
- Chat history durability guarantees (chat persists via the adapter but is not part of restart assertions)
- Multi-table support, multi-process safety, connection pooling
- PostgreSQL or any adapter other than SQLite
- Schema migrations (this phase uses `CREATE TABLE IF NOT EXISTS`; ALTER TABLE is deferred)
- Analytics queries, aggregation pipelines, or reporting
- Any new gameplay features or poker rule changes

---

## Entities — Durable vs In-Memory

| Entity | Durable in This Phase | Notes |
|--------|----------------------|-------|
| `User` | YES | Core identity; survives restart |
| `Club` | YES | Core product entity |
| `ClubMembership` | YES | Part of `save_club` / `save_membership` |
| `TableRecord` + `TableConfig` | YES | Config must survive restart |
| `HandSummary` | YES | Immutable record; append-only |
| `PlayerStats` | YES | Accumulated per club/player |
| `GameStateSnapshot` | YES (persisted) | Write path implemented; active hand recovery deferred |
| `PlayerSession` | YES (persisted) | Write path implemented; live session re-hydration deferred |
| `ChatMessage` | YES (persisted) | Write path implemented; no restart assertion required |

---

## Restart Behavior — In Scope vs Deferred

### In scope (must work after restart)
- `get_user_by_phone()` returns the correct user
- `get_club()` / `get_club_by_invite()` return the club with its memberships
- `get_clubs_for_user()` returns all clubs the user belongs to
- `get_table()` / `get_club_table()` return the table with its config
- `get_hand_history()` returns all saved summaries for a table
- `get_player_stats()` / `get_leaderboard()` return persisted stats

### Deferred (not in scope for this phase)
- Re-hydrating an active `TableSessionManager` from persisted sessions
- Resuming a hand in progress from a game snapshot
- Replaying chat history into live WebSocket sessions on connect

---

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | `SqlitePersistenceAdapter.initialize()` creates all tables without error |
| AC-02 | A `User` saved via `save_user()` is retrievable by ID and by phone after adapter re-creation |
| AC-03 | A `Club` with memberships saved via `save_club()` + `save_membership()` is retrievable after adapter re-creation |
| AC-04 | A `TableRecord` saved via `save_table()` is retrievable by table ID and by club ID after adapter re-creation |
| AC-05 | `HandSummary` records saved via `save_hand_summary()` are returned by `get_hand_history()` in order, after adapter re-creation |
| AC-06 | `PlayerStats` accumulated via `upsert_player_stats()` (multiple deltas) are correct after adapter re-creation |
| AC-07 | `GameStateSnapshot` saved via `save_game_state_snapshot()` is loadable after adapter re-creation |
| AC-08 | `PlayerSession` saved via `save_player_session()` is returned by `load_player_sessions()` after adapter re-creation |
| AC-09 | `delete_player_session()` removes the session; subsequent `load_player_sessions()` does not include it |
| AC-10 | `main.py` uses `SqlitePersistenceAdapter` when `USE_SQLITE=true` and `InMemoryPersistenceAdapter` otherwise |
| AC-11 | All existing tests continue to pass without modification |
| AC-12 | SQLite persistence tests run in CI using `:memory:` database (no disk file created in CI) |
| AC-13 | The `player_stats` schema columns match Python `PlayerStats` fields (`wins`, `total_won`, `total_lost`) |

---

## Dependencies

- `sqlalchemy[asyncio]` (already in scaffold imports — confirm in `requirements.txt`)
- `aiosqlite` (needed for `sqlite+aiosqlite://` URLs)
- No new domain models required
- No changes to `poker_engine/`

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Schema/model field mismatch causes silent wrong values | High (already identified) | Explicitly fix in technical design; add assertion test for field alignment |
| Existing tests break if `InMemoryPersistenceAdapter` is no longer the default | Medium | Keep `InMemoryPersistenceAdapter` as default; `USE_SQLITE` opt-in |
| Shared SQLite file in CI creates cross-test pollution | Medium | All tests use `sqlite+aiosqlite:///:memory:` |
| `aiosqlite` not installed | Low | Add to `requirements.txt` |
| Concurrent write contention | Low (single-process asyncio) | Single asyncio event loop; no thread safety needed |
| `BETWEEN_HANDS_DELAY` timing interacts with persistence tests | Low | Persistence tests do not use the full app wiring |

---

## Open Questions (Resolved)

1. **Which adapter for CI?** `InMemoryPersistenceAdapter` for all existing tests; `SqlitePersistenceAdapter(":memory:")` for new persistence-specific tests.
2. **Schema migrations?** Deferred — use `CREATE TABLE IF NOT EXISTS` for now.
3. **PostgreSQL?** Deferred; SQLite is sufficient for this phase.
4. **Should `main.py` default to SQLite?** No — default remains in-memory; opt-in via `USE_SQLITE=true` to prevent breaking dev/CI flows.
5. **Game state recovery in scope?** Snapshot write path is in scope; live game re-hydration is deferred.
