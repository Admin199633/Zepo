"""
Tests for SqlitePersistenceAdapter — restart-safety and all CRUD contracts.

Uses sqlite+aiosqlite with a tmp_path temp file for restart tests
(two sequential adapter instances sharing the same DB file simulate a server restart).

Single-adapter tests use sqlite+aiosqlite:///:memory: for speed.
"""
from __future__ import annotations

import time

import pytest

from backend.auth.models import ClubRole, User
from backend.chat.models import ChatMessage
from backend.clubs.models import Club, ClubMembership
from backend.persistence.sqlite_adapter import (
    SqlitePersistenceAdapter,
    player_stats_table,
)
from backend.stats.models import PlayerStats, StatsDelta
from backend.tables.models import HandSummary, TableRecord
from poker_engine.engine.models import PlayerSession, PlayerStatus, TableConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db() -> SqlitePersistenceAdapter:
    adapter = SqlitePersistenceAdapter("sqlite+aiosqlite:///:memory:")
    await adapter.initialize()
    yield adapter
    await adapter._engine.dispose()


@pytest.fixture
def db_url(tmp_path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path}/test.db"


@pytest.fixture
def alice() -> User:
    return User(id="u1", phone_number="+1000000001", display_name="Alice", created_at=1.0)


@pytest.fixture
def bob() -> User:
    return User(id="u2", phone_number="+1000000002", display_name="Bob", created_at=2.0)


@pytest.fixture
def cfg() -> TableConfig:
    return TableConfig(
        starting_stack=1000, small_blind=10, big_blind=20, turn_timer_seconds=30
    )


@pytest.fixture
def club(alice) -> Club:
    return Club(
        id="club1", name="Test Club", owner_id=alice.id,
        invite_code="INVITE1", created_at=1.0,
        memberships=[
            ClubMembership(club_id="club1", user_id=alice.id,
                           role=ClubRole.OWNER, joined_at=1.0),
        ],
    )


@pytest.fixture
def table_record(club, cfg) -> TableRecord:
    return TableRecord(
        id="tbl1", club_id=club.id, config=cfg,
        created_by=club.owner_id, created_at=1.0,
    )


# ---------------------------------------------------------------------------
# TC-01: Initialize — idempotent DDL
# ---------------------------------------------------------------------------

async def test_initialize_idempotent(db):
    # Second initialize should not raise
    await db.initialize()


# ---------------------------------------------------------------------------
# TC-02/03/04/05: Users
# ---------------------------------------------------------------------------

async def test_user_save_and_get(db, alice):
    await db.save_user(alice)
    fetched = await db.get_user("u1")
    assert fetched is not None
    assert fetched.id == "u1"
    assert fetched.phone_number == "+1000000001"
    assert fetched.display_name == "Alice"
    assert fetched.created_at == 1.0


async def test_user_get_by_phone(db, alice):
    await db.save_user(alice)
    fetched = await db.get_user_by_phone("+1000000001")
    assert fetched is not None
    assert fetched.id == "u1"


async def test_user_nonexistent_returns_none(db):
    assert await db.get_user("no-such") is None
    assert await db.get_user_by_phone("+99999") is None


async def test_user_overwrite_upsert(db, alice):
    await db.save_user(alice)
    alice2 = User(id="u1", phone_number="+1000000001", display_name="Alice2", created_at=1.0)
    await db.save_user(alice2)
    fetched = await db.get_user("u1")
    assert fetched.display_name == "Alice2"


# ---------------------------------------------------------------------------
# TC-06: User restart safety
# ---------------------------------------------------------------------------

async def test_user_restart_safety(db_url, alice):
    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_user(alice)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    fetched_by_id = await db2.get_user("u1")
    fetched_by_phone = await db2.get_user_by_phone("+1000000001")
    await db2._engine.dispose()

    assert fetched_by_id is not None
    assert fetched_by_id.display_name == "Alice"
    assert fetched_by_phone is not None
    assert fetched_by_phone.id == "u1"


