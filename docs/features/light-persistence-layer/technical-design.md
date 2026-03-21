# Technical Design — light-persistence-layer

> Agent: Senior Mobile Game Developer
> Date: 2026-03-19

---

## 1. Persistence Strategy

**Phase strategy: implement the existing scaffold.**

The system already has a clean adapter pattern with:
- `PersistenceAdapter` ABC — all contracts are defined
- `InMemoryPersistenceAdapter` — working reference implementation
- `SqlitePersistenceAdapter` — schema defined, all methods raise `NotImplementedError`

The implementation task is bounded: fill in the `NotImplementedError` stubs in `SqlitePersistenceAdapter`. No new abstractions are needed. No new tables are added. No adapter interface changes are required.

**Why SQLite?**
- Schema is already defined in the scaffold
- `settings.database_url` defaults to `sqlite+aiosqlite:///./poker.db`
- Single-process asyncio backend — no concurrent write contention
- Zero infrastructure overhead (file-based, no server)
- `aiosqlite` enables non-blocking async I/O from the asyncio event loop
- SQLAlchemy Core provides a migration path to Postgres without changing calling code

---

## 2. Schema Corrections Required

The scaffold's `player_stats_table` column names do not match the Python `PlayerStats` dataclass. The Python model is the source of truth.

**Current scaffold (wrong):**
```python
sa.Column("hands_won",       sa.Integer, ...),
sa.Column("total_winnings",  sa.Integer, ...),
sa.Column("biggest_pot",     sa.Integer, ...),
```

**Must become (correct — matches `PlayerStats` dataclass and `StatsDelta`):**
```python
sa.Column("wins",       sa.Integer, nullable=False, default=0),
sa.Column("total_won",  sa.Integer, nullable=False, default=0),
sa.Column("total_lost", sa.Integer, nullable=False, default=0),
```

`StatsDelta` fields map to accumulations:
- `delta.hands_played_delta` → `hands_played += delta.hands_played_delta`
- `delta.wins_delta`         → `wins += delta.wins_delta`
- `delta.chips_won`          → `total_won += delta.chips_won`
- `delta.chips_lost`         → `total_lost += delta.chips_lost`

The `get_leaderboard()` sort key is `total_won DESC` (matching `InMemoryPersistenceAdapter` which sorts by `wins`). The technical design aligns on `wins DESC` as the leaderboard sort — consistent with `memory.py` line 201 which sorts by `s.wins`.

---

## 3. Implementation Detail — Method by Method

### `initialize()`
```python
async def initialize(self) -> None:
    self._engine = create_async_engine(self._database_url, echo=False)
    async with self._engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
```
Called once at app startup. `metadata.create_all` issues `CREATE TABLE IF NOT EXISTS` for all 9 tables. Idempotent.

### Users
- `save_user`: `INSERT OR REPLACE INTO users` with all 4 fields
- `get_user`: `SELECT WHERE id = ?`, return `User(**row._mapping)` or `None`
- `get_user_by_phone`: `SELECT WHERE phone_number = ?`

### Clubs
- `save_club`: Two-step atomic write:
  1. `INSERT OR REPLACE INTO clubs` (5 fields)
  2. For each membership in `club.memberships`: `INSERT OR REPLACE INTO club_memberships`
- `get_club`: Two-query reconstruction:
  1. `SELECT FROM clubs WHERE id = ?` → base `Club` (memberships=[])
  2. `SELECT FROM club_memberships WHERE club_id = ?` → populate `club.memberships`
- `get_club_by_invite`: `SELECT FROM clubs WHERE invite_code = ?`, then reconstruct
- `get_clubs_for_user`: `SELECT club_id FROM club_memberships WHERE user_id = ? AND is_blocked = 0`, then fetch each club
- `save_membership`: `INSERT OR REPLACE INTO club_memberships`

**Note on `save_club` atomicity:** Both the club row and all membership rows are written inside a single `async with self._engine.begin() as conn` context (auto-commit on exit, rollback on exception).

