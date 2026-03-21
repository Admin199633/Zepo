# Technical Design — connection-resilience-and-session-recovery

> Agent: Senior Mobile Game Developer
> Date: 2026-03-19

---

## 1. Recovery Strategy

**Phase strategy: harden the existing implementation.** The reconnect architecture is sound. The WS router's `finally` block, the 60-second reserve timer, the `_do_reconnect` flow, and the `STATE_SNAPSHOT` resync are all correct. This feature fixes two concrete defects and adds the test coverage needed to prove all recovery behaviors.

**No new architecture is introduced.** The changes are:
1. Fix `disconnect()` to guard against timer reset on double-disconnect
2. Wire `disconnect_reserve_seconds` through `TableSessionManager.__init__` and `TableSessionRegistry`
3. New tests for all reconnect scenarios
4. New simulation scenario S7

---

## 2. Change 1 — Fix Double-Disconnect

**File**: `backend/sessions/session_manager.py` — `disconnect()` method

**Current behavior** (line 265–289):
```python
async def disconnect(self, user_id: str) -> None:
    ...
    player.is_connected = False        # always overwrites
    player.disconnect_at = time.time() # always resets
    ...
    self._cancel_disconnect_timer(user_id)  # always cancels old timer
    task = asyncio.create_task(...)         # always starts new timer
```

**Fixed behavior**: Guard at entry. If player is already disconnected, take no action.
```python
async def disconnect(self, user_id: str) -> None:
    async with self._lock:
        if user_id in self._spectators:
            del self._spectators[user_id]
            self._connections.pop(user_id, None)
            return

        player = self._state.players.get(user_id)
        if player is None:
            return

        # Guard: only a fresh disconnect (connected → disconnected) starts the timer.
        # If already disconnected, do nothing — preserve original disconnect_at and timer.
        if not player.is_connected:
            return

        player.is_connected = False
        player.disconnect_at = time.time()
        self._connections.pop(user_id, None)

        await self._broadcast_all(
            ServerEventType.PLAYER_STATUS,
            PlayerStatusPayload(
                user_id=user_id,
                status="disconnected",
                stack=player.stack,
                reserve_until=time.time() + self._disconnect_reserve_seconds,
            ),
        )

        self._cancel_disconnect_timer(user_id)
        task = asyncio.create_task(
            self._run_disconnect_timer(user_id),
            name=f"disconnect_{user_id}",
        )
        self._disconnect_tasks[user_id] = task
```

**Note**: `reserve_until` now uses `self._disconnect_reserve_seconds` instead of the module-level constant. See Change 2.

---

## 3. Change 2 — Wire `disconnect_reserve_seconds` Through the Constructor

### `backend/sessions/session_manager.py`

Add parameter to `__init__`:
```python
def __init__(
    self,
    table_id: str,
    club_id: str,
    config: TableConfig,
    persistence: PersistenceAdapter,
    broadcaster: BroadcastService,
    analytics: Optional[AnalyticsService] = None,
    disconnect_reserve_seconds: Optional[int] = None,   # NEW
) -> None:
    ...
    self._disconnect_reserve_seconds: int = (
        disconnect_reserve_seconds
        if disconnect_reserve_seconds is not None
        else DISCONNECT_RESERVE_SECONDS
    )
```

Replace all uses of `DISCONNECT_RESERVE_SECONDS` inside the class with `self._disconnect_reserve_seconds`:
- `_run_disconnect_timer`: `await asyncio.sleep(self._disconnect_reserve_seconds)`
- `disconnect`: `reserve_until=time.time() + self._disconnect_reserve_seconds`

The module-level `DISCONNECT_RESERVE_SECONDS = 60` constant stays as the fallback default. Existing tests that patch `sm_module.DISCONNECT_RESERVE_SECONDS` continue to work for tests that create the manager without the parameter. Tests that create the manager with `disconnect_reserve_seconds=0.05` are preferred for new tests.

### `backend/session_registry.py`

Import and pass the setting:
```python
from .config import settings

async def get_or_create(
    self,
    table_id: str,
    club_id: str,
    config: TableConfig,
    persistence: PersistenceAdapter,
    broadcaster: BroadcastService,
) -> TableSessionManager:
    async with self._lock:
        if table_id not in self._sessions:
            self._sessions[table_id] = TableSessionManager(
                table_id=table_id,
                club_id=club_id,
                config=config,
                persistence=persistence,
                broadcaster=broadcaster,
                disconnect_reserve_seconds=settings.disconnect_timeout_seconds,  # NEW
            )
        return self._sessions[table_id]
```

### `tests/conftest.py`

The `manager` fixture can optionally accept `disconnect_reserve_seconds`. Since `conftest.py` uses the default (module-level `DISCONNECT_RESERVE_SECONDS`), it does not need to change. Individual tests that need a fast timer will create their own manager with `disconnect_reserve_seconds=0.05`.