# ---------------------------------------------------------------------------
# TC-07/08/09/10/11: Clubs
# ---------------------------------------------------------------------------

async def test_club_save_and_get(db, alice, bob, club):
    membership_bob = ClubMembership(
        club_id="club1", user_id=bob.id, role=ClubRole.MEMBER, joined_at=2.0
    )
    club.memberships.append(membership_bob)
    await db.save_club(club)

    fetched = await db.get_club("club1")
    assert fetched is not None
    assert fetched.id == "club1"
    assert fetched.name == "Test Club"
    assert fetched.invite_code == "INVITE1"
    assert len(fetched.memberships) == 2


async def test_club_get_by_invite(db, club):
    await db.save_club(club)
    fetched = await db.get_club_by_invite("INVITE1")
    assert fetched is not None
    assert fetched.id == "club1"


async def test_club_membership_upsert(db, alice, bob, club):
    await db.save_club(club)
    new_membership = ClubMembership(
        club_id="club1", user_id=bob.id, role=ClubRole.MEMBER, joined_at=2.0
    )
    await db.save_membership(new_membership)
    fetched = await db.get_club("club1")
    assert len(fetched.memberships) == 2
    assert any(m.user_id == bob.id for m in fetched.memberships)


async def test_club_membership_blocked_excluded_from_get_clubs_for_user(db, alice, bob, club):
    blocked = ClubMembership(
        club_id="club1", user_id=bob.id, role=ClubRole.MEMBER,
        joined_at=2.0, is_blocked=True,
    )
    club.memberships.append(blocked)
    await db.save_club(club)
    clubs_for_bob = await db.get_clubs_for_user(bob.id)
    assert len(clubs_for_bob) == 0


async def test_get_clubs_for_user(db, alice, bob, club):
    # bob is active member
    club.memberships.append(
        ClubMembership(club_id="club1", user_id=bob.id, role=ClubRole.MEMBER, joined_at=2.0)
    )
    club2 = Club(
        id="club2", name="Club Two", owner_id=alice.id,
        invite_code="INVITE2", created_at=2.0,
        memberships=[
            ClubMembership(club_id="club2", user_id=alice.id, role=ClubRole.OWNER, joined_at=1.0),
            ClubMembership(club_id="club2", user_id=bob.id, role=ClubRole.MEMBER, joined_at=2.0),
        ],
    )
    await db.save_club(club)
    await db.save_club(club2)
    clubs = await db.get_clubs_for_user(bob.id)
    club_ids = {c.id for c in clubs}
    assert "club1" in club_ids
    assert "club2" in club_ids


# ---------------------------------------------------------------------------
# TC-12: Club restart safety
# ---------------------------------------------------------------------------

async def test_club_restart_safety(db_url, club, bob):
    club.memberships.append(
        ClubMembership(club_id="club1", user_id=bob.id, role=ClubRole.MEMBER, joined_at=2.0)
    )
    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_club(club)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    fetched = await db2.get_club("club1")
    by_invite = await db2.get_club_by_invite("INVITE1")
    clubs_for_bob = await db2.get_clubs_for_user(bob.id)
    await db2._engine.dispose()

    assert fetched is not None
    assert len(fetched.memberships) == 2
    assert by_invite is not None
    assert any(c.id == "club1" for c in clubs_for_bob)


# ---------------------------------------------------------------------------
# TC-13/14/15: Tables
# ---------------------------------------------------------------------------

async def test_table_save_and_get(db, table_record):
    await db.save_table(table_record)
    fetched = await db.get_table("tbl1")
    assert fetched is not None
    assert fetched.id == "tbl1"
    assert fetched.config.starting_stack == 1000
    assert fetched.config.small_blind == 10
    assert fetched.config.big_blind == 20
    assert fetched.config.turn_timer_seconds == 30


async def test_table_get_by_club(db, table_record):
    await db.save_table(table_record)
    fetched = await db.get_club_table("club1")
    assert fetched is not None
    assert fetched.id == "tbl1"


