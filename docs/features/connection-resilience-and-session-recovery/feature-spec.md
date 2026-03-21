# Feature Spec — connection-resilience-and-session-recovery

> Agent: Product Manager
> Date: 2026-03-19

---

## Feature Goal

Harden the backend's reconnect and temporary-disconnect handling so it behaves like a reliable real-time poker system under realistic mobile-network conditions: players can lose connection and come back without the session feeling broken.

The system already has a functional reserve-window mechanism (60-second timer, `SIT_OUT` on expiry, `STATE_SNAPSHOT` on reconnect). This feature closes the remaining reliability gaps, wires configuration correctly, and proves all recovery behaviors with comprehensive tests.

---

## Problem Statement

The current reconnect infrastructure is sound in design but has three concrete defects plus significant gaps in test coverage:

1. **Double-disconnect timer reset** — if `disconnect()` is called for a player who is already disconnected (e.g., a lingering TCP close fires after the WS cleanup), the 60-second reserve timer resets from zero. A player could theoretically extend their reservation window indefinitely by oscillating connections. More practically, a legitimate user who experiences flapping network conditions gets a longer-than-expected reserve window without the system being in control.

2. **`DISCONNECT_RESERVE_SECONDS` ignores settings** — `config.py` defines `disconnect_timeout_seconds` (defaulting to 60, configurable via `DISCONNECT_TIMEOUT_SECONDS` env var) but `session_manager.py` hardcodes `DISCONNECT_RESERVE_SECONDS = 60` and never reads the setting. Setting the env var silently has no effect.

3. **Reconnect-after-expiry is untested** — after the 60-second timer fires and the player moves to `SIT_OUT`, they can still reconnect (seat is preserved in `_state.players`). This behavior is correct but entirely untested. Operators and developers have no verified guarantee for this path.

4. **Disconnect broadcast payload not verified in tests** — the `PLAYER_STATUS{status="disconnected"}` event includes `reserve_until` (future epoch), but no test checks this field is populated correctly.

5. **SYNC_REQUEST / send_sync is untested** — the `SYNC_REQUEST` message and the `send_sync` path that resends a full `STATE_SNAPSHOT` on demand exists but has zero test coverage.

---

## Scope

### In Scope

1. **Fix double-disconnect**: Guard `disconnect()` — if `player.is_connected` is already `False`, do not reset the timer or overwrite `disconnect_at`. Only a fresh disconnect (transition from connected → disconnected) starts a new timer.

2. **Wire config**: Add `disconnect_reserve_seconds` parameter to `TableSessionManager.__init__`. `TableSessionRegistry.get_or_create` passes `settings.disconnect_timeout_seconds`. The module-level `DISCONNECT_RESERVE_SECONDS` constant remains as the default (preserving existing test-patching patterns).

3. **Tests for all reconnect scenarios** — new `tests/test_connection_resilience.py` covering:
   - Reconnect after reserve expiry succeeds with `SIT_OUT` status
   - Double-disconnect does not reset the reserve timer
   - Disconnect broadcast `reserve_until` is in the future
   - SYNC_REQUEST delivers a fresh STATE_SNAPSHOT
   - Full lifecycle: join → disconnect → expiry → reconnect → SIT_OUT → sit_in → WAITING

4. **New simulation scenario S7** — `simulation/scenarios/s7_disconnect_reserve_expiry.py` proving that a player who does not reconnect within the reserve window ends up with `SIT_OUT` status, and that the table continues correctly without them.

5. **Wire S7 into `tests/test_simulation_scenarios.py`**.

### Out of Scope

- Crash recovery (server restart with active disconnect timers lost)
- Active-hand state replay after reconnect (snapshot-only resync is in scope; full hand replay from event log is deferred)
- Spectator reserve windows (spectators leave immediately on disconnect — by design, not a bug)
- Push notifications (out of scope for all phases until mobile client exists)
- Distributed session recovery (multi-server handoff)
- Reconnect across different `table_id` values
- Any `poker_engine/` changes
- Any mobile client code

---

## Disconnect / Reconnect Behavior — Explicit Definitions