---

## 4. What Is Recovered After Reconnect

| Item | Recovered | Notes |
|------|-----------|-------|
| Seat index | YES | `_state.players[uid].seat_index` unchanged |
| Stack | YES | `_state.players[uid].stack` unchanged |
| Player status (`ACTIVE`, `SIT_OUT`, etc.) | YES | Unchanged during disconnect |
| Hole cards | YES | `build_player_view` includes hole cards in snapshot |
| Community cards | YES | Included in snapshot |
| Current phase | YES | Included in snapshot |
| Pot state | YES | Included in snapshot |
| `disconnect_at` | CLEARED | Reset to `None` on reconnect |
| `reserve_until` | N/A | Was in the broadcast event, not persisted in player state |
| Disconnect timer | CANCELLED | Timer task is cancelled |
| Turn position | YES (passively) | Snapshot shows current turn; player gets TURN_CHANGED on reconnect if it's their turn |
| Chat history | NO | Only new messages received after reconnect |

---

## 5. What Is NOT Recovered After Reconnect

- Chat messages sent while disconnected (not replayed — new messages only)
- PLAYER_ACTED / TURN_CHANGED events that occurred while disconnected (history not replayed — state visible via snapshot)
- Deck (never broadcast, never persisted)
- Active hand event log (only current state is sent, not event history)

---

## 6. Persistence Participation in Recovery

Persistence is not directly involved in the reconnect path. The session manager holds live `GameState` in memory. When a player reconnects:
- `_do_reconnect` reads from `self._state.players` (in-memory)
- `_build_player_snapshot(user_id)` builds the view from in-memory state
- No DB read occurs during reconnect

Persistence is used at the boundaries of state transitions:
- `save_player_session` is called when a player joins, when status changes (e.g., `_force_sit_out_unlocked`), and when the session manager persists at phase boundaries
- The reconnect path itself does not call `save_player_session` since the seat/stack haven't changed

This is correct: the in-memory state is authoritative during an active session. Persistence records are point-in-time snapshots, not the recovery source.

---

## 7. Reconnect After Reserve Expiry

When the 60-second timer fires:
1. `_force_sit_out_unlocked(user_id, reason="disconnect_timeout")`
2. If it's the player's turn: auto-fold via engine
3. `player.status = SIT_OUT`
4. Broadcast `PLAYER_STATUS{sit_out}`
5. `save_player_session` persists the SIT_OUT status

When the player later reconnects:
1. `_do_reconnect` is called (via `join_as_player` or `reconnect`)
2. `_cancel_disconnect_timer(user_id)` — timer is already done, no-op
3. `player.is_connected = True`, `player.disconnect_at = None`
4. Broadcast `PLAYER_STATUS{status="sit_out"}` — status unchanged
5. `STATE_SNAPSHOT` sent — player sees themselves as SIT_OUT
6. `ReconnectResult(success=True, role="player")`

The player then calls `SIT_IN` → status → `WAITING` → participates in next hand.

**No special error code is returned for reconnect-after-expiry.** The player's `SIT_OUT` status in the snapshot is the signal. This avoids a separate error path and keeps the reconnect flow uniform.

---

## 8. Duplicate/Racing Reconnect Attempts

**Scenario**: Two simultaneous reconnect attempts from the same user (e.g., the client retries the WS connection before the first attempt is fully processed).

**Current behavior**: Both attempts call `join_as_player`, which locks on `self._lock` sequentially. The first one wins and calls `_do_reconnect`. The second one also sees `user_id in self._state.players` → calls `_do_reconnect` again → sends a second `STATE_SNAPSHOT`. This is harmless (idempotent reconnect), and the second snapshot is redundant but correct.

The broadcaster uses a dict keyed by `user_id` — the second connection overwrites the first in `_connections`. The first connection's WS will eventually get a `WebSocketDisconnect` from the server side when the second connection's `finally` block unregisters it. No ghost sessions accumulate.

**No special handling needed** for this phase. The lock and the dict semantics make it safe.

---

## 9. `_run_disconnect_timer` Change

```python
async def _run_disconnect_timer(self, user_id: str) -> None:
    try:
        await asyncio.sleep(self._disconnect_reserve_seconds)  # uses instance value
    except asyncio.CancelledError:
        return

    async with self._lock:
        player = self._state.players.get(user_id)
        if player and not player.is_connected:
            await self._force_sit_out_unlocked(user_id, reason="disconnect_timeout")
```

---

## 10. New Simulation Scenario — S7

**File**: `simulation/scenarios/s7_disconnect_reserve_expiry.py`