async def test_table_nonexistent_returns_none(db):
    assert await db.get_table("no-such") is None
    assert await db.get_club_table("no-such-club") is None


async def test_table_restart_safety(db_url, table_record):
    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_table(table_record)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    fetched = await db2.get_table("tbl1")
    await db2._engine.dispose()

    assert fetched is not None
    assert fetched.config.starting_stack == 1000
    assert fetched.config.big_blind == 20


# ---------------------------------------------------------------------------
# TC-16/17/18/19: Hand History
# ---------------------------------------------------------------------------

def _make_summary(hand_id: str, hand_number: int, ts: float) -> HandSummary:
    return HandSummary(
        hand_id=hand_id,
        table_id="tbl1",
        club_id="club1",
        hand_number=hand_number,
        phase_reached="RIVER",
        winner_ids=["u1"],
        pot_total=100,
        player_ids=["u1", "u2"],
        stacks_before={"u1": 1000, "u2": 1000},
        stacks_after={"u1": 1100, "u2": 900},
        community_cards=["Ah", "Kd", "Qc", "Js", "Tc"],
        timestamp=ts,
    )


async def test_hand_history_save_and_retrieve(db):
    for i in range(3):
        await db.save_hand_summary(_make_summary(f"h{i}", i + 1, float(i)))
    history = await db.get_hand_history("tbl1")
    assert len(history) == 3
    # Chronological order
    assert history[0].hand_number == 1
    assert history[1].hand_number == 2
    assert history[2].hand_number == 3


async def test_hand_history_limit(db):
    for i in range(60):
        await db.save_hand_summary(_make_summary(f"h{i}", i + 1, float(i)))
    history = await db.get_hand_history("tbl1", limit=50)
    assert len(history) == 50


async def test_hand_history_json_fields_roundtrip(db):
    summary = _make_summary("hX", 1, 1.0)
    summary.winner_ids = ["u1", "u3"]
    summary.community_cards = ["2h", "3d", "4c"]
    summary.stacks_before = {"u1": 500, "u2": 700}
    await db.save_hand_summary(summary)
    history = await db.get_hand_history("tbl1")
    h = history[0]
    assert h.winner_ids == ["u1", "u3"]
    assert h.community_cards == ["2h", "3d", "4c"]
    assert h.stacks_before == {"u1": 500, "u2": 700}


async def test_hand_history_restart_safety(db_url):
    summary = _make_summary("h1", 1, 1.0)

    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_hand_summary(summary)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    history = await db2.get_hand_history("tbl1")
    await db2._engine.dispose()

    assert len(history) == 1
    assert history[0].hand_id == "h1"
    assert history[0].pot_total == 100


# ---------------------------------------------------------------------------
# TC-20/21/22/23/24: Stats
# ---------------------------------------------------------------------------

async def test_stats_initial_accumulation(db):
    delta = StatsDelta(hands_played_delta=1, wins_delta=1, chips_won=500, chips_lost=0)
    await db.upsert_player_stats("club1", "u1", "Alice", delta)
    stats = await db.get_player_stats("club1", "u1")
    assert stats is not None
    assert stats.hands_played == 1
    assert stats.wins == 1
    assert stats.total_won == 500
    assert stats.total_lost == 0


async def test_stats_cumulative_accumulation(db):
    d1 = StatsDelta(hands_played_delta=1, wins_delta=1, chips_won=300, chips_lost=0)
    d2 = StatsDelta(hands_played_delta=1, wins_delta=0, chips_won=0, chips_lost=200)
    d3 = StatsDelta(hands_played_delta=1, wins_delta=1, chips_won=150, chips_lost=0)
    await db.upsert_player_stats("club1", "u1", "Alice", d1)
    await db.upsert_player_stats("club1", "u1", "Alice", d2)
    await db.upsert_player_stats("club1", "u1", "Alice", d3)
    stats = await db.get_player_stats("club1", "u1")
    assert stats.hands_played == 3
    assert stats.wins == 2
    assert stats.total_won == 450
    assert stats.total_lost == 200


