# QA Test Plan — light-persistence-layer

> Agent: Senior QA Reviewer
> Date: 2026-03-19

---

## Test Scope

New file: `tests/test_sqlite_persistence.py`

This file tests `SqlitePersistenceAdapter` in isolation using `sqlite+aiosqlite:///:memory:`. No app wiring, no HTTP, no WebSockets. Pure adapter contract tests.

**All existing tests must continue to pass without modification.** This is a non-negotiable regression gate (AC-11).

---

## Test Infrastructure Design

### Shared fixture
```python
@pytest.fixture
async def db() -> SqlitePersistenceAdapter:
    adapter = SqlitePersistenceAdapter("sqlite+aiosqlite:///:memory:")
    await adapter.initialize()
    yield adapter
    await adapter._engine.dispose()
```

### Restart simulation pattern
"Restart" means: create a second adapter instance pointing to the same database. For `:memory:` databases in SQLite, a named shared-cache connection string is required to share state between two engine instances:
```
sqlite+aiosqlite:///file::memory:?cache=shared&uri=true
```
Each restart test creates `db1` (saves data), then creates `db2` (same URL), calls `db2.initialize()`, reads data from `db2`, and asserts it matches.

This is the canonical CI-safe restart simulation for SQLite — no disk files, full restart semantics.

---

## Test Cases

### TC-01: Initialize — Idempotent DDL
**AC-01**
- Call `adapter.initialize()` twice on the same engine
- No exception raised; all tables exist after second call

### TC-02: User Save and Retrieve by ID
**AC-02**
- Save a `User`, retrieve by `user_id`
- Assert all fields match: `id`, `phone_number`, `display_name`, `created_at`

### TC-03: User Retrieve by Phone
**AC-02**
- Save a `User`, retrieve by `phone_number`
- Assert returned user's `id` matches

### TC-04: User — Nonexistent Returns None
- `get_user("no-such-id")` returns `None`
- `get_user_by_phone("+99999")` returns `None`

### TC-05: User Overwrite (Upsert)
- Save same user_id twice with different `display_name`
- Retrieve — `display_name` reflects the second write

### TC-06: User Restart Safety
**AC-02**
- `db1.save_user(alice)` → `db2.get_user("u1")` returns alice
- `db2.get_user_by_phone(alice.phone_number)` returns alice

### TC-07: Club Save and Retrieve
**AC-03**
- Save a `Club` with 2 memberships via `save_club()`
- Retrieve via `get_club()` — assert `id`, `name`, `owner_id`, `invite_code`, `len(memberships) == 2`

### TC-08: Club Retrieve by Invite Code
**AC-03**
- `get_club_by_invite(invite_code)` returns the club

### TC-09: Club Memberships — Upsert
- Add a membership via `save_membership()` for a user not already in the club
- `get_club()` includes the new membership

### TC-10: Club Membership — Block Flag
- Save membership with `is_blocked=True`
- `get_clubs_for_user()` does NOT include this club for the blocked user

### TC-11: Club — `get_clubs_for_user`
- User is member of 2 clubs → `get_clubs_for_user()` returns both
- User is blocked from 1 → returns only the unblocked club

### TC-12: Club Restart Safety
**AC-03**
- `db1.save_club(club)` + `db1.save_membership(extra_member)`
- `db2.get_club(club.id)` — all memberships present
- `db2.get_club_by_invite(club.invite_code)` — returns club
- `db2.get_clubs_for_user(member_user_id)` — returns the club

### TC-13: Table Save and Retrieve by ID
**AC-04**
- Save `TableRecord` with a `TableConfig`
- Retrieve by `table_id` — assert `config.starting_stack`, `config.small_blind`, `config.big_blind`, `config.turn_timer_seconds`

### TC-14: Table Retrieve by Club
**AC-04**
- `get_club_table(club_id)` returns the active table

