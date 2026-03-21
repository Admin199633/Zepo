# QA Test Plan — connection-resilience-and-session-recovery

> Agent: Senior QA Reviewer
> Date: 2026-03-19

---

## Regression Baseline

Current passing count: **272/272**. All 272 must continue passing after this feature. No existing test files may be modified except `tests/test_simulation_scenarios.py` (adding one test).

---

## New Test File: `tests/test_connection_resilience.py`

All tests use `disconnect_reserve_seconds=0.05` on the manager under test (directly constructed, not via registry). This keeps timing reliable: `await asyncio.sleep(0.2)` is safe wait; tests complete in <1s each.

---

## Test Cases

### TC-01 — AC-01: Fresh disconnect starts timer and broadcasts `PLAYER_STATUS{disconnected}`

**Setup**: Manager with `disconnect_reserve_seconds=0.05`, one connected player.
**Action**: Call `manager.disconnect(user_id)`.
**Assert**:
- Broadcast spy received exactly one `PLAYER_STATUS` event with `status="disconnected"`.
- `reserve_until` in the payload is between `time.time() + 0.04` and `time.time() + 0.06` (i.e., approximately `now + 0.05`).
- `player.is_connected == False`.
- `player.disconnect_at` is set and close to `time.time()`.
- One disconnect task is active in `manager._disconnect_tasks[user_id]`.

---

### TC-02 — AC-02: Double-disconnect does NOT reset the timer

**Setup**: Manager with `disconnect_reserve_seconds=0.05`, one connected player.
**Action**:
1. Call `manager.disconnect(user_id)` — records `disconnect_at_first = player.disconnect_at` and captures task reference `task_first`.
2. Wait 0.01s.
3. Call `manager.disconnect(user_id)` again.
**Assert**:
- `player.disconnect_at` is still equal to `disconnect_at_first` (not reset).
- Task in `_disconnect_tasks[user_id]` is the same object as `task_first` (not a new task).
- Broadcast spy received exactly one `PLAYER_STATUS` event total (the second disconnect produced no event).
- `player.is_connected == False` (still disconnected).

---

### TC-03 — AC-02: Double-disconnect cannot extend the reserve window (timer fires on original schedule)

**Setup**: Manager with `disconnect_reserve_seconds=0.05`.
**Action**:
1. `disconnect(user_id)` at t=0.
2. `disconnect(user_id)` at t=0.03 (before timer fires).
3. `await asyncio.sleep(0.15)` — well past the original 0.05s timer.
**Assert**:
- Player status is `SIT_OUT` (timer fired on original schedule, not reset).
- `player.is_connected == False`.
- Broadcast spy received `PLAYER_STATUS{status="sit_out"}` — timer fired.

---

### TC-04 — AC-03: Reconnect within reserve window restores connection

**Setup**: Manager with `disconnect_reserve_seconds=0.5`, two players (owner + joiner). A hand is in progress.
**Action**:
1. `disconnect(owner_id)`.
2. Immediately call `join_as_player(owner_id, ...)` (reconnect within window).
**Assert**:
- Returns `ReconnectResult(success=True, role="player")`.
- `player.is_connected == True`.
- `player.disconnect_at == None`.
- Broadcast spy received `PLAYER_STATUS{status=<active_status>}` — not "disconnected".
- `owner_id` not in `manager._disconnect_tasks` (timer cancelled).

---

### TC-05 — AC-03: Reconnect within window sends STATE_SNAPSHOT

**Setup**: Manager with `disconnect_reserve_seconds=0.5`, one player, snapshot broadcast spy.
**Action**: `disconnect(user_id)` then `join_as_player(user_id, ...)`.
**Assert**:
- Broadcast spy for the reconnecting player received a `STATE_SNAPSHOT` event.
- Snapshot `table_id` matches.
- Snapshot contains `players` dict with `user_id` present.
- Snapshot shows player's `stack`, `seat_index`, current `status`.

---

### TC-06 — AC-04: Reconnect after reserve expiry succeeds with `SIT_OUT` status

**Setup**: Manager with `disconnect_reserve_seconds=0.05`, one player.
**Action**:
1. `disconnect(user_id)`.
2. `await asyncio.sleep(0.2)` — timer fires, player is forced to `SIT_OUT`.
3. Call `join_as_player(user_id, ...)`.
**Assert**:
- Returns `ReconnectResult(success=True, role="player")`.
- `player.is_connected == True`.
- `player.status == PlayerStatus.SIT_OUT`.
- Broadcast spy received `PLAYER_STATUS{status="sit_out"}` on reconnect (not "active").
- `STATE_SNAPSHOT` sent to reconnecting player.

---

### TC-07 — AC-04: STATE_SNAPSHOT after expiry-reconnect shows SIT_OUT