async def test_stats_schema_column_names():
    """TC-22: Directly verify column names match the Python model, not the old scaffold."""
    col_names = {col.name for col in player_stats_table.columns}
    assert "wins" in col_names, "Expected 'wins' column (not 'hands_won')"
    assert "total_won" in col_names, "Expected 'total_won' column (not 'total_winnings')"
    assert "total_lost" in col_names, "Expected 'total_lost' column (not 'biggest_pot')"
    assert "hands_won" not in col_names
    assert "total_winnings" not in col_names
    assert "biggest_pot" not in col_names


async def test_stats_restart_safety(db_url):
    d1 = StatsDelta(hands_played_delta=2, wins_delta=1, chips_won=400, chips_lost=100)

    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.upsert_player_stats("club1", "u1", "Alice", d1)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    stats = await db2.get_player_stats("club1", "u1")
    await db2._engine.dispose()

    assert stats is not None
    assert stats.hands_played == 2
    assert stats.wins == 1
    assert stats.total_won == 400
    assert stats.total_lost == 100


async def test_leaderboard_order(db):
    await db.upsert_player_stats("club1", "u1", "Alice",
                                  StatsDelta(hands_played_delta=3, wins_delta=3, chips_won=600, chips_lost=0))
    await db.upsert_player_stats("club1", "u2", "Bob",
                                  StatsDelta(hands_played_delta=3, wins_delta=1, chips_won=100, chips_lost=0))
    await db.upsert_player_stats("club1", "u3", "Carol",
                                  StatsDelta(hands_played_delta=3, wins_delta=2, chips_won=300, chips_lost=0))
    board = await db.get_leaderboard("club1")
    assert board[0].user_id == "u1"  # 3 wins
    assert board[1].user_id == "u3"  # 2 wins
    assert board[2].user_id == "u2"  # 1 win


# ---------------------------------------------------------------------------
# TC-25/26/27: Game Snapshots
# ---------------------------------------------------------------------------

async def test_snapshot_save_and_load(db):
    snap = {"phase": "FLOP", "players": {"u1": {"stack": 980}}}
    await db.save_game_state_snapshot("tbl1", snap)
    loaded = await db.load_game_state_snapshot("tbl1")
    assert loaded is not None
    assert loaded["phase"] == "FLOP"
    assert loaded["players"]["u1"]["stack"] == 980


async def test_snapshot_deck_guard(db):
    """TC-26: A snapshot with a top-level 'deck' key must be rejected."""
    snap = {"deck": ["Ah", "Kd"], "phase": "PRE_FLOP"}
    with pytest.raises(AssertionError):
        await db.save_game_state_snapshot("tbl1", snap)


async def test_snapshot_deck_nested_stripped(db):
    """TC-26 variant: deck inside 'hand' sub-dict is stripped, not rejected."""
    snap = {"hand": {"deck": ["Ah", "Kd"], "pot": 100}, "phase": "FLOP"}
    await db.save_game_state_snapshot("tbl1", snap)
    loaded = await db.load_game_state_snapshot("tbl1")
    assert "deck" not in loaded.get("hand", {})
    assert loaded["hand"]["pot"] == 100


async def test_snapshot_none_for_missing(db):
    assert await db.load_game_state_snapshot("no-such") is None


async def test_snapshot_restart_safety(db_url):
    snap = {"phase": "TURN", "hand_number": 3}

    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_game_state_snapshot("tbl1", snap)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    loaded = await db2.load_game_state_snapshot("tbl1")
    await db2._engine.dispose()

    assert loaded is not None
    assert loaded["phase"] == "TURN"
    assert loaded["hand_number"] == 3


# ---------------------------------------------------------------------------
# TC-28/29/30/31: Player Sessions
# ---------------------------------------------------------------------------