### Fresh disconnect (connected → disconnected)
1. `player.is_connected = False`, `player.disconnect_at = now()`
2. Remove from `_connections`
3. Broadcast `PLAYER_STATUS{status="disconnected", reserve_until=now()+reserve_seconds}`
4. Start reserve timer

### Double-disconnect (already disconnected → disconnect called again)
1. No-op: timer is NOT reset, `disconnect_at` is NOT changed
2. No broadcast (no event to send — player is already known disconnected)

### Reconnect within reserve window
1. Cancel reserve timer
2. `player.is_connected = True`, `player.disconnect_at = None`
3. Restore `_connections`
4. Broadcast `PLAYER_STATUS{status=<player's current status>}`
5. Send `STATE_SNAPSHOT` to reconnected player
6. Returns `ReconnectResult(success=True)`

### Reconnect after reserve window expires
1. Reserve timer fired → `player.status = SIT_OUT`
2. Player reconnects: same flow as "within window" (timer already cancelled/done)
3. Broadcast `PLAYER_STATUS{status="sit_out"}`
4. Send `STATE_SNAPSHOT` — player sees themselves as `SIT_OUT`
5. Returns `ReconnectResult(success=True)` — seat is still held
6. Player must call `SIT_IN` to rejoin the game flow

### Reserve expiry with no reconnect
1. Timer fires → player moves to `SIT_OUT`
2. Broadcast `PLAYER_STATUS{sit_out}` to all
3. Player remains in `_state.players` (seat held indefinitely until voluntary `LEAVE_TABLE`)
4. Hand start eligibility excludes `SIT_OUT` players

---

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | `disconnect()` on a connected player starts the reserve timer and broadcasts `PLAYER_STATUS{disconnected}` with `reserve_until > now()` |
| AC-02 | `disconnect()` on an already-disconnected player does not reset the timer and does not broadcast again |
| AC-03 | `reconnect()` within the reserve window cancels the timer, restores connection, broadcasts `PLAYER_STATUS{<status>}`, and sends `STATE_SNAPSHOT` |
| AC-04 | `reconnect()` after reserve expiry succeeds with `SIT_OUT` status; player receives `STATE_SNAPSHOT`; player must call `SIT_IN` to rejoin |
| AC-05 | `DISCONNECT_RESERVE_SECONDS` in session_manager uses the value passed to `TableSessionManager.__init__`, which defaults to the module-level constant |
| AC-06 | `TableSessionRegistry.get_or_create` passes `settings.disconnect_timeout_seconds` as `disconnect_reserve_seconds` |
| AC-07 | `SYNC_REQUEST` delivers a full `STATE_SNAPSHOT` to the requesting player |
| AC-08 | S7 simulation: a player who does not reconnect within the reserve window ends up `SIT_OUT`; table continues normally |
| AC-09 | All existing tests continue to pass without modification |
| AC-10 | `reserve_until` in the disconnect broadcast is between `now() + reserve_seconds - 1` and `now() + reserve_seconds + 1` |

---

## Dependencies

- `backend/sessions/session_manager.py` — primary change target
- `backend/session_registry.py` — pass config to manager
- `backend/config.py` — `disconnect_timeout_seconds` already defined
- `tests/conftest.py` — manager fixture (may need `disconnect_reserve_seconds` parameter)
- `simulation/scenarios/` — new S7
- `tests/test_simulation_scenarios.py` — wire S7

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Patching `sm_module.DISCONNECT_RESERVE_SECONDS` in existing tests breaks | Medium | Keep module constant as fallback; instance-level value takes priority when passed |
| S7 timing sensitive to CI speed | Medium | Use patched `DISCONNECT_RESERVE_SECONDS=0.1` for fast expiry in simulation |
| Reconnect-after-expiry test flaky due to asyncio.sleep timing | Low | Use `0.05s` timer + `0.2s` wait — consistent with existing timeout test pattern |
| `settings.disconnect_timeout_seconds` unused in tests after fix | Low | No test relies on the env var — all use patching or constructor params |
| Double-disconnect fix breaks edge case in existing tests | Low | Existing tests only call `disconnect()` once per player; no existing test tests double-disconnect |
