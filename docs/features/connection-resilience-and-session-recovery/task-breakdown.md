# Task Breakdown — connection-resilience-and-session-recovery

> Agent: Senior Mobile Game Developer
> Date: 2026-03-19

---

## Overview

5 implementation tasks. No research task needed — codebase is already understood from the technical design phase.

| Task | File(s) | Description |
|------|---------|-------------|
| T1 | `backend/sessions/session_manager.py` | Fix double-disconnect guard; add `disconnect_reserve_seconds` param; replace constant usages |
| T2 | `backend/session_registry.py` | Pass `settings.disconnect_timeout_seconds` to manager |
| T3 | `tests/test_connection_resilience.py` | New test file — all reconnect scenarios (19 tests) |
| T4 | `simulation/scenarios/s7_disconnect_reserve_expiry.py` | New simulation scenario |
| T5 | `tests/test_simulation_scenarios.py` | Add `test_s7_disconnect_reserve_expiry` |

---

## T1 — Fix `session_manager.py`

**File**: `backend/sessions/session_manager.py`

### Step 1a: Add `disconnect_reserve_seconds` parameter to `__init__`

Locate the `__init__` signature. After `analytics: Optional[AnalyticsService] = None`, add:

```python
disconnect_reserve_seconds: Optional[int] = None,
```

In the body, after existing attribute assignments, add:

```python
self._disconnect_reserve_seconds: int = (
    disconnect_reserve_seconds
    if disconnect_reserve_seconds is not None
    else DISCONNECT_RESERVE_SECONDS
)
```

### Step 1b: Update `_run_disconnect_timer` to use instance value

Change:
```python
await asyncio.sleep(DISCONNECT_RESERVE_SECONDS)
```
To:
```python
await asyncio.sleep(self._disconnect_reserve_seconds)
```

### Step 1c: Fix `disconnect()` — add double-disconnect guard and use instance value

In the `disconnect` method, after the spectators block and the `player is None` check, add:

```python
# Guard: only a fresh disconnect starts the timer.
# If already disconnected, do nothing — preserve original disconnect_at and timer.
if not player.is_connected:
    return
```

Also change the `reserve_until` computation from:
```python
reserve_until=time.time() + DISCONNECT_RESERVE_SECONDS,
```
To:
```python
reserve_until=time.time() + self._disconnect_reserve_seconds,
```

---

## T2 — Fix `session_registry.py`

**File**: `backend/session_registry.py`

In `get_or_create`, when constructing `TableSessionManager`, add the new keyword argument:

```python
self._sessions[table_id] = TableSessionManager(
    table_id=table_id,
    club_id=club_id,
    config=config,
    persistence=persistence,
    broadcaster=broadcaster,
    disconnect_reserve_seconds=settings.disconnect_timeout_seconds,  # NEW
)
```

Ensure `settings` is imported — it's already imported via `from .config import settings` (verify before adding).

---

## T3 — Create `tests/test_connection_resilience.py`