def _make_session(user_id: str, seat: int, stack: int = 1000) -> PlayerSession:
    return PlayerSession(
        user_id=user_id,
        display_name=f"Player{user_id}",
        seat_index=seat,
        stack=stack,
        status=PlayerStatus.ACTIVE,
        timeout_count=0,
        is_connected=True,
        disconnect_at=None,
    )


async def test_player_session_save_and_load(db):
    s1 = _make_session("u1", 0)
    s2 = _make_session("u2", 1, stack=850)
    await db.save_player_session("tbl1", s1)
    await db.save_player_session("tbl1", s2)

    sessions = await db.load_player_sessions("tbl1")
    assert len(sessions) == 2
    by_uid = {s.user_id: s for s in sessions}
    assert by_uid["u1"].seat_index == 0
    assert by_uid["u2"].stack == 850
    assert by_uid["u1"].status == PlayerStatus.ACTIVE
    assert by_uid["u1"].is_connected is True


async def test_player_session_delete(db):
    await db.save_player_session("tbl1", _make_session("u1", 0))
    await db.save_player_session("tbl1", _make_session("u2", 1))
    await db.delete_player_session("tbl1", "u1")
    sessions = await db.load_player_sessions("tbl1")
    assert len(sessions) == 1
    assert sessions[0].user_id == "u2"


async def test_player_session_status_enum_roundtrip(db):
    """TC-30: PlayerStatus enum must be reconstructed correctly."""
    session = PlayerSession(
        user_id="u1", display_name="Alice", seat_index=0, stack=1000,
        status=PlayerStatus.SIT_OUT,
        timeout_count=2, is_connected=False, disconnect_at=999.0,
    )
    await db.save_player_session("tbl1", session)
    sessions = await db.load_player_sessions("tbl1")
    assert len(sessions) == 1
    loaded = sessions[0]
    assert loaded.status == PlayerStatus.SIT_OUT
    assert loaded.timeout_count == 2
    assert loaded.is_connected is False
    assert loaded.disconnect_at == 999.0


async def test_player_session_restart_safety(db_url):
    session = _make_session("u1", 2, stack=750)

    db1 = SqlitePersistenceAdapter(db_url)
    await db1.initialize()
    await db1.save_player_session("tbl1", session)
    await db1._engine.dispose()

    db2 = SqlitePersistenceAdapter(db_url)
    await db2.initialize()
    sessions = await db2.load_player_sessions("tbl1")
    await db2._engine.dispose()

    assert len(sessions) == 1
    assert sessions[0].user_id == "u1"
    assert sessions[0].stack == 750
    assert sessions[0].seat_index == 2


# ---------------------------------------------------------------------------
# TC-32/33: Chat
# ---------------------------------------------------------------------------

def _make_msg(msg_id: str, ts: float, is_system: bool = False) -> ChatMessage:
    return ChatMessage(
        id=msg_id, table_id="tbl1", user_id="u1",
        display_name="Alice", message=f"msg-{msg_id}",
        timestamp=ts, is_system=is_system,
    )


async def test_chat_save_and_retrieve(db):
    for i in range(5):
        await db.save_chat_message(_make_msg(f"m{i}", float(i)))
    history = await db.get_chat_history("tbl1")
    assert len(history) == 5
    assert history[0].id == "m0"  # chronological
    assert history[4].id == "m4"


async def test_chat_limit(db):
    for i in range(60):
        await db.save_chat_message(_make_msg(f"m{i}", float(i)))
    history = await db.get_chat_history("tbl1", limit=50)
    assert len(history) == 50


async def test_chat_is_system_roundtrip(db):
    await db.save_chat_message(_make_msg("sys1", 1.0, is_system=True))
    await db.save_chat_message(_make_msg("usr1", 2.0, is_system=False))
    history = await db.get_chat_history("tbl1")
    by_id = {m.id: m for m in history}
    assert by_id["sys1"].is_system is True
    assert by_id["usr1"].is_system is False
