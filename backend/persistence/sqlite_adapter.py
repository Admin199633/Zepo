"""
SqlitePersistenceAdapter — production persistence path.

Implements all PersistenceAdapter methods using SQLAlchemy Core + aiosqlite.

To activate:
  Set USE_SQLITE=true in environment (or .env).
  main.py lifespan will instantiate this adapter instead of InMemoryPersistenceAdapter.

Schema design notes:
  - All primary keys are string UUIDs.
  - Timestamps are REAL (epoch seconds, float).
  - JSON blobs (config, hole_cards, stacks) stored as TEXT columns.
  - No foreign key enforcement in SQLite for performance; enforce in application.
"""
from __future__ import annotations

import copy
import json
import time
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from poker_engine.engine.models import PlayerSession, PlayerStatus, TableConfig

from ..auth.models import ClubRole, User
from ..chat.models import ChatMessage
from ..clubs.models import Club, ClubMembership
from ..stats.models import PlayerStats, StatsDelta
from ..tables.models import HandSummary, TableRecord
from .adapter import PersistenceAdapter


# ---------------------------------------------------------------------------
# SQLAlchemy Core table definitions
# ---------------------------------------------------------------------------

metadata = sa.MetaData()

users_table = sa.Table(
    "users", metadata,
    sa.Column("id",            sa.String,  primary_key=True),
    sa.Column("phone_number",  sa.String,  nullable=True),   # NULL for username-auth users
    sa.Column("display_name",  sa.String,  nullable=False),
    sa.Column("created_at",    sa.Float,   nullable=False),
    sa.Column("username",      sa.String,  nullable=False, server_default=""),
    sa.Column("password_hash", sa.String,  nullable=False, server_default=""),
)

clubs_table = sa.Table(
    "clubs", metadata,
    sa.Column("id",          sa.String, primary_key=True),
    sa.Column("name",        sa.String, nullable=False),
    sa.Column("owner_id",    sa.String, nullable=False),
    sa.Column("invite_code", sa.String, nullable=False, unique=True),
    sa.Column("created_at",  sa.Float,  nullable=False),
)

club_memberships_table = sa.Table(
    "club_memberships", metadata,
    sa.Column("club_id",    sa.String,  primary_key=True),
    sa.Column("user_id",    sa.String,  primary_key=True),
    sa.Column("role",       sa.String,  nullable=False),   # ClubRole.value
    sa.Column("joined_at",  sa.Float,   nullable=False),
    sa.Column("is_blocked", sa.Boolean, nullable=False, default=False),
)

tables_table = sa.Table(
    "tables", metadata,
    sa.Column("id",          sa.String,  primary_key=True),
    sa.Column("club_id",     sa.String,  nullable=False),
    sa.Column("config_json", sa.Text,    nullable=False),   # JSON of TableConfig fields
    sa.Column("created_by",  sa.String,  nullable=False),
    sa.Column("created_at",  sa.Float,   nullable=False),
    sa.Column("is_active",   sa.Boolean, nullable=False, default=True),
)

hand_summaries_table = sa.Table(
    "hand_summaries", metadata,
    sa.Column("hand_id",              sa.String,  primary_key=True),
    sa.Column("table_id",             sa.String,  nullable=False),
    sa.Column("club_id",              sa.String,  nullable=False),
    sa.Column("hand_number",          sa.Integer, nullable=False),
    sa.Column("phase_reached",        sa.String,  nullable=False),
    sa.Column("winner_ids_json",      sa.Text,    nullable=False),   # JSON list[str]
    sa.Column("pot_total",            sa.Integer, nullable=False),
    sa.Column("player_ids_json",      sa.Text,    nullable=False),   # JSON list[str]
    sa.Column("stacks_before_json",   sa.Text,    nullable=False),   # JSON dict[str,int]
    sa.Column("stacks_after_json",    sa.Text,    nullable=False),   # JSON dict[str,int]
    sa.Column("community_cards_json", sa.Text,    nullable=False),   # JSON list[str]
    sa.Column("timestamp",            sa.Float,   nullable=False),
)