```python
"""
Tests for connection resilience and session recovery.

Covers all reconnect scenarios per feature spec ACs:
  - AC-01: Fresh disconnect starts timer, broadcasts PLAYER_STATUS{disconnected} with reserve_until
  - AC-02: Double-disconnect does not reset the timer
  - AC-03: Reconnect within window restores connection and sends STATE_SNAPSHOT
  - AC-04: Reconnect after expiry succeeds with SIT_OUT status
  - AC-05: disconnect_reserve_seconds constructor param is respected
  - AC-07: SYNC_REQUEST delivers STATE_SNAPSHOT
  - AC-10: reserve_until is accurate
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.sessions.session_manager as sm_module
from backend.sessions.session_manager import TableSessionManager, DISCONNECT_RESERVE_SECONDS
from poker_engine.engine.models import TableConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(disconnect_reserve_seconds=None) -> TableSessionManager:
    """Create a minimal TableSessionManager for testing."""
    config = TableConfig(small_blind=5, big_blind=10, min_buy_in=100, max_buy_in=500)
    persistence = AsyncMock()
    persistence.save_player_session = AsyncMock(return_value=None)
    broadcaster = AsyncMock()
    broadcaster.broadcast_to_all = AsyncMock(return_value=None)
    broadcaster.broadcast_to_user = AsyncMock(return_value=None)
    analytics = None
    kwargs = dict(
        table_id="test_table",
        club_id="test_club",
        config=config,
        persistence=persistence,
        broadcaster=broadcaster,
        analytics=analytics,
    )
    if disconnect_reserve_seconds is not None:
        kwargs["disconnect_reserve_seconds"] = disconnect_reserve_seconds
    return TableSessionManager(**kwargs)


def _collect_broadcasts(manager: TableSessionManager, event_type: str) -> list:
    """Return list of payloads broadcast with a given type."""
    calls = manager._broadcaster.broadcast_to_all.call_args_list
    return [
        call.args[1] if call.args else call.kwargs.get("payload")
        for call in calls
        if (call.args[0] if call.args else call.kwargs.get("event_type")) == event_type
    ]


# ---------------------------------------------------------------------------
# TC-09, TC-10 — Constructor parameter
# ---------------------------------------------------------------------------

def test_constructor_default_uses_module_constant():
    """TC-09: No param → falls back to DISCONNECT_RESERVE_SECONDS module constant."""
    manager = _make_manager()
    assert manager._disconnect_reserve_seconds == DISCONNECT_RESERVE_SECONDS


def test_constructor_param_overrides_module_constant():
    """TC-09: Explicit param takes priority over module constant."""
    manager = _make_manager(disconnect_reserve_seconds=0.05)
    assert manager._disconnect_reserve_seconds == 0.05


def test_module_constant_patch_used_as_fallback(monkeypatch):
    """TC-10: Patching sm_module.DISCONNECT_RESERVE_SECONDS is respected when no param given."""
    monkeypatch.setattr(sm_module, "DISCONNECT_RESERVE_SECONDS", 0.05)
    manager = _make_manager()
    assert manager._disconnect_reserve_seconds == 0.05


# ---------------------------------------------------------------------------
# Fixtures for async tests
# ---------------------------------------------------------------------------

@pytest.fixture
async def manager_and_player():
    """Manager with one pre-joined player."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    # Inject a player directly into manager state
    result = await m.join_as_player("player_1", display_name="Alice", buy_in=200)
    yield m, "player_1"
    # Cancel any pending tasks
    for task in list(m._disconnect_tasks.values()):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


# ---------------------------------------------------------------------------
# TC-01 — Fresh disconnect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fresh_disconnect_sets_is_connected_false():
    """TC-01: disconnect() sets is_connected=False."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    await m.disconnect("p1")

    player = m._state.players["p1"]
    assert player.is_connected is False
    assert player.disconnect_at is not None

    # Cleanup
    m._disconnect_tasks.get("p1") and m._disconnect_tasks["p1"].cancel()


@pytest.mark.asyncio
async def test_fresh_disconnect_starts_timer():
    """TC-01: disconnect() creates a timer task."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    await m.disconnect("p1")

    assert "p1" in m._disconnect_tasks
    assert not m._disconnect_tasks["p1"].done()

    m._disconnect_tasks["p1"].cancel()


@pytest.mark.asyncio
async def test_fresh_disconnect_broadcasts_player_status():
    """TC-01: disconnect() broadcasts PLAYER_STATUS{disconnected}."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    m._broadcaster.broadcast_to_all.reset_mock()

    await m.disconnect("p1")

    calls = m._broadcaster.broadcast_to_all.call_args_list
    status_calls = [c for c in calls if "PLAYER_STATUS" in str(c)]
    assert len(status_calls) >= 1

    m._disconnect_tasks.get("p1") and m._disconnect_tasks["p1"].cancel()


# ---------------------------------------------------------------------------
# TC-11 — reserve_until accuracy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reserve_until_is_accurate():
    """TC-11: reserve_until in disconnect broadcast ≈ now + disconnect_reserve_seconds."""
    reserve_secs = 1.0
    m = _make_manager(disconnect_reserve_seconds=reserve_secs)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    m._broadcaster.broadcast_to_all.reset_mock()

    t_before = time.time()
    await m.disconnect("p1")
    t_after = time.time()

    # Find the PLAYER_STATUS broadcast call and check reserve_until
    found = False
    for call in m._broadcaster.broadcast_to_all.call_args_list:
        args = call.args if call.args else []
        kwargs = call.kwargs if call.kwargs else {}
        payload = args[1] if len(args) > 1 else kwargs.get("payload")
        if payload and hasattr(payload, "reserve_until") and payload.reserve_until:
            assert t_before + reserve_secs - 0.1 < payload.reserve_until < t_after + reserve_secs + 0.1
            found = True
            break
    assert found, "No PLAYER_STATUS broadcast with reserve_until found"

    m._disconnect_tasks.get("p1") and m._disconnect_tasks["p1"].cancel()


# ---------------------------------------------------------------------------
# TC-02, TC-03 — Double-disconnect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_double_disconnect_does_not_reset_disconnect_at():
    """TC-02: Second disconnect() leaves disconnect_at unchanged."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    await m.disconnect("p1")
    disconnect_at_first = m._state.players["p1"].disconnect_at
    task_first = m._disconnect_tasks["p1"]

    await asyncio.sleep(0.01)
    await m.disconnect("p1")

    assert m._state.players["p1"].disconnect_at == disconnect_at_first
    assert m._disconnect_tasks["p1"] is task_first

    task_first.cancel()


@pytest.mark.asyncio
async def test_double_disconnect_does_not_send_second_broadcast():
    """TC-02: Second disconnect() produces no additional PLAYER_STATUS broadcast."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    await m.disconnect("p1")
    broadcast_count_after_first = m._broadcaster.broadcast_to_all.call_count

    await m.disconnect("p1")
    broadcast_count_after_second = m._broadcaster.broadcast_to_all.call_count

    assert broadcast_count_after_second == broadcast_count_after_first

    m._disconnect_tasks["p1"].cancel()


@pytest.mark.asyncio
async def test_double_disconnect_cannot_extend_reserve_window():
    """TC-03: Timer fires on original schedule despite second disconnect call."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    await m.disconnect("p1")
    await asyncio.sleep(0.02)
    await m.disconnect("p1")   # should be no-op

    await asyncio.sleep(0.15)  # well past original 0.05s

    player = m._state.players["p1"]
    from backend.sessions.player_models import PlayerStatus
    assert player.status == PlayerStatus.SIT_OUT


# ---------------------------------------------------------------------------
# TC-04, TC-05 — Reconnect within window
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconnect_within_window_restores_connection():
    """TC-04: Reconnect within reserve window sets is_connected=True."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")

    result = await m.join_as_player("p1", display_name="Alice", buy_in=200)

    assert result.success is True
    assert m._state.players["p1"].is_connected is True
    assert m._state.players["p1"].disconnect_at is None


@pytest.mark.asyncio
async def test_reconnect_within_window_cancels_timer():
    """TC-04: Reconnect cancels the disconnect timer task."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")

    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    assert "p1" not in m._disconnect_tasks or m._disconnect_tasks["p1"].done()


@pytest.mark.asyncio
async def test_reconnect_within_window_sends_state_snapshot():
    """TC-05: Reconnect within window sends STATE_SNAPSHOT to the reconnecting player."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")
    m._broadcaster.broadcast_to_user.reset_mock()

    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    calls = m._broadcaster.broadcast_to_user.call_args_list
    snapshot_calls = [c for c in calls if "STATE_SNAPSHOT" in str(c)]
    assert len(snapshot_calls) >= 1


# ---------------------------------------------------------------------------
# TC-06, TC-07, TC-08 — Reconnect after expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconnect_after_expiry_succeeds():
    """TC-06: Reconnect after reserve expiry returns success."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")
    await asyncio.sleep(0.2)   # timer fires

    result = await m.join_as_player("p1", display_name="Alice", buy_in=200)

    assert result.success is True
    assert m._state.players["p1"].is_connected is True


@pytest.mark.asyncio
async def test_reconnect_after_expiry_player_is_sit_out():
    """TC-06: After expiry, player status is SIT_OUT on reconnect."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")
    await asyncio.sleep(0.2)

    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    from backend.sessions.player_models import PlayerStatus
    assert m._state.players["p1"].status == PlayerStatus.SIT_OUT


@pytest.mark.asyncio
async def test_reconnect_after_expiry_sends_state_snapshot():
    """TC-07: STATE_SNAPSHOT sent on reconnect-after-expiry."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")
    await asyncio.sleep(0.2)
    m._broadcaster.broadcast_to_user.reset_mock()

    await m.join_as_player("p1", display_name="Alice", buy_in=200)

    calls = m._broadcaster.broadcast_to_user.call_args_list
    snapshot_calls = [c for c in calls if "STATE_SNAPSHOT" in str(c)]
    assert len(snapshot_calls) >= 1


# ---------------------------------------------------------------------------
# TC-12, TC-13 — SYNC_REQUEST / send_sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_request_sends_state_snapshot():
    """TC-12: send_sync delivers STATE_SNAPSHOT to the requesting player."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    m._broadcaster.broadcast_to_user.reset_mock()

    await m.send_sync("p1")

    calls = m._broadcaster.broadcast_to_user.call_args_list
    snapshot_calls = [c for c in calls if "STATE_SNAPSHOT" in str(c)]
    assert len(snapshot_calls) >= 1


@pytest.mark.asyncio
async def test_sync_request_unknown_user_no_crash():
    """TC-13: send_sync on unknown user_id does not raise."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    # Should not raise
    await m.send_sync("unknown_user")


# ---------------------------------------------------------------------------
# TC-17 — Spectator disconnect (no reserve timer)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spectator_disconnect_has_no_reserve_timer():
    """TC-17: Spectators get no reserve window on disconnect."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_spectator("spec_1")

    await m.disconnect("spec_1")

    assert "spec_1" not in m._disconnect_tasks
    assert "spec_1" not in m._spectators


# ---------------------------------------------------------------------------
# TC-16 — Duplicate reconnect (idempotent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_reconnect_is_idempotent():
    """TC-16: Two reconnect calls in rapid succession don't crash and leave valid state."""
    m = _make_manager(disconnect_reserve_seconds=0.5)
    await m.join_as_player("p1", display_name="Alice", buy_in=200)
    await m.disconnect("p1")

    r1 = await m.join_as_player("p1", display_name="Alice", buy_in=200)
    r2 = await m.join_as_player("p1", display_name="Alice", buy_in=200)

    assert r1.success is True
    assert r2.success is True
    assert m._state.players["p1"].is_connected is True
```

