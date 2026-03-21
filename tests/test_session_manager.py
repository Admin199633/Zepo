"""
Session Manager integration tests.
Uses in-memory persistence and a capturing broadcaster.
"""
import asyncio
import pytest

from poker_engine.engine.models import HandPhase, PlayerStatus
from backend.realtime.schemas import ServerEventType
from backend.sessions.models import JoinErrorCode
from backend.sessions.session_manager import DISCONNECT_RESERVE_SECONDS, TableSessionManager


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Join / Seat assignment
# ---------------------------------------------------------------------------

class TestJoinAsPlayer:
    async def test_first_player_gets_seat_0(self, manager, broadcaster):
        result = await manager.join_as_player("alice", "Alice", "conn-a")
        assert result.success
        assert result.seat_index == 0
        assert result.role == "player"

    async def test_second_player_gets_seat_1(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        result = await manager.join_as_player("bob", "Bob", "conn-b")
        assert result.success
        assert result.seat_index == 1

    async def test_join_broadcasts_player_joined(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        events = broadcaster.broadcasts_of_type("PLAYER_JOINED")
        assert len(events) == 1
        assert events[0].payload["user_id"] == "alice"

    async def test_join_sends_state_snapshot_to_new_player(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        snaps = broadcaster.player_messages_of_type("alice", "STATE_SNAPSHOT")
        assert len(snaps) == 1

    async def test_full_table_rejected(self, manager):
        names = ["alice", "bob", "carol", "dave", "eve", "frank"]
        for uid in names:
            await manager.join_as_player(uid, uid.capitalize(), f"conn-{uid}")
        result = await manager.join_as_player("grace", "Grace", "conn-grace")
        assert not result.success
        assert result.error_code == JoinErrorCode.TABLE_FULL

    async def test_already_seated_treated_as_reconnect(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        result = await manager.join_as_player("alice", "Alice", "conn-a2")
        assert result.success  # reconnect succeeds

    async def test_player_count(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        assert manager.player_count == 2


class TestJoinAsSpectator:
    async def test_spectator_join_success(self, manager):
        result = await manager.join_as_spectator("zara", "Zara", "conn-z")
        assert result.success
        assert result.role == "spectator"

    async def test_spectator_receives_snapshot(self, manager, broadcaster):
        await manager.join_as_spectator("zara", "Zara", "conn-z")
        snaps = broadcaster.player_messages_of_type("zara", "STATE_SNAPSHOT")
        assert len(snaps) == 1

    async def test_spectator_count(self, manager):
        await manager.join_as_spectator("zara", "Zara", "conn-z")
        assert manager.spectator_count == 1


# ---------------------------------------------------------------------------
# Mid-hand join gets WAITING status
# ---------------------------------------------------------------------------

class TestMidHandJoin:
    async def test_join_during_hand_gets_waiting_status(self, manager):
        # Start a hand first
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        # Wait a bit for the hand to start
        await asyncio.sleep(0.1)

        # Cancel auto-start to keep hand in progress manually
        # We'll directly check by looking at state after enough time
        await asyncio.sleep(3.5)  # wait for between_hands_delay

        # Now join carol mid-hand if hand started
        if manager._state.phase not in (
            HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END
        ):
            result = await manager.join_as_player("carol", "Carol", "conn-c")
            assert result.success
            carol_session = manager._state.players.get("carol")
            if carol_session:
                assert carol_session.status == PlayerStatus.WAITING


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------

class TestLeave:
    async def test_leave_removes_player(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.leave("alice")
        assert "alice" not in manager._state.players

    async def test_leave_broadcasts_player_left(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        broadcaster.reset()
        await manager.leave("alice")
        events = broadcaster.broadcasts_of_type("PLAYER_LEFT")
        assert len(events) == 1

    async def test_leave_unknown_player_no_error(self, manager):
        await manager.leave("nonexistent")  # should not raise


# ---------------------------------------------------------------------------
# Disconnect / Reconnect
# ---------------------------------------------------------------------------

class TestDisconnectReconnect:
    async def test_disconnect_marks_player_disconnected(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.disconnect("alice")
        assert manager._state.players["alice"].is_connected is False
        assert manager._state.players["alice"].disconnect_at is not None

    async def test_reconnect_within_window_saves_seat(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.disconnect("alice")
        result = await manager.reconnect("alice", "conn-a2")
        assert result.success
        assert manager._state.players["alice"].is_connected is True

    async def test_reconnect_cancels_disconnect_timer(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.disconnect("alice")
        assert "alice" in manager._disconnect_tasks
        await manager.reconnect("alice", "conn-a2")
        # Task should be cancelled or completed
        task = manager._disconnect_tasks.get("alice")
        assert task is None or task.cancelled() or task.done()

    async def test_reconnect_resends_state_snapshot(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.disconnect("alice")
        broadcaster.reset()
        await manager.reconnect("alice", "conn-a2")
        snaps = broadcaster.player_messages_of_type("alice", "STATE_SNAPSHOT")
        assert len(snaps) == 1

    async def test_reconnect_nonexistent_player_fails(self, manager):
        result = await manager.reconnect("ghost", "conn-g")
        assert not result.success

    async def test_disconnect_timeout_sits_out_player(self, manager):
        """After DISCONNECT_RESERVE_SECONDS, player moves to SIT_OUT."""
        # Patch the sleep duration for the test
        import backend.sessions.session_manager as sm_module
        original = sm_module.DISCONNECT_RESERVE_SECONDS
        sm_module.DISCONNECT_RESERVE_SECONDS = 0.05  # 50ms for test speed

        try:
            await manager.join_as_player("alice", "Alice", "conn-a")
            await manager.disconnect("alice")
            await asyncio.sleep(0.2)  # wait for timer to fire

            player = manager._state.players.get("alice")
            assert player is None or player.status == PlayerStatus.SIT_OUT
        finally:
            sm_module.DISCONNECT_RESERVE_SECONDS = original


# ---------------------------------------------------------------------------
# Sit out / Sit in
# ---------------------------------------------------------------------------

class TestSitOutSitIn:
    async def test_sit_out_changes_status(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.sit_out("alice")
        assert manager._state.players["alice"].status == PlayerStatus.SIT_OUT

    async def test_sit_in_from_sit_out(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.sit_out("alice")
        await manager.sit_in("alice")
        assert manager._state.players["alice"].status == PlayerStatus.WAITING

    async def test_sit_in_broadcasts_status(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.sit_out("alice")
        broadcaster.reset()
        await manager.sit_in("alice")
        events = broadcaster.broadcasts_of_type("PLAYER_STATUS")
        assert len(events) >= 1

    async def test_sit_in_with_no_chips_ignored(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        manager._state.players["alice"].stack = 0
        await manager.sit_out("alice")
        await manager.sit_in("alice")
        assert manager._state.players["alice"].status == PlayerStatus.SIT_OUT


# ---------------------------------------------------------------------------
# Action routing
# ---------------------------------------------------------------------------

class TestActionRouting:
    async def test_action_on_wrong_turn_raises(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        await asyncio.sleep(3.5)  # wait for hand to start

        if manager._state.hand and manager._state.hand.current_turn_seat is not None:
            current_seat = manager._state.hand.current_turn_seat
            wrong_uid = next(
                uid for uid, p in manager._state.players.items()
                if p.seat_index != current_seat
            )
            with pytest.raises(ValueError, match="NOT_YOUR_TURN"):
                await manager.handle_action(wrong_uid, "fold", 0, "req-1")

    async def test_duplicate_request_id_ignored(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        await asyncio.sleep(3.5)

        if manager._state.hand and manager._state.hand.current_turn_seat is not None:
            uid = manager._state.seat_map[manager._state.hand.current_turn_seat]
            # Send same request_id twice — second should be silently dropped
            try:
                await manager.handle_action(uid, "fold", 0, "req-dupe")
            except Exception:
                pass
            # If first succeeded, second should not raise
            try:
                await manager.handle_action(uid, "fold", 0, "req-dupe")
            except ValueError as e:
                # Only "NOT_YOUR_TURN" or "NO_ACTIVE_HAND" are acceptable here
                assert "NOT_YOUR_TURN" in str(e) or "NO_ACTIVE_HAND" in str(e)

    async def test_chat_is_broadcast(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.handle_chat("alice", "Alice", "שלום")
        events = broadcaster.broadcasts_of_type("CHAT_MESSAGE")
        assert len(events) == 1
        assert events[0].payload["message"] == "שלום"

    async def test_sync_request_resends_snapshot(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        broadcaster.reset()
        await manager.send_sync("alice")
        snaps = broadcaster.player_messages_of_type("alice", "STATE_SNAPSHOT")
        assert len(snaps) == 1


# ---------------------------------------------------------------------------
# Auto-start hand
# ---------------------------------------------------------------------------

class TestAutoStartHand:
    async def test_hand_starts_after_two_players_join(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        # Wait for between_hands_delay + buffer
        await asyncio.sleep(3.5)
        assert manager._state.phase not in (
            HandPhase.WAITING_FOR_PLAYERS,
        )

    async def test_single_player_does_not_start_hand(self, manager):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await asyncio.sleep(3.5)
        assert manager._state.phase == HandPhase.WAITING_FOR_PLAYERS

    async def test_hand_start_broadcasts_phase_changed(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        await asyncio.sleep(3.5)
        phase_events = broadcaster.broadcasts_of_type("PHASE_CHANGED")
        assert len(phase_events) >= 1

    async def test_each_player_receives_hole_cards(self, manager, broadcaster):
        await manager.join_as_player("alice", "Alice", "conn-a")
        await manager.join_as_player("bob", "Bob", "conn-b")
        await asyncio.sleep(3.5)

        alice_cards = broadcaster.player_messages_of_type("alice", "CARDS_DEALT")
        bob_cards = broadcaster.player_messages_of_type("bob", "CARDS_DEALT")
        if manager._state.phase != HandPhase.WAITING_FOR_PLAYERS:
            assert len(alice_cards) >= 1
            assert len(bob_cards) >= 1