### Tables
- `save_table`: Serialize `TableConfig` to JSON, `INSERT OR REPLACE INTO tables`
  ```python
  config_json = json.dumps({
      "starting_stack": table.config.starting_stack,
      "small_blind": table.config.small_blind,
      "big_blind": table.config.big_blind,
      "turn_timer_seconds": table.config.turn_timer_seconds,
  })
  ```
- `get_table`: Deserialize config_json → `TableConfig(**json.loads(row.config_json))` → `TableRecord`
- `get_club_table`: `SELECT WHERE club_id = ? AND is_active = 1 LIMIT 1`
- `save_hand_summary`: `INSERT INTO hand_summaries` — JSON-serialize all list/dict fields
- `get_hand_history`: `SELECT WHERE table_id = ? ORDER BY timestamp ASC LIMIT ?` → reconstruct `HandSummary` list

**Hand history order**: Return in ascending timestamp order (oldest first), consistent with `InMemoryPersistenceAdapter` which returns `history[-limit:]` (chronological).

### Game Snapshots
- `save_game_state_snapshot`: Assert `"deck"` not in snapshot; `INSERT OR REPLACE INTO game_snapshots`
- `load_game_state_snapshot`: `SELECT snapshot_json WHERE table_id = ?`, `json.loads()`

### Player Sessions
- `save_player_session`: `INSERT OR REPLACE INTO player_sessions` — map `PlayerSession` fields: `user_id`, `display_name`, `seat_index`, `stack`, `status.value`, `is_connected`
- `load_player_sessions`: `SELECT WHERE table_id = ?` → reconstruct `PlayerSession` list
- `delete_player_session`: `DELETE WHERE table_id = ? AND user_id = ?`

**`PlayerSession` reconstruction**: `PlayerSession` is a dataclass from `poker_engine.engine.models`. Fields: `user_id`, `display_name`, `seat_index`, `stack`, `status` (PlayerStatus enum), `is_connected`. The `status` column stores `status.value` (string); reconstruction uses `PlayerStatus(row.status)`.

### Stats
- `upsert_player_stats`:
  ```sql
  INSERT OR IGNORE INTO player_stats (club_id, user_id, display_name, hands_played, wins, total_won, total_lost)
  VALUES (?, ?, ?, 0, 0, 0, 0)
  ```
  Then:
  ```sql
  UPDATE player_stats
  SET display_name = ?,
      hands_played = hands_played + ?,
      wins         = wins + ?,
      total_won    = total_won + ?,
      total_lost   = total_lost + ?
  WHERE club_id = ? AND user_id = ?
  ```
  Both in one transaction. The two-statement approach avoids read-modify-write races (though not relevant in single-process asyncio).
- `get_player_stats`: `SELECT WHERE club_id = ? AND user_id = ?` → `PlayerStats(**row._mapping)`
- `get_leaderboard`: `SELECT WHERE club_id = ? ORDER BY wins DESC LIMIT ?`

### Chat
- `save_chat_message`: `INSERT INTO chat_messages`
- `get_chat_history`: `SELECT WHERE table_id = ? ORDER BY timestamp ASC LIMIT ?`

---

## 4. Synchronous vs Asynchronous Writes

All writes in this phase are **synchronous** (awaited inline). The asyncio event loop cooperatively yields during DB I/O via `aiosqlite`, so there is no blocking of other coroutines. Fire-and-forget was the pattern for `save_chat_message` in `SessionManager` — this is acceptable to keep as-is since the write is still non-blocking.

No background write queue, no write-ahead log, no batch flushing. The volume is low (one DB write per user action), and SQLite's WAL mode is not required for this phase.

---

## 5. Transaction Boundaries

| Operation | Transaction boundary |
|-----------|---------------------|
| `save_user` | Single INSERT OR REPLACE — implicit autocommit |
| `save_club` | Single transaction: club row + all membership rows |
| `save_membership` | Single INSERT OR REPLACE — implicit |
| `save_table` | Single INSERT OR REPLACE |
| `save_hand_summary` | Single INSERT |
| `upsert_player_stats` | Single transaction: INSERT OR IGNORE + UPDATE |
| `save_game_state_snapshot` | Single INSERT OR REPLACE |
| `save_player_session` | Single INSERT OR REPLACE |
| All reads | Single connection, no transaction needed |