### TC-15: Table Restart Safety
**AC-04**
- `db1.save_table(table)` → `db2.get_table(table_id)` — full config reconstructed correctly

### TC-16: Hand History — Save and Retrieve
**AC-05**
- Save 3 `HandSummary` records for the same table
- `get_hand_history(table_id)` returns all 3 in chronological order

### TC-17: Hand History — Limit
- Save 60 summaries; `get_hand_history(limit=50)` returns exactly 50

### TC-18: Hand History — JSON Fields Roundtrip
- `winner_ids`, `player_ids`, `stacks_before`, `stacks_after`, `community_cards` survive save/load with correct types (list, dict)

### TC-19: Hand History Restart Safety
**AC-05**
- `db1.save_hand_summary(summary)` → `db2.get_hand_history(table_id)` — returns the summary with correct fields

### TC-20: Stats — Initial Accumulation
**AC-06**
- `upsert_player_stats(club_id, user_id, name, delta1)` where `delta1 = StatsDelta(hands_played_delta=1, wins_delta=1, chips_won=500, chips_lost=0)`
- `get_player_stats()` returns `hands_played=1, wins=1, total_won=500, total_lost=0`

### TC-21: Stats — Cumulative Accumulation
**AC-06**
- Apply 3 deltas; assert totals are sum of all deltas

### TC-22: Stats — Schema Column Alignment
**AC-13**
- Directly assert that `player_stats_table.c` contains columns named `wins`, `total_won`, `total_lost`
- Assert it does NOT contain `hands_won`, `total_winnings`, `biggest_pot`

### TC-23: Stats Restart Safety
**AC-06**
- `db1.upsert_player_stats(...)` twice → `db2.get_player_stats()` returns correct cumulative values

### TC-24: Leaderboard Order
- 3 players with different `wins`; `get_leaderboard()` returns them sorted `wins DESC`

### TC-25: Game Snapshot Save and Load
**AC-07**
- Save a snapshot dict; `load_game_state_snapshot()` returns the same dict (deep equality)

### TC-26: Game Snapshot — Deck Guard
- Attempt to save a snapshot containing a `"deck"` key
- Either an `AssertionError` is raised, or the deck key is stripped — must not be loadable

### TC-27: Game Snapshot Restart Safety
**AC-07**
- `db1.save_game_state_snapshot(table_id, snap)` → `db2.load_game_state_snapshot(table_id)` returns snap

### TC-28: Player Session Save and Load
**AC-08**
- Save 2 `PlayerSession` objects for same table
- `load_player_sessions()` returns both; `user_id`, `seat_index`, `stack`, `status`, `is_connected` are correct

### TC-29: Player Session Delete
**AC-09**
- Save 2 sessions; delete one; `load_player_sessions()` returns only the remaining session

### TC-30: Player Session — Status Enum Roundtrip
- Save a session with `status=PlayerStatus.SITTING_OUT`; reload and assert `status == PlayerStatus.SITTING_OUT` (enum reconstruction is correct)

### TC-31: Player Session Restart Safety
**AC-08**
- `db1.save_player_session(table_id, session)` → `db2.load_player_sessions(table_id)` returns the session

### TC-32: Chat Save and Retrieve
- Save 5 chat messages; `get_chat_history()` returns all 5 in chronological order

### TC-33: Chat History Limit
- Save 60 messages; `get_chat_history(limit=50)` returns exactly 50

---

## Regression Tests

### TR-01: Existing persistence tests still pass
- Run `tests/test_persistence.py` — all tests pass (unchanged)
- These test `InMemoryPersistenceAdapter` which is untouched

### TR-02: Integration tests still pass
- Run `tests/test_app_integration.py` — all tests pass
- The integration test fixture uses `InMemoryPersistenceAdapter` (default)

### TR-03: Simulation tests still pass
- Run `tests/test_gameplay_scenarios.py` — all 6 tests pass
- `simulation/app_factory.py` is unchanged; uses in-memory