**Setup**: As TC-06.
**Action**: Same sequence. Capture the `STATE_SNAPSHOT` broadcast.
**Assert**:
- Player entry in snapshot has `status == "sit_out"`.
- Snapshot does not contain hole cards (player is sitting out, no active hand).

---

### TC-08 — AC-04: Player must call SIT_IN after expiry-reconnect to rejoin game flow

**Setup**: As TC-06. After reconnect, player status is `SIT_OUT`.
**Action**: Player sends `SIT_IN` action.
**Assert**:
- Player status transitions to `PlayerStatus.WAITING`.
- Broadcast spy receives `PLAYER_STATUS{status="waiting"}`.

---

### TC-09 — AC-05: `disconnect_reserve_seconds` constructor param overrides module constant

**Setup**: Create two managers — one with default (no param), one with `disconnect_reserve_seconds=0.05`.
**Assert**:
- Default manager: `manager._disconnect_reserve_seconds == DISCONNECT_RESERVE_SECONDS` (60).
- Parameterized manager: `manager._disconnect_reserve_seconds == 0.05`.

---

### TC-10 — AC-05: Module-level constant still works as fallback for patched tests

**Setup**: Patch `session_manager.DISCONNECT_RESERVE_SECONDS = 0.05`. Create manager with no `disconnect_reserve_seconds` param.
**Assert**:
- `manager._disconnect_reserve_seconds == 0.05` (picked up the patched constant).

---

### TC-11 — AC-10: `reserve_until` in disconnect broadcast is accurate

**Setup**: Manager with `disconnect_reserve_seconds=1`, one player.
**Action**: `disconnect(user_id)` at time `t0`.
**Assert**:
- Captured broadcast `PLAYER_STATUS` payload has `reserve_until` field.
- `t0 + 0.99 < payload.reserve_until < t0 + 1.01`.

---

### TC-12 — AC-07: SYNC_REQUEST delivers STATE_SNAPSHOT to the requesting player

**Setup**: Manager with one connected player who has joined.
**Action**: Player sends `SYNC_REQUEST` message (calls `send_sync(user_id)`).
**Assert**:
- Broadcast spy for that player received a `STATE_SNAPSHOT` event.
- No broadcast to other players.
- Snapshot `table_id` is correct.

---

### TC-13 — AC-07: SYNC_REQUEST from unknown/disconnected user

**Setup**: Manager with one connected player.
**Action**: Call `send_sync("unknown_user_id")`.
**Assert**:
- No exception raised.
- No snapshot broadcast (or, if the method silently no-ops for unknowns, assertion depends on implementation — must not crash).

---

### TC-14: Disconnect during active hand — timer fires → auto-fold + SIT_OUT

**Setup**: Manager with `disconnect_reserve_seconds=0.05`, two players, hand in progress, it's `user_A`'s turn.
**Action**: `disconnect(user_A_id)`.
**Wait**: `await asyncio.sleep(0.2)` — timer fires.
**Assert**:
- `user_A.status == SIT_OUT`.
- Broadcast includes `PLAYER_STATUS{status="sit_out"}` for user_A.
- The hand advanced (auto-fold occurred): user_A's turn is no longer current.
- user_B received appropriate events.

---

### TC-15: Disconnect between hands — timer fires → SIT_OUT only (no auto-fold)

**Setup**: Manager with `disconnect_reserve_seconds=0.05`, two players, NO hand in progress (idle state).
**Action**: `disconnect(user_A_id)`.
**Wait**: `await asyncio.sleep(0.2)`.
**Assert**:
- `user_A.status == SIT_OUT`.
- No PLAYER_ACTED broadcast (no hand was in progress to fold).
- Table remains in idle/waiting state.

---

### TC-16: Duplicate reconnect attempts are safe (idempotent)

**Setup**: Manager with `disconnect_reserve_seconds=0.5`, one disconnected player.
**Action**: Call `join_as_player(user_id, ...)` twice in rapid succession (both within reserve window).
**Assert**:
- No exception raised on either call.
- Both return `ReconnectResult(success=True)`.
- `player.is_connected == True`.
- Two `STATE_SNAPSHOT` events sent (second one is redundant but correct).
- No ghost state — only one entry in `_disconnect_tasks` (cleared or absent).

---

### TC-17: Spectator disconnect is immediate (no reserve timer)

**Setup**: Manager with one connected spectator.
**Action**: `disconnect(spectator_user_id)`.
**Assert**:
- Spectator removed from `_spectators`.
- No disconnect task created (spectators do not get a reserve window).
- No `PLAYER_STATUS` broadcast for the spectator's disconnect (or if broadcast, it has no `reserve_until`).

---