---

## T4 — Create `simulation/scenarios/s7_disconnect_reserve_expiry.py`

```python
"""
S7 — Disconnect Reserve Expiry simulation scenario.

Flow:
  1. Two players connect and join the table.
  2. A hand starts; owner and joiner receive BLINDS_POSTED.
  3. Owner disconnects — joiner sees PLAYER_STATUS{disconnected}.
  4. Reserve timer fires (patched to 0.1s) — joiner sees PLAYER_STATUS{sit_out}.
  5. Owner reconnects — receives STATE_SNAPSHOT with status=sit_out.

Usage: Called from tests/test_simulation_scenarios.py with make_test_client fixture.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from simulation.helpers import drain_until, ws_send


async def run(http, owner_ws, joiner_ws, app, table_id: str) -> None:
    """
    Run the S7 scenario.

    Preconditions:
      - owner_ws and joiner_ws are open WebSocket connections
      - Both have sent JOIN_TABLE{role=player} and received STATE_SNAPSHOT
      - manager._disconnect_reserve_seconds has been patched to 0.1 externally
    """
    # --- Start a hand ---
    await ws_send(owner_ws, {
        "type": "START_HAND",
        "request_id": str(uuid.uuid4()),
        "table_id": table_id,
        "payload": {},
    })

    # Both players receive BLINDS_POSTED (drain for it)
    await drain_until(owner_ws, "BLINDS_POSTED", max_msgs=15)
    await drain_until(joiner_ws, "BLINDS_POSTED", max_msgs=15)

    # --- Owner disconnects ---
    await owner_ws.close()

    # Joiner should receive PLAYER_STATUS{disconnected}
    disconnect_msg = await drain_until(joiner_ws, "PLAYER_STATUS", max_msgs=10)
    assert disconnect_msg["payload"]["status"] == "disconnected", (
        f"Expected status=disconnected, got: {disconnect_msg['payload']['status']}"
    )
    assert disconnect_msg["payload"].get("reserve_until", 0) > time.time(), (
        "reserve_until should be in the future"
    )

    # --- Wait for reserve timer to fire (0.1s + buffer) ---
    await asyncio.sleep(0.3)

    # Joiner should receive PLAYER_STATUS{sit_out}
    sit_out_msg = await drain_until(joiner_ws, "PLAYER_STATUS", max_msgs=10)
    assert sit_out_msg["payload"]["status"] == "sit_out", (
        f"Expected status=sit_out after expiry, got: {sit_out_msg['payload']['status']}"
    )

    # --- Owner reconnects ---
    reconnect_ws = await http.ws_connect(f"/ws/table/{table_id}?token={http.owner_token}")
    try:
        await ws_send(reconnect_ws, {
            "type": "JOIN_TABLE",
            "request_id": str(uuid.uuid4()),
            "table_id": table_id,
            "payload": {"role": "player"},
        })

        snapshot = await drain_until(reconnect_ws, "STATE_SNAPSHOT", max_msgs=10)
        players = snapshot["payload"]["players"]
        owner_id = http.owner_user_id
        assert owner_id in players, "Owner not in snapshot players"
        assert players[owner_id]["status"] == "sit_out", (
            f"Owner should be sit_out in snapshot, got: {players[owner_id]['status']}"
        )
    finally:
        await reconnect_ws.close()
```

---

## T5 — Update `tests/test_simulation_scenarios.py`

Add one test at the end of the file:

```python
@pytest.mark.asyncio
async def test_s7_disconnect_reserve_expiry(make_test_client):
    """S7: Player who does not reconnect within reserve window ends up SIT_OUT."""
    from simulation.scenarios.s7_disconnect_reserve_expiry import run as s7_run

    async with make_test_client() as (http, owner_ws, joiner_ws, app, table_id):
        # Patch the manager's reserve seconds before any hand activity
        manager = app.state.registry._sessions.get(table_id)
        if manager:
            manager._disconnect_reserve_seconds = 0.1

        await s7_run(http, owner_ws, joiner_ws, app, table_id)
```

---

## Ordering

1. T1 (session_manager.py changes) — no dependencies
2. T2 (session_registry.py) — depends on T1 (new param must exist)
3. T3 (test_connection_resilience.py) — can be written before or after T1/T2, but must pass after both
4. T4 (s7 scenario) — can be written independently
5. T5 (test_simulation_scenarios.py) — depends on T4

Run regression after T5 to confirm 272 + 20 = 292+ passing.