**Flow**:
1. 2 players connect (`owner`, `joiner`)
2. Hand starts (both get `BLINDS_POSTED`)
3. `owner` disconnects — `joiner` receives `PLAYER_STATUS{disconnected}`
4. Reserve timer fires (0.1s patched timer)
5. `joiner` receives `PLAYER_STATUS{sit_out}` — owner timed out
6. `owner` reconnects — receives `STATE_SNAPSHOT` with `status="sit_out"`
7. Assertions: owner is in snapshot, status is `sit_out`

**Challenge**: Patching `DISCONNECT_RESERVE_SECONDS` in simulation. The simulation uses `make_test_client` which creates the full app. The `TableSessionManager` is created by `TableSessionRegistry.get_or_create`. After Change 2, the registry passes `settings.disconnect_timeout_seconds`. For the S7 test, we can either:
- Set `DISCONNECT_TIMEOUT_SECONDS=0` in test env (unreliable for timing)
- Patch `sm_module.DISCONNECT_RESERVE_SECONDS = 0.1` before the test and rely on the registry using the module constant as fallback

Actually with the new design: `TableSessionRegistry.get_or_create` passes `settings.disconnect_timeout_seconds`. If we patch `settings.disconnect_timeout_seconds = 0.1` before the `registry.get_or_create` call, the manager gets `0.1`. But the registry calls this only when creating a new manager instance. Since each test creates a fresh client (fresh registry), patching at test setup time works.

**Simpler approach**: The S7 scenario will patch `sm_module.DISCONNECT_RESERVE_SECONDS = 0.1` AND ensure the manager is freshly created with `disconnect_reserve_seconds=None` (which falls back to the patched module constant). Since the fixture creates `make_test_client()` fresh, the first `get_or_create` in S7 will create a manager with `disconnect_reserve_seconds=settings.disconnect_timeout_seconds`. This requires the simulation fixture to temporarily set `settings.disconnect_timeout_seconds = 0` or use a different mechanism.

**Resolution**: Patch `sm_module.DISCONNECT_RESERVE_SECONDS = 0.1` at the start of S7 (restore at end). After Change 2, `get_or_create` uses `settings.disconnect_timeout_seconds` — but the simulation can also patch this via `import backend.sessions.session_manager as sm; sm.DISCONNECT_RESERVE_SECONDS = 0.1`. However, this won't affect the manager since it reads the setting at creation time.

**Final approach**: S7 will take `disconnect_reserve_seconds` as a parameter. The test fixture will create a custom `make_test_client` variant or pass the reserve seconds to the run function. Actually the cleanest approach is to patch the `settings` object before `make_test_client` is called:

```python
import backend.config as config_module
config_module.settings.disconnect_timeout_seconds = 0  # type: ignore
# now make_test_client creates app with settings.disconnect_timeout_seconds=0
```

Wait, but `settings` is a Pydantic `BaseSettings` instance which may be immutable. Let's use the approach that already works in `test_session_manager.py`: patch `sm_module.DISCONNECT_RESERVE_SECONDS` AND bypass the registry by directly controlling the manager. Since S7 is a simulation scenario using the full app, we need a different approach.

**Simplest workable approach for S7**: After the app is created by `make_test_client`, the registry creates managers lazily on first WS connect. We can patch the registry to use a short timeout by:
1. Connecting the WS
2. Grabbing the manager from `app.state.registry._sessions[table_id]`
3. Patching `manager._disconnect_reserve_seconds = 0.1`
4. Proceeding

This is a targeted in-test patch that doesn't require changing the public API. The S7 scenario function will accept the `http` client plus the mechanism to patch the manager's reserve seconds.

---

## 11. Engine Isolation

Zero changes to `poker_engine/`. The `_force_sit_out_unlocked` method already calls the engine for auto-fold when needed. The disconnect/reconnect path never calls the engine directly. Engine isolation is preserved.

---

## 12. Files to Create or Modify

| File | Change |
|------|--------|
| `backend/sessions/session_manager.py` | Fix double-disconnect guard; add `disconnect_reserve_seconds` param; use `self._disconnect_reserve_seconds` in `_run_disconnect_timer` and `disconnect` |
| `backend/session_registry.py` | Pass `settings.disconnect_timeout_seconds` to `TableSessionManager` |
| `tests/test_connection_resilience.py` | New — all reconnect scenario tests |
| `simulation/scenarios/s7_disconnect_reserve_expiry.py` | New simulation scenario |
| `tests/test_simulation_scenarios.py` | Add `test_s7_disconnect_reserve_expiry` |

**Must NOT change**:
- `backend/persistence/adapter.py`
- `backend/persistence/memory.py`
- `backend/persistence/sqlite_adapter.py`
- `poker_engine/`
- `backend/realtime/ws_router.py`
- All existing test files except `tests/test_simulation_scenarios.py` (adding one test)
- `tests/conftest.py` (no change needed — default manager fixture stays as-is)