### TR-04: Full regression baseline
- Total test count: 235 (existing) + new SQLite tests = 235 + N
- All 235 + N must pass

---

## Failure Cases and Risks

### F-01: Schema column name mismatch (High risk)
**Scenario**: `player_stats_table` retains old column names (`hands_won`, etc.); `upsert_player_stats` fails or stores in wrong columns.
**Detection**: TC-22 asserts column names directly; TC-20/21 would fail on wrong values.

### F-02: `ClubMembership` not reconstructed on `get_club` (Medium)
**Scenario**: `save_club` saves memberships, but `get_club` only queries the clubs table without joining memberships.
**Detection**: TC-07 asserts `len(memberships) == 2`.

### F-03: `TableConfig` JSON roundtrip loses fields (Medium)
**Scenario**: `save_table` serializes only some `TableConfig` fields; `get_table` returns config with defaults for the missing fields.
**Detection**: TC-13 checks all 4 `TableConfig` fields explicitly.

### F-04: Hand history order — wrong sort (Low)
**Scenario**: `get_hand_history` returns newest-first instead of oldest-first.
**Detection**: TC-16 saves summaries with explicit timestamps and checks order.

### F-05: PlayerSession `status` enum not reconstructed (Medium)
**Scenario**: `status` stored as string but reconstructed as string, not `PlayerStatus` enum.
**Detection**: TC-30 checks `session.status == PlayerStatus.SITTING_OUT` (not just a string).

### F-06: Restart with shared-cache `:memory:` not supported (Medium)
**Scenario**: Two adapter instances with `file::memory:?cache=shared&uri=true` do not share data in all aiosqlite versions.
**Detection**: TC-06/12/19 fail. If this occurs, restart tests must use a `tmp_path` temp file instead (pytest `tmp_path` fixture provides a unique temp directory).
**Mitigation**: Use `tmp_path` as the fallback restart simulation approach. Both approaches are CI-safe (no persistent disk state).

### F-07: `aiosqlite` not installed (Low)
**Scenario**: Import fails at test collection.
**Detection**: Immediate `ImportError` / collection failure.
**Mitigation**: Add `aiosqlite` to `requirements.txt` explicitly.

### F-08: `save_club` not atomic — partial writes on exception (Low for this phase)
**Scenario**: Club row written but memberships not written if an exception occurs mid-loop.
**Detection**: TC-12 would pass even with partial writes (no exception injected).
**Mitigation**: `save_club` uses a single `async with self._engine.begin()` transaction (per technical design). This is verified indirectly by TC-12.

### F-09: Stats leaderboard sort key mismatch with `InMemoryPersistenceAdapter` (Low)
**Scenario**: `memory.py` sorts by `s.wins`; SQLite sorts by `wins DESC` — these should be equivalent. If column was renamed differently, they'd diverge.
**Detection**: TC-24 checks order explicitly.

---

## What This Feature Proves vs Does Not Prove

### Proves
- All core entity types survive an adapter-level restart
- All write/read contracts are correctly implemented for SQLite
- The `player_stats` schema is correctly aligned with the Python model
- Enum values roundtrip through the DB correctly
- JSON list/dict fields survive serialization

### Does NOT Prove
- Live `TableSessionManager` can be reconstructed from persisted sessions after a real server restart
- Active hand state can be recovered mid-hand after a crash
- The app works correctly end-to-end with `USE_SQLITE=true` (integration test with SQLite wiring is deferred)
- Performance or concurrency under load
- Schema migration safety

---

## CI Constraints

- All new tests use `sqlite+aiosqlite:///:memory:` (or shared-cache equivalent) — no disk files
- Test isolation: each test fixture creates a fresh adapter instance
- No `time.sleep()` or timer-dependent assertions
- New tests must be marked `asyncio` (use `pytest-asyncio` with `asyncio_mode=auto` already configured in `pytest.ini`)