game_snapshots_table = sa.Table(
    "game_snapshots", metadata,
    sa.Column("table_id",      sa.String, primary_key=True),
    sa.Column("snapshot_json", sa.Text,   nullable=False),   # JSON; deck NEVER included
    sa.Column("updated_at",    sa.Float,  nullable=False),
)

player_sessions_table = sa.Table(
    "player_sessions", metadata,
    sa.Column("table_id",      sa.String,  primary_key=True),
    sa.Column("user_id",       sa.String,  primary_key=True),
    sa.Column("display_name",  sa.String,  nullable=False),
    sa.Column("seat_index",    sa.Integer, nullable=False),
    sa.Column("stack",         sa.Integer, nullable=False),
    sa.Column("status",        sa.String,  nullable=False),   # PlayerStatus.value
    sa.Column("timeout_count", sa.Integer, nullable=False, default=0),
    sa.Column("is_connected",  sa.Boolean, nullable=False),
    sa.Column("disconnect_at", sa.Float,   nullable=True),
)

player_stats_table = sa.Table(
    "player_stats", metadata,
    sa.Column("club_id",      sa.String,  primary_key=True),
    sa.Column("user_id",      sa.String,  primary_key=True),
    sa.Column("display_name", sa.String,  nullable=False),
    sa.Column("hands_played", sa.Integer, nullable=False, default=0),
    sa.Column("wins",         sa.Integer, nullable=False, default=0),
    sa.Column("total_won",    sa.Integer, nullable=False, default=0),
    sa.Column("total_lost",   sa.Integer, nullable=False, default=0),
)

chat_messages_table = sa.Table(
    "chat_messages", metadata,
    sa.Column("id",           sa.String,  primary_key=True),
    sa.Column("table_id",     sa.String,  nullable=False),
    sa.Column("user_id",      sa.String,  nullable=False),
    sa.Column("display_name", sa.String,  nullable=False),
    sa.Column("message",      sa.Text,    nullable=False),
    sa.Column("timestamp",    sa.Float,   nullable=False),
    sa.Column("is_system",    sa.Boolean, nullable=False, default=False),
)


# ---------------------------------------------------------------------------
# Adapter implementation
# ---------------------------------------------------------------------------

