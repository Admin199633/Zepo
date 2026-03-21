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

import pytest

import backend.sessions.session_manager as sm_module
from backend.realtime.broadcaster import CapturingBroadcaster
from backend.persistence.memory import InMemoryPersistenceAdapter
from backend.sessions.session_manager import TableSessionManager, DISCONNECT_RESERVE_SECONDS
from poker_engine.engine.models import PlayerStatus, TableConfig


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_manager(disconnect_reserve_seconds=None) -> TableSessionManager:
    config = TableConfig(
        starting_stack=1000,
        small_blind=10,
        big_blind=20,
        turn_timer_seconds=30,
        max_players=6,
        house_rules=[],
    )
    persistence = InMemoryPersistenceAdapter()
    broadcaster = CapturingBroadcaster()
    kwargs = dict(
        table_id="test_table",
        club_id="test_club",
        config=config,
        persistence=persistence,
        broadcaster=broadcaster,
    )
    if disconnect_reserve_seconds is not None:
        kwargs["disconnect_reserve_seconds"] = disconnect_reserve_seconds
    return TableSessionManager(**kwargs)


async def _join(manager: TableSessionManager, user_id: str, conn_id: str = "conn-x") -> None:
    await manager.join_as_player(user_id, user_id.capitalize(), conn_id)


# ---------------------------------------------------------------------------
# TC-09 — Constructor parameter
# ---------------------------------------------------------------------------

def test_constructor_default_is_none():
    """TC-09: No param → internal value is None (reads module constant lazily)."""
    m = _make_manager()
    assert m._disconnect_reserve_seconds is None


def test_constructor_explicit_param_stored():
    """TC-09: Explicit param stored as given."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    assert m._disconnect_reserve_seconds == 0.05


def test_resolve_reserve_seconds_defaults_to_module_constant():
    """TC-09: _resolve_reserve_seconds() returns DISCONNECT_RESERVE_SECONDS when no param."""
    m = _make_manager()
    assert m._resolve_reserve_seconds() == DISCONNECT_RESERVE_SECONDS


def test_resolve_reserve_seconds_returns_explicit_value():
    """TC-09: _resolve_reserve_seconds() returns explicit value when param provided."""
    m = _make_manager(disconnect_reserve_seconds=5)
    assert m._resolve_reserve_seconds() == 5


# ---------------------------------------------------------------------------
# TC-10 — Module-level constant patching still works
# ---------------------------------------------------------------------------

async def test_module_constant_patch_respected(monkeypatch):
    """TC-10: Patching sm_module.DISCONNECT_RESERVE_SECONDS is used lazily for timer."""
    monkeypatch.setattr(sm_module, "DISCONNECT_RESERVE_SECONDS", 0.05)
    m = _make_manager()  # no explicit param → uses module constant lazily
    await _join(m, "p1")
    await m.disconnect("p1")
    await asyncio.sleep(0.2)  # 0.05s timer should have fired

    assert m._state.players["p1"].status == PlayerStatus.SIT_OUT


# ---------------------------------------------------------------------------
# TC-01 — Fresh disconnect
# ---------------------------------------------------------------------------

async def test_fresh_disconnect_sets_is_connected_false():
    """TC-01: disconnect() sets is_connected=False and records disconnect_at."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")

    await m.disconnect("p1")

    player = m._state.players["p1"]
    assert player.is_connected is False
    assert player.disconnect_at is not None

    m._disconnect_tasks.get("p1") and m._disconnect_tasks["p1"].cancel()


async def test_fresh_disconnect_starts_timer():
    """TC-01: disconnect() creates a timer task."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")

    await m.disconnect("p1")

    assert "p1" in m._disconnect_tasks
    assert not m._disconnect_tasks["p1"].done()

    m._disconnect_tasks["p1"].cancel()


async def test_fresh_disconnect_broadcasts_player_status():
    """TC-01: disconnect() broadcasts PLAYER_STATUS with status=disconnected."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")
    m._broadcaster.reset()

    await m.disconnect("p1")

    events = m._broadcaster.broadcasts_of_type("PLAYER_STATUS")
    assert len(events) == 1
    assert events[0].payload["status"] == "disconnected"
    assert events[0].payload["user_id"] == "p1"

    m._disconnect_tasks["p1"].cancel()


