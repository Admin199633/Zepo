"""
Tests for InMemoryPersistenceAdapter — validates all CRUD contracts.
"""
import time
import pytest

from backend.auth.models import ClubRole, User
from backend.chat.models import ChatMessage
from backend.clubs.models import Club, ClubMembership
from backend.persistence.memory import InMemoryPersistenceAdapter
from backend.stats.models import PlayerStats, StatsDelta
from backend.tables.models import HandSummary, TableRecord
from poker_engine.engine.models import PlayerSession, PlayerStatus, TableConfig


@pytest.fixture
def db() -> InMemoryPersistenceAdapter:
    return InMemoryPersistenceAdapter()


@pytest.fixture
def alice() -> User:
    return User(id="u1", phone_number="+972501234567", display_name="Alice", created_at=time.time())


@pytest.fixture
def config() -> TableConfig:
    return TableConfig(starting_stack=1000, small_blind=10, big_blind=20, turn_timer_seconds=30)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class TestUsers:
    async def test_save_and_get(self, db, alice):
        await db.save_user(alice)
        fetched = await db.get_user("u1")
        assert fetched is not None
        assert fetched.id == "u1"
        assert fetched.display_name == "Alice"

    async def test_get_by_phone(self, db, alice):
        await db.save_user(alice)
        fetched = await db.get_user_by_phone("+972501234567")
        assert fetched is not None
        assert fetched.id == "u1"

    async def test_get_nonexistent_returns_none(self, db):
        assert await db.get_user("nope") is None

    async def test_returns_copy_not_reference(self, db, alice):
        await db.save_user(alice)
        fetched = await db.get_user("u1")
        fetched.display_name = "Modified"
        original = await db.get_user("u1")
        assert original.display_name == "Alice"


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------

class TestClubs:
    async def test_save_and_get_club(self, db):
        club = Club(id="c1", name="Test Club", owner_id="u1", invite_code="INV123")
        await db.save_club(club)
        fetched = await db.get_club("c1")
        assert fetched is not None
        assert fetched.name == "Test Club"

    async def test_get_by_invite(self, db):
        club = Club(id="c1", name="Test Club", owner_id="u1", invite_code="INV123")
        await db.save_club(club)
        fetched = await db.get_club_by_invite("INV123")
        assert fetched is not None
        assert fetched.id == "c1"

    async def test_get_clubs_for_user(self, db, alice):
        club = Club(
            id="c1",
            name="Test Club",
            owner_id="u1",
            invite_code="INV123",
            memberships=[
                ClubMembership(club_id="c1", user_id="u1", role=ClubRole.OWNER)
            ],
        )
        await db.save_club(club)
        clubs = await db.get_clubs_for_user("u1")
        assert len(clubs) == 1

    async def test_blocked_user_not_in_clubs(self, db):
        club = Club(
            id="c1",
            name="Test Club",
            owner_id="u1",
            invite_code="INV123",
            memberships=[
                ClubMembership(club_id="c1", user_id="u2", role=ClubRole.MEMBER, is_blocked=True)
            ],
        )
        await db.save_club(club)
        clubs = await db.get_clubs_for_user("u2")
        assert len(clubs) == 0


# ---------------------------------------------------------------------------
# Tables and Hand History
# ---------------------------------------------------------------------------

class TestTables:
    async def test_save_and_get_table(self, db, config):
        table = TableRecord(id="t1", club_id="c1", config=config, created_by="u1")
        await db.save_table(table)
        fetched = await db.get_table("t1")
        assert fetched is not None
        assert fetched.id == "t1"

    async def test_get_club_table(self, db, config):
        table = TableRecord(id="t1", club_id="c1", config=config, created_by="u1")
        await db.save_table(table)
        fetched = await db.get_club_table("c1")
        assert fetched is not None
        assert fetched.id == "t1"

    async def test_hand_history_stores_and_returns_in_order(self, db):
        for i in range(5):
            summary = HandSummary(
                hand_id=f"h{i}",
                table_id="t1",
                club_id="c1",
                hand_number=i + 1,
                phase_reached="SHOWDOWN",
                winner_ids=["u1"],
                pot_total=100,
                player_ids=["u1","u2"],
                stacks_before={},
                stacks_after={},
                community_cards=[],
                timestamp=time.time(),
            )
            await db.save_hand_summary(summary)

        history = await db.get_hand_history("t1", limit=3)
        assert len(history) == 3
        assert history[-1].hand_id == "h4"

    async def test_hand_history_empty_table(self, db):
        history = await db.get_hand_history("nonexistent")
        assert history == []


# ---------------------------------------------------------------------------
# Game State Snapshots
# ---------------------------------------------------------------------------