class SqlitePersistenceAdapter(PersistenceAdapter):
    """
    Production SQLite adapter.
    Uses SQLAlchemy Core + aiosqlite for fully async non-blocking I/O.
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Optional[AsyncEngine] = None

    async def initialize(self) -> None:
        """
        Create engine and run CREATE TABLE IF NOT EXISTS for all tables.
        Migrates the users table to the new schema if needed (adds username /
        password_hash columns, drops the old phone_number UNIQUE constraint in
        favour of partial unique indexes). Idempotent.
        """
        self._engine = create_async_engine(self._database_url, echo=False)
        async with self._engine.begin() as conn:
            # Detect whether the users table needs migration
            res = await conn.execute(sa.text("PRAGMA table_info(users)"))
            users_cols = {row[1] for row in res.fetchall()}
            needs_migration = bool(users_cols) and "username" not in users_cols

            if needs_migration:
                # Rename old table, recreate with new schema, copy data, drop old
                await conn.execute(sa.text("ALTER TABLE users RENAME TO _users_old"))

            await conn.run_sync(metadata.create_all)

            if needs_migration:
                await conn.execute(sa.text(
                    "INSERT INTO users "
                    "(id, phone_number, display_name, created_at, username, password_hash) "
                    "SELECT id, phone_number, display_name, created_at, '', '' "
                    "FROM _users_old"
                ))
                await conn.execute(sa.text("DROP TABLE _users_old"))

            # Partial unique indexes (idempotent — replace old blanket unique index)
            await conn.execute(sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone "
                "ON users (phone_number) "
                "WHERE phone_number IS NOT NULL AND phone_number != ''"
            ))
            await conn.execute(sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username "
                "ON users (username) WHERE username != ''"
            ))

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def save_user(self, user: User) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                users_table.insert().prefix_with("OR REPLACE").values(
                    id=user.id,
                    phone_number=user.phone_number or None,  # "" → NULL (avoids UNIQUE conflict)
                    display_name=user.display_name,
                    created_at=user.created_at,
                    username=user.username,
                    password_hash=user.password_hash,
                )
            )

    def _row_to_user(self, row) -> User:
        return User(
            id=row.id,
            phone_number=row.phone_number or "",
            display_name=row.display_name,
            created_at=row.created_at,
            username=row.username or "",
            password_hash=row.password_hash or "",
        )

    async def get_user(self, user_id: str) -> Optional[User]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                users_table.select().where(users_table.c.id == user_id)
            )).first()
        return self._row_to_user(row) if row else None

    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                users_table.select().where(users_table.c.phone_number == phone_number)
            )).first()
        return self._row_to_user(row) if row else None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                users_table.select().where(users_table.c.username == username)
            )).first()
        return self._row_to_user(row) if row else None

    # ------------------------------------------------------------------
    # Clubs
    # ------------------------------------------------------------------

    async def save_club(self, club: Club) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                clubs_table.insert().prefix_with("OR REPLACE").values(
                    id=club.id,
                    name=club.name,
                    owner_id=club.owner_id,
                    invite_code=club.invite_code,
                    created_at=club.created_at,
                )
            )
            for m in club.memberships:
                await conn.execute(
                    club_memberships_table.insert().prefix_with("OR REPLACE").values(
                        club_id=m.club_id,
                        user_id=m.user_id,
                        role=m.role.value,
                        joined_at=m.joined_at,
                        is_blocked=m.is_blocked,
                    )
                )

    async def get_club(self, club_id: str) -> Optional[Club]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                clubs_table.select().where(clubs_table.c.id == club_id)
            )).first()
            if row is None:
                return None
            m_rows = (await conn.execute(
                club_memberships_table.select().where(
                    club_memberships_table.c.club_id == club_id
                )
            )).fetchall()
        club = Club(
            id=row.id,
            name=row.name,
            owner_id=row.owner_id,
            invite_code=row.invite_code,
            created_at=row.created_at,
        )
        club.memberships = [
            ClubMembership(
                club_id=r.club_id,
                user_id=r.user_id,
                role=ClubRole(r.role),
                joined_at=r.joined_at,
                is_blocked=r.is_blocked,
            )
            for r in m_rows
        ]
        return club

    async def get_club_by_invite(self, invite_code: str) -> Optional[Club]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                clubs_table.select().where(clubs_table.c.invite_code == invite_code)
            )).first()
        if row is None:
            return None
        return await self.get_club(row.id)

    async def get_clubs_for_user(self, user_id: str) -> list[Club]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                club_memberships_table.select().where(
                    (club_memberships_table.c.user_id == user_id) &
                    (club_memberships_table.c.is_blocked == False)  # noqa: E712
                )
            )).fetchall()
        clubs = []
        for r in rows:
            club = await self.get_club(r.club_id)
            if club is not None:
                clubs.append(club)
        return clubs

    async def save_membership(self, membership: ClubMembership) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                club_memberships_table.insert().prefix_with("OR REPLACE").values(
                    club_id=membership.club_id,
                    user_id=membership.user_id,
                    role=membership.role.value,
                    joined_at=membership.joined_at,
                    is_blocked=membership.is_blocked,
                )
            )

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    async def save_table(self, table: TableRecord) -> None:
        config_json = json.dumps({
            "starting_stack": table.config.starting_stack,
            "small_blind": table.config.small_blind,
            "big_blind": table.config.big_blind,
            "turn_timer_seconds": table.config.turn_timer_seconds,
        })
        async with self._engine.begin() as conn:
            await conn.execute(
                tables_table.insert().prefix_with("OR REPLACE").values(
                    id=table.id,
                    club_id=table.club_id,
                    config_json=config_json,
                    created_by=table.created_by,
                    created_at=table.created_at,
                    is_active=table.is_active,
                )
            )

    async def get_table(self, table_id: str) -> Optional[TableRecord]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                tables_table.select().where(tables_table.c.id == table_id)
            )).first()
        if row is None:
            return None
        cfg = json.loads(row.config_json)
        return TableRecord(
            id=row.id,
            club_id=row.club_id,
            config=TableConfig(**cfg),
            created_by=row.created_by,
            created_at=row.created_at,
            is_active=row.is_active,
        )

    async def get_club_table(self, club_id: str) -> Optional[TableRecord]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                tables_table.select()
                .where(
                    (tables_table.c.club_id == club_id) &
                    (tables_table.c.is_active == True)  # noqa: E712
                )
                .limit(1)
            )).first()
        if row is None:
            return None
        return await self.get_table(row.id)

    async def save_hand_summary(self, summary: HandSummary) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                hand_summaries_table.insert().values(
                    hand_id=summary.hand_id,
                    table_id=summary.table_id,
                    club_id=summary.club_id,
                    hand_number=summary.hand_number,
                    phase_reached=summary.phase_reached,
                    winner_ids_json=json.dumps(summary.winner_ids),
                    pot_total=summary.pot_total,
                    player_ids_json=json.dumps(summary.player_ids),
                    stacks_before_json=json.dumps(summary.stacks_before),
                    stacks_after_json=json.dumps(summary.stacks_after),
                    community_cards_json=json.dumps(summary.community_cards),
                    timestamp=summary.timestamp,
                )
            )

    async def get_hand_history(
        self, table_id: str, limit: int = 50
    ) -> list[HandSummary]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                hand_summaries_table.select()
                .where(hand_summaries_table.c.table_id == table_id)
                .order_by(hand_summaries_table.c.timestamp.asc())
                .limit(limit)
            )).fetchall()
        return [
            HandSummary(
                hand_id=r.hand_id,
                table_id=r.table_id,
                club_id=r.club_id,
                hand_number=r.hand_number,
                phase_reached=r.phase_reached,
                winner_ids=json.loads(r.winner_ids_json),
                pot_total=r.pot_total,
                player_ids=json.loads(r.player_ids_json),
                stacks_before=json.loads(r.stacks_before_json),
                stacks_after=json.loads(r.stacks_after_json),
                community_cards=json.loads(r.community_cards_json),
                timestamp=r.timestamp,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Game State Snapshots  (deck NEVER included)
    # ------------------------------------------------------------------

    async def save_game_state_snapshot(
        self, table_id: str, snapshot: dict
    ) -> None:
        # Strip deck defensively (caller should have already done this)
        if "hand" in snapshot and snapshot["hand"] is not None:
            snapshot = copy.deepcopy(snapshot)
            snapshot["hand"].pop("deck", None)
        assert "deck" not in snapshot, "deck must never be persisted"
        async with self._engine.begin() as conn:
            await conn.execute(
                game_snapshots_table.insert().prefix_with("OR REPLACE").values(
                    table_id=table_id,
                    snapshot_json=json.dumps(snapshot),
                    updated_at=time.time(),
                )
            )

    async def load_game_state_snapshot(
        self, table_id: str
    ) -> Optional[dict]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                game_snapshots_table.select().where(
                    game_snapshots_table.c.table_id == table_id
                )
            )).first()
        return json.loads(row.snapshot_json) if row else None

    # ------------------------------------------------------------------
    # Player Sessions
    # ------------------------------------------------------------------

    async def save_player_session(
        self, table_id: str, session: PlayerSession
    ) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                player_sessions_table.insert().prefix_with("OR REPLACE").values(
                    table_id=table_id,
                    user_id=session.user_id,
                    display_name=session.display_name,
                    seat_index=session.seat_index,
                    stack=session.stack,
                    status=session.status.value,
                    timeout_count=session.timeout_count,
                    is_connected=session.is_connected,
                    disconnect_at=session.disconnect_at,
                )
            )

    async def load_player_sessions(
        self, table_id: str
    ) -> list[PlayerSession]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                player_sessions_table.select().where(
                    player_sessions_table.c.table_id == table_id
                )
            )).fetchall()
        return [
            PlayerSession(
                user_id=r.user_id,
                display_name=r.display_name,
                seat_index=r.seat_index,
                stack=r.stack,
                status=PlayerStatus(r.status),
                timeout_count=r.timeout_count,
                is_connected=r.is_connected,
                disconnect_at=r.disconnect_at,
            )
            for r in rows
        ]

    async def delete_player_session(
        self, table_id: str, user_id: str
    ) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                player_sessions_table.delete().where(
                    (player_sessions_table.c.table_id == table_id) &
                    (player_sessions_table.c.user_id == user_id)
                )
            )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def upsert_player_stats(
        self, club_id: str, user_id: str, display_name: str, delta: StatsDelta
    ) -> None:
        async with self._engine.begin() as conn:
            # Ensure row exists
            await conn.execute(
                player_stats_table.insert().prefix_with("OR IGNORE").values(
                    club_id=club_id,
                    user_id=user_id,
                    display_name=display_name,
                    hands_played=0,
                    wins=0,
                    total_won=0,
                    total_lost=0,
                )
            )
            # Apply delta
            await conn.execute(
                player_stats_table.update()
                .where(
                    (player_stats_table.c.club_id == club_id) &
                    (player_stats_table.c.user_id == user_id)
                )
                .values(
                    display_name=display_name,
                    hands_played=player_stats_table.c.hands_played + delta.hands_played_delta,
                    wins=player_stats_table.c.wins + delta.wins_delta,
                    total_won=player_stats_table.c.total_won + delta.chips_won,
                    total_lost=player_stats_table.c.total_lost + delta.chips_lost,
                )
            )

    async def get_player_stats(
        self, club_id: str, user_id: str
    ) -> Optional[PlayerStats]:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                player_stats_table.select().where(
                    (player_stats_table.c.club_id == club_id) &
                    (player_stats_table.c.user_id == user_id)
                )
            )).first()
        if row is None:
            return None
        return PlayerStats(
            user_id=row.user_id,
            club_id=row.club_id,
            display_name=row.display_name,
            hands_played=row.hands_played,
            wins=row.wins,
            total_won=row.total_won,
            total_lost=row.total_lost,
        )

    async def get_leaderboard(
        self, club_id: str, limit: int = 20
    ) -> list[PlayerStats]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                player_stats_table.select()
                .where(player_stats_table.c.club_id == club_id)
                .order_by(player_stats_table.c.wins.desc())
                .limit(limit)
            )).fetchall()
        return [
            PlayerStats(
                user_id=r.user_id,
                club_id=r.club_id,
                display_name=r.display_name,
                hands_played=r.hands_played,
                wins=r.wins,
                total_won=r.total_won,
                total_lost=r.total_lost,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def save_chat_message(self, message: ChatMessage) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                chat_messages_table.insert().values(
                    id=message.id,
                    table_id=message.table_id,
                    user_id=message.user_id,
                    display_name=message.display_name,
                    message=message.message,
                    timestamp=message.timestamp,
                    is_system=message.is_system,
                )
            )

    async def get_chat_history(
        self, table_id: str, limit: int = 50
    ) -> list[ChatMessage]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                chat_messages_table.select()
                .where(chat_messages_table.c.table_id == table_id)
                .order_by(chat_messages_table.c.timestamp.asc())
                .limit(limit)
            )).fetchall()
        return [
            ChatMessage(
                id=r.id,
                table_id=r.table_id,
                user_id=r.user_id,
                display_name=r.display_name,
                message=r.message,
                timestamp=r.timestamp,
                is_system=r.is_system,
            )
            for r in rows
        ]