# ---------------------------------------------------------------------------
# TC-11 — reserve_until accuracy
# ---------------------------------------------------------------------------

async def test_reserve_until_is_accurate():
    """TC-11: reserve_until in disconnect broadcast ≈ now + reserve_seconds."""
    reserve_secs = 1.0
    m = _make_manager(disconnect_reserve_seconds=reserve_secs)
    await _join(m, "p1")
    m._broadcaster.reset()

    t_before = time.time()
    await m.disconnect("p1")
    t_after = time.time()

    events = m._broadcaster.broadcasts_of_type("PLAYER_STATUS")
    assert len(events) == 1
    reserve_until = events[0].payload.get("reserve_until")
    assert reserve_until is not None
    assert t_before + reserve_secs - 0.1 < reserve_until < t_after + reserve_secs + 0.1

    m._disconnect_tasks["p1"].cancel()


# ---------------------------------------------------------------------------
# TC-02, TC-03 — Double-disconnect
# ---------------------------------------------------------------------------

async def test_double_disconnect_preserves_disconnect_at():
    """TC-02: Second disconnect() leaves disconnect_at unchanged."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")

    await m.disconnect("p1")
    disconnect_at_first = m._state.players["p1"].disconnect_at
    task_first = m._disconnect_tasks["p1"]

    await asyncio.sleep(0.01)
    await m.disconnect("p1")

    assert m._state.players["p1"].disconnect_at == disconnect_at_first
    assert m._disconnect_tasks["p1"] is task_first

    task_first.cancel()


async def test_double_disconnect_sends_no_second_broadcast():
    """TC-02: Second disconnect() produces no additional PLAYER_STATUS broadcast."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")

    await m.disconnect("p1")
    count_after_first = len(m._broadcaster.broadcasts_of_type("PLAYER_STATUS"))

    await m.disconnect("p1")
    count_after_second = len(m._broadcaster.broadcasts_of_type("PLAYER_STATUS"))

    assert count_after_second == count_after_first

    m._disconnect_tasks["p1"].cancel()


async def test_double_disconnect_cannot_extend_reserve_window():
    """TC-03: Timer fires on original schedule despite second disconnect() call."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await _join(m, "p1")

    await m.disconnect("p1")
    await asyncio.sleep(0.02)
    await m.disconnect("p1")   # no-op — should not reset the timer

    await asyncio.sleep(0.15)  # original timer should have already fired

    assert m._state.players["p1"].status == PlayerStatus.SIT_OUT


# ---------------------------------------------------------------------------
# TC-04, TC-05 — Reconnect within window
# ---------------------------------------------------------------------------

async def test_reconnect_within_window_restores_connection():
    """TC-04: Reconnect within reserve window sets is_connected=True."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")
    await m.disconnect("p1")

    result = await m.reconnect("p1", "conn-new")

    assert result.success is True
    assert m._state.players["p1"].is_connected is True
    assert m._state.players["p1"].disconnect_at is None


async def test_reconnect_within_window_cancels_timer():
    """TC-04: Reconnect cancels the disconnect timer."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")
    await m.disconnect("p1")

    await m.reconnect("p1", "conn-new")

    task = m._disconnect_tasks.get("p1")
    assert task is None or task.cancelled() or task.done()


async def test_reconnect_within_window_sends_state_snapshot():
    """TC-05: Reconnect within window sends STATE_SNAPSHOT to the reconnecting player."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")
    await m.disconnect("p1")
    m._broadcaster.reset()

    await m.reconnect("p1", "conn-new")

    snaps = m._broadcaster.player_messages_of_type("p1", "STATE_SNAPSHOT")
    assert len(snaps) == 1


# ---------------------------------------------------------------------------
# TC-06, TC-07, TC-08 — Reconnect after expiry
# ---------------------------------------------------------------------------

async def test_reconnect_after_expiry_succeeds():
    """TC-06: Reconnect after reserve expiry returns success."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await _join(m, "p1")
    await m.disconnect("p1")
    await asyncio.sleep(0.2)   # timer fires

    result = await m.reconnect("p1", "conn-new")

    assert result.success is True
    assert m._state.players["p1"].is_connected is True


async def test_reconnect_after_expiry_player_is_sit_out():
    """TC-06: After expiry, player status is SIT_OUT on reconnect."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await _join(m, "p1")
    await m.disconnect("p1")
    await asyncio.sleep(0.2)

    await m.reconnect("p1", "conn-new")

    assert m._state.players["p1"].status == PlayerStatus.SIT_OUT