### TC-18: Full lifecycle — join → disconnect → expiry → reconnect → SIT_OUT → sit_in → WAITING

**Setup**: Manager with `disconnect_reserve_seconds=0.05`, two players.
**Sequence**:
1. Both players join (`ACTIVE`).
2. `disconnect(player_A)` → `PLAYER_STATUS{disconnected}` broadcast.
3. `await asyncio.sleep(0.15)` → timer fires → `PLAYER_STATUS{sit_out}` broadcast.
4. `join_as_player(player_A)` → reconnects → `PLAYER_STATUS{sit_out}` + `STATE_SNAPSHOT`.
5. `SIT_IN` → `PLAYER_STATUS{waiting}`.
**Assert** at each step:
- Status transitions are correct: `ACTIVE → disconnected(transport) → SIT_OUT → SIT_OUT(reconnected) → WAITING`.
- `disconnect_at` is `None` after reconnect.
- Timer is not present after reconnect.
- `STATE_SNAPSHOT` was received on reconnect.

---

### TC-19: `_disconnect_reserve_seconds` used in both `disconnect()` and `_run_disconnect_timer()`

**Setup**: Manager with `disconnect_reserve_seconds=2`.
**Assert** (by inspecting the manager):
- `disconnect()` computes `reserve_until = time.time() + 2`.
- `_run_disconnect_timer` uses `asyncio.sleep(2)` (indirectly verifiable by checking the manager attribute equals 2, and the timer takes ~2s to fire).

---

## Simulation Test: `tests/test_simulation_scenarios.py`

### TC-S7 — AC-08: S7 simulation — reserve expiry, table continues, player rejoins as SIT_OUT

**File**: `simulation/scenarios/s7_disconnect_reserve_expiry.py`
**Test in**: `tests/test_simulation_scenarios.py` as `test_s7_disconnect_reserve_expiry`

**Scenario**:
1. 2 players connect via `make_test_client`.
2. Both send `JOIN_TABLE{role=player}`, receive `STATE_SNAPSHOT`.
3. Owner's manager is located via `app.state.registry._sessions[table_id]`.
4. Patch: `manager._disconnect_reserve_seconds = 0.1`.
5. Both send `START_HAND` / wait for `BLINDS_POSTED`.
6. Owner disconnects (WS close).
7. Joiner receives `PLAYER_STATUS{status="disconnected", reserve_until=...}`.
8. `await asyncio.sleep(0.3)` — timer fires.
9. Joiner receives `PLAYER_STATUS{status="sit_out"}`.
10. Owner reconnects (new WS + `JOIN_TABLE`).
11. Owner receives `STATE_SNAPSHOT` with `status="sit_out"`.
**Assert**:
- Step 7: `reserve_until > time.time()`.
- Step 9: Owner's status is `sit_out` in broadcast.
- Step 11: Owner's own status in snapshot is `sit_out`.
- No crash, no orphaned tasks.

---

## Failure Cases

| FC | Scenario | Expected Behavior |
|----|----------|-------------------|
| FC-01 | `disconnect()` on unknown user_id | No-op, no exception |
| FC-02 | `reconnect()` on user_id not in `_state.players` | Appropriate error or spectator join (not crash) |
| FC-03 | `disconnect()` called with timer already expired | No-op (player already `SIT_OUT`) — double-guard on `is_connected` handles this |
| FC-04 | `send_sync()` on user not in `_connections` | No-op (no snapshot, no exception) |
| FC-05 | Timer fires for a player who reconnected mid-sleep | `if player and not player.is_connected` guard prevents `_force_sit_out` on already-connected player |

---

## Coverage Requirements

| Area | Requirement |
|------|-------------|
| `disconnect()` double-disconnect guard | TC-02, TC-03 |
| `disconnect()` fresh disconnect | TC-01, TC-11 |
| `reconnect()` within window | TC-04, TC-05 |
| `reconnect()` after expiry | TC-06, TC-07, TC-08 |
| `disconnect_reserve_seconds` constructor param | TC-09, TC-10, TC-19 |
| `SYNC_REQUEST` / `send_sync` | TC-12, TC-13 |
| Active hand disconnect + auto-fold | TC-14 |
| Between-hands disconnect | TC-15 |
| Duplicate reconnect | TC-16 |
| Spectator disconnect | TC-17 |
| Full lifecycle | TC-18 |
| Simulation S7 end-to-end | TC-S7 |

Minimum new test count: **19 unit tests + 1 simulation test = 20 new tests**.

---

## Regression Gate

- All 272 existing tests must pass.
- `tests/test_session_manager.py` must pass unchanged — the module-level constant patching pattern must still work.
- `tests/conftest.py` must not be modified.
- New count after implementation: **272 + 20 = 292 minimum**.