class TestSnapshots:
    async def test_save_and_load_snapshot(self, db):
        snapshot = {"table_id": "t1", "phase": "PRE_FLOP", "hand": {"pots": []}}
        await db.save_game_state_snapshot("t1", snapshot)
        loaded = await db.load_game_state_snapshot("t1")
        assert loaded is not None
        assert loaded["phase"] == "PRE_FLOP"

    async def test_deck_stripped_from_snapshot(self, db):
        snapshot = {
            "table_id": "t1",
            "hand": {
                "deck": [{"rank":"A","suit":"S"}] * 50,
                "pots": [],
            },
        }
        await db.save_game_state_snapshot("t1", snapshot)
        loaded = await db.load_game_state_snapshot("t1")
        assert "deck" not in loaded["hand"]

    async def test_load_nonexistent_returns_none(self, db):
        assert await db.load_game_state_snapshot("nope") is None


# ---------------------------------------------------------------------------
# Player Sessions
# ---------------------------------------------------------------------------

class TestPlayerSessions:
    async def test_save_and_load_session(self, db):
        session = PlayerSession(
            user_id="u1",
            display_name="Alice",
            seat_index=0,
            stack=950,
            status=PlayerStatus.ACTIVE,
        )
        await db.save_player_session("t1", session)
        sessions = await db.load_player_sessions("t1")
        assert len(sessions) == 1
        assert sessions[0].stack == 950

    async def test_delete_session(self, db):
        session = PlayerSession(
            user_id="u1",
            display_name="Alice",
            seat_index=0,
            stack=950,
            status=PlayerStatus.ACTIVE,
        )
        await db.save_player_session("t1", session)
        await db.delete_player_session("t1", "u1")
        sessions = await db.load_player_sessions("t1")
        assert len(sessions) == 0

    async def test_update_session_stack(self, db):
        session = PlayerSession(
            user_id="u1",
            display_name="Alice",
            seat_index=0,
            stack=1000,
            status=PlayerStatus.ACTIVE,
        )
        await db.save_player_session("t1", session)
        session.stack = 750
        await db.save_player_session("t1", session)
        sessions = await db.load_player_sessions("t1")
        assert sessions[0].stack == 750


# ---------------------------------------------------------------------------
# Stats and Leaderboard
# ---------------------------------------------------------------------------

class TestStats:
    async def test_upsert_creates_new(self, db):
        await db.upsert_player_stats("c1", "u1", "Alice", StatsDelta(wins_delta=1, chips_won=100))
        stats = await db.get_player_stats("c1", "u1")
        assert stats is not None
        assert stats.wins == 1
        assert stats.hands_played == 1

    async def test_upsert_accumulates(self, db):
        await db.upsert_player_stats("c1", "u1", "Alice", StatsDelta(wins_delta=1))
        await db.upsert_player_stats("c1", "u1", "Alice", StatsDelta(wins_delta=1))
        stats = await db.get_player_stats("c1", "u1")
        assert stats.wins == 2
        assert stats.hands_played == 2

    async def test_leaderboard_sorted_by_wins(self, db):
        await db.upsert_player_stats("c1", "u1", "Alice", StatsDelta(wins_delta=3))
        await db.upsert_player_stats("c1", "u2", "Bob",   StatsDelta(wins_delta=5))
        await db.upsert_player_stats("c1", "u3", "Carol", StatsDelta(wins_delta=1))
        board = await db.get_leaderboard("c1")
        assert board[0].user_id == "u2"
        assert board[1].user_id == "u1"
        assert board[2].user_id == "u3"

    async def test_win_rate_calculation(self, db):
        await db.upsert_player_stats("c1", "u1", "Alice", StatsDelta(wins_delta=1))
        await db.upsert_player_stats("c1", "u1", "Alice", StatsDelta(wins_delta=0))
        stats = await db.get_player_stats("c1", "u1")
        assert stats.win_rate == 0.5


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class TestChat:
    async def test_save_and_retrieve_messages(self, db):
        for i in range(3):
            await db.save_chat_message(ChatMessage(
                id=f"m{i}", table_id="t1",
                user_id="u1", display_name="Alice",
                message=f"msg {i}", timestamp=time.time(),
            ))
        history = await db.get_chat_history("t1", limit=10)
        assert len(history) == 3

    async def test_limit_respected(self, db):
        for i in range(10):
            await db.save_chat_message(ChatMessage(
                id=f"m{i}", table_id="t1",
                user_id="u1", display_name="Alice",
                message=f"msg {i}", timestamp=time.time(),
            ))
        history = await db.get_chat_history("t1", limit=5)
        assert len(history) == 5

    async def test_utf8_messages_stored(self, db):
        await db.save_chat_message(ChatMessage(
            id="m1", table_id="t1",
            user_id="u1", display_name="Alice",
            message="שלום עולם", timestamp=time.time(),
        ))
        history = await db.get_chat_history("t1")
        assert history[0].message == "שלום עולם"