async def test_reconnect_after_expiry_sends_state_snapshot():
    """TC-07: STATE_SNAPSHOT sent on reconnect-after-expiry."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await _join(m, "p1")
    await m.disconnect("p1")
    await asyncio.sleep(0.2)
    m._broadcaster.reset()

    await m.reconnect("p1", "conn-new")

    snaps = m._broadcaster.player_messages_of_type("p1", "STATE_SNAPSHOT")
    assert len(snaps) == 1


async def test_reconnect_after_expiry_sit_in_transitions_to_waiting():
    """TC-08: Player calls SIT_IN after expiry-reconnect → status becomes WAITING."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await _join(m, "p1")
    await m.disconnect("p1")
    await asyncio.sleep(0.2)

    await m.reconnect("p1", "conn-new")
    await m.sit_in("p1")

    assert m._state.players["p1"].status == PlayerStatus.WAITING


# ---------------------------------------------------------------------------
# TC-12, TC-13 — SYNC_REQUEST / send_sync
# ---------------------------------------------------------------------------

async def test_sync_request_sends_state_snapshot():
    """TC-12: send_sync delivers STATE_SNAPSHOT to the requesting player."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")
    m._broadcaster.reset()

    await m.send_sync("p1")

    snaps = m._broadcaster.player_messages_of_type("p1", "STATE_SNAPSHOT")
    assert len(snaps) == 1


async def test_sync_request_unknown_user_no_crash():
    """TC-13: send_sync on unknown user_id does not raise."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await m.send_sync("unknown_user")  # must not raise


# ---------------------------------------------------------------------------
# TC-17 — Spectator disconnect (no reserve timer)
# ---------------------------------------------------------------------------

async def test_spectator_disconnect_no_reserve_timer():
    """TC-17: Spectators have no reserve window — no timer task created."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await m.join_as_spectator("spec_1", "Spectator", "conn-spec")

    await m.disconnect("spec_1")

    assert "spec_1" not in m._disconnect_tasks
    assert "spec_1" not in m._spectators


# ---------------------------------------------------------------------------
# TC-16 — Duplicate reconnect (idempotent)
# ---------------------------------------------------------------------------

async def test_duplicate_reconnect_is_idempotent():
    """TC-16: Two reconnect calls in rapid succession leave valid state."""
    m = _make_manager(disconnect_reserve_seconds=5)
    await _join(m, "p1")
    await m.disconnect("p1")

    r1 = await m.reconnect("p1", "conn-1")
    r2 = await m.reconnect("p1", "conn-2")

    assert r1.success is True
    assert r2.success is True
    assert m._state.players["p1"].is_connected is True


# ---------------------------------------------------------------------------
# TC-18 — Full lifecycle
# ---------------------------------------------------------------------------

async def test_full_lifecycle_disconnect_expiry_reconnect_sitin():
    """TC-18: join → disconnect → expiry → reconnect → SIT_OUT → SIT_IN → WAITING."""
    m = _make_manager(disconnect_reserve_seconds=0.05)
    await _join(m, "p1")
    assert m._state.players["p1"].is_connected is True

    # Disconnect
    await m.disconnect("p1")
    assert m._state.players["p1"].is_connected is False
    assert m._state.players["p1"].disconnect_at is not None
    status_events = m._broadcaster.broadcasts_of_type("PLAYER_STATUS")
    assert any(e.payload["status"] == "disconnected" for e in status_events)

    # Wait for expiry
    await asyncio.sleep(0.2)
    assert m._state.players["p1"].status == PlayerStatus.SIT_OUT

    # Reconnect
    await m.reconnect("p1", "conn-new")
    assert m._state.players["p1"].is_connected is True
    assert m._state.players["p1"].disconnect_at is None
    snaps = m._broadcaster.player_messages_of_type("p1", "STATE_SNAPSHOT")
    assert len(snaps) >= 1

    # Player is SIT_OUT after reconnect
    assert m._state.players["p1"].status == PlayerStatus.SIT_OUT

    # SIT_IN → WAITING
    await m.sit_in("p1")
    assert m._state.players["p1"].status == PlayerStatus.WAITING