**Pattern**: Use `async with self._engine.begin() as conn` for multi-statement transactions; `async with self._engine.connect() as conn` + `await conn.execute(...)` for single-statement reads/writes (autocommit via `begin()`).

---

## 6. App Wiring

### `backend/config.py`
Add one new field to `Settings`:
```python
use_sqlite: bool = Field(False, alias="USE_SQLITE")
```

### `backend/main.py` — lifespan
Replace:
```python
persistence = InMemoryPersistenceAdapter()
```
With:
```python
if settings.use_sqlite:
    persistence = SqlitePersistenceAdapter(settings.database_url)
    await persistence.initialize()
else:
    persistence = InMemoryPersistenceAdapter()
```

This preserves the existing in-memory default. `USE_SQLITE=true` activates SQLite for production-like runs.

### `simulation/app_factory.py`
**No change.** The simulation factory uses `create_app()` which defaults to `InMemoryPersistenceAdapter`. All simulation and integration tests remain unaffected.

---

## 7. Startup/Bootstrap Loading Behaviour

The SQLite adapter has **no startup loading phase**. Each query reads from the DB on demand. There is no in-memory cache to warm.

This is correct for this phase: the system reads from SQLite on each request. Caching is deferred.

`initialize()` only runs DDL (`CREATE TABLE IF NOT EXISTS`). It does not load any rows into memory.

---

## 8. What Persists vs What Remains In-Memory

| Data | Persisted to SQLite | In-Memory Only |
|------|--------------------|-|
| Users | YES | — |
| Clubs + Memberships | YES | — |
| TableRecord + TableConfig | YES | — |
| HandSummary | YES | — |
| PlayerStats | YES | — |
| GameStateSnapshot | YES | — |
| PlayerSession (seat/stack at hand boundaries) | YES | — |
| ChatMessage | YES | — |
| Live `TableSessionManager` state (active hands, WebSocket connections, timers) | — | IN-MEMORY ONLY |
| Active `GameEngine` instance (deck, hand in progress) | — | IN-MEMORY ONLY — deck never persisted |
| WebSocket connection registry | — | IN-MEMORY ONLY |
| JWT/auth tokens | — | IN-MEMORY ONLY (stateless JWT) |

---

## 9. Engine Isolation

**Zero changes to `poker_engine/`.** The persistence layer sits entirely in `backend/persistence/`. The engine communicates via the adapter only through `SessionManager`, which calls adapter methods with already-serializable data. No engine object is passed raw to the adapter; the `SessionManager` is responsible for mapping engine state to adapter-friendly types before calling persistence methods.

---

## 10. Migration Path to Stronger Persistence

The adapter pattern makes future migration straightforward:
1. Add `PostgresPersistenceAdapter(database_url)` implementing `PersistenceAdapter`
2. Change one line in `main.py` lifespan
3. No calling code changes anywhere in the backend

For schema evolution, a lightweight migration tool (e.g. `alembic` or manual versioned DDL scripts) can be added later. For this phase, `CREATE TABLE IF NOT EXISTS` is sufficient.

---

## 11. Dependencies to Add

| Package | Reason |
|---------|--------|
| `aiosqlite` | Async SQLite driver for `sqlite+aiosqlite://` |
| `sqlalchemy[asyncio]` | Already used in scaffold; confirm in requirements.txt |

Check `requirements.txt` and add both if not present.

---

## 12. Files to Create or Modify

| File | Action |
|------|--------|
| `backend/persistence/sqlite_adapter.py` | Implement all methods; fix `player_stats` schema columns |
| `backend/config.py` | Add `use_sqlite: bool` field |
| `backend/main.py` | Conditional adapter selection in lifespan |
| `requirements.txt` | Add `aiosqlite` if missing |
| `tests/test_sqlite_persistence.py` | New — restart-safety tests using `:memory:` |

**Must NOT change:**
- `backend/persistence/adapter.py` (interface is complete)
- `backend/persistence/memory.py` (reference implementation; existing tests depend on it)
- `simulation/app_factory.py`
- `poker_engine/` (zero changes)
- All existing test files
