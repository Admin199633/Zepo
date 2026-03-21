"""
In-memory persistence adapter.
Thread/task-safe for single-process asyncio use (no actual locking needed
since asyncio is cooperative — no two coroutines can run simultaneously).

Used for:
  - Tests (fast, isolated)
  - Development (no DB setup required)
  - All Phase 2 work
"""
from __future__ import annotations

import copy
from typing import Optional

from poker_engine.engine.models import PlayerSession

from ..auth.models import User
from ..clubs.models import Club, ClubMembership
from ..tables.models import HandSummary, TableRecord
from ..stats.models import PlayerStats, StatsDelta
from ..chat.models import ChatMessage
from .adapter import PersistenceAdapter


class InMemoryPersistenceAdapter(PersistenceAdapter):

    def __init__(self) -> None:
        self._users:            dict[str, User]             = {}   # user_id → User
        self._users_by_phone:   dict[str, str]              = {}   # phone → user_id
        self._users_by_username: dict[str, str]             = {}   # username → user_id
        self._clubs:           dict[str, Club]             = {}   # club_id → Club
        self._clubs_by_invite: dict[str, str]              = {}   # invite_code → club_id
        self._tables:          dict[str, TableRecord]      = {}   # table_id → TableRecord
        self._club_tables:     dict[str, str]              = {}   # club_id → table_id
        self._hand_history:    dict[str, list[HandSummary]]= {}   # table_id → [HandSummary]
        self._snapshots:       dict[str, dict]             = {}   # table_id → snapshot dict
        self._sessions:        dict[str, dict[str, PlayerSession]] = {}  # table_id → {uid → session}
        self._stats:           dict[str, dict[str, PlayerStats]]   = {}  # club_id → {uid → stats}
        self._chat:            dict[str, list[ChatMessage]] = {}  # table_id → [msg]

    # -----------------------------------------------------------------------
    # Users
    # -----------------------------------------------------------------------

    async def save_user(self, user: User) -> None:
        self._users[user.id] = copy.deepcopy(user)
        if user.phone_number:
            self._users_by_phone[user.phone_number] = user.id
        if user.username:
            self._users_by_username[user.username] = user.id

    async def get_user(self, user_id: str) -> Optional[User]:
        u = self._users.get(user_id)
        return copy.deepcopy(u) if u else None

    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        uid = self._users_by_phone.get(phone_number)
        if uid is None:
            return None
        return await self.get_user(uid)

    async def get_user_by_username(self, username: str) -> Optional[User]:
        uid = self._users_by_username.get(username)
        if uid is None:
            return None
        return await self.get_user(uid)

    # -----------------------------------------------------------------------
    # Clubs
    # -----------------------------------------------------------------------

    async def save_club(self, club: Club) -> None:
        self._clubs[club.id] = copy.deepcopy(club)
        self._clubs_by_invite[club.invite_code] = club.id

    async def get_club(self, club_id: str) -> Optional[Club]:
        c = self._clubs.get(club_id)
        return copy.deepcopy(c) if c else None

    async def get_club_by_invite(self, invite_code: str) -> Optional[Club]:
        club_id = self._clubs_by_invite.get(invite_code)
        if club_id is None:
            return None
        return await self.get_club(club_id)

    async def get_clubs_for_user(self, user_id: str) -> list[Club]:
        result = []
        for club in self._clubs.values():
            if any(m.user_id == user_id and not m.is_blocked for m in club.memberships):
                result.append(copy.deepcopy(club))
        return result

    async def save_membership(self, membership: ClubMembership) -> None:
        club = self._clubs.get(membership.club_id)
        if club is None:
            return
        # Replace existing membership if present
        club.memberships = [
            m for m in club.memberships if m.user_id != membership.user_id
        ]
        club.memberships.append(copy.deepcopy(membership))

    # -----------------------------------------------------------------------
    # Tables
    # -----------------------------------------------------------------------

    async def save_table(self, table: TableRecord) -> None:
        self._tables[table.id] = copy.deepcopy(table)
        self._club_tables[table.club_id] = table.id

    async def get_table(self, table_id: str) -> Optional[TableRecord]:
        t = self._tables.get(table_id)
        return copy.deepcopy(t) if t else None

    async def get_club_table(self, club_id: str) -> Optional[TableRecord]:
        table_id = self._club_tables.get(club_id)
        if table_id is None:
            return None
        return await self.get_table(table_id)

    async def save_hand_summary(self, summary: HandSummary) -> None:
        self._hand_history.setdefault(summary.table_id, []).append(
            copy.deepcopy(summary)
        )

    async def get_hand_history(
        self, table_id: str, limit: int = 50
    ) -> list[HandSummary]:
        history = self._hand_history.get(table_id, [])
        return [copy.deepcopy(h) for h in history[-limit:]]

    # -----------------------------------------------------------------------
    # Game State Snapshots
    # -----------------------------------------------------------------------

    async def save_game_state_snapshot(
        self, table_id: str, snapshot: dict
    ) -> None:
        # Defensive: ensure deck is never stored
        if "hand" in snapshot and snapshot["hand"] is not None:
            snapshot = copy.deepcopy(snapshot)
            snapshot["hand"].pop("deck", None)
        self._snapshots[table_id] = snapshot

    async def load_game_state_snapshot(
        self, table_id: str
    ) -> Optional[dict]:
        snap = self._snapshots.get(table_id)
        return copy.deepcopy(snap) if snap else None

    # -----------------------------------------------------------------------
    # Player Sessions
    # -----------------------------------------------------------------------

    async def save_player_session(
        self, table_id: str, session: PlayerSession
    ) -> None:
        self._sessions.setdefault(table_id, {})[session.user_id] = (
            copy.deepcopy(session)
        )

    async def load_player_sessions(
        self, table_id: str
    ) -> list[PlayerSession]:
        return [
            copy.deepcopy(s)
            for s in self._sessions.get(table_id, {}).values()
        ]

    async def delete_player_session(
        self, table_id: str, user_id: str
    ) -> None:
        self._sessions.get(table_id, {}).pop(user_id, None)

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    async def upsert_player_stats(
        self,
        club_id: str,
        user_id: str,
        display_name: str,
        delta: StatsDelta,
    ) -> None:
        club_stats = self._stats.setdefault(club_id, {})
        existing = club_stats.get(user_id)
        if existing is None:
            existing = PlayerStats(
                user_id=user_id, club_id=club_id, display_name=display_name
            )
            club_stats[user_id] = existing
        existing.display_name = display_name
        existing.hands_played += delta.hands_played_delta
        existing.wins += delta.wins_delta
        existing.total_won += delta.chips_won
        existing.total_lost += delta.chips_lost

    async def get_player_stats(
        self, club_id: str, user_id: str
    ) -> Optional[PlayerStats]:
        stats = self._stats.get(club_id, {}).get(user_id)
        return copy.deepcopy(stats) if stats else None

    async def get_leaderboard(
        self, club_id: str, limit: int = 20
    ) -> list[PlayerStats]:
        club_stats = self._stats.get(club_id, {})
        sorted_stats = sorted(
            club_stats.values(), key=lambda s: s.wins, reverse=True
        )
        return [copy.deepcopy(s) for s in sorted_stats[:limit]]

    # -----------------------------------------------------------------------
    # Chat
    # -----------------------------------------------------------------------

    async def save_chat_message(self, message: ChatMessage) -> None:
        self._chat.setdefault(message.table_id, []).append(
            copy.deepcopy(message)
        )

    async def get_chat_history(
        self, table_id: str, limit: int = 50
    ) -> list[ChatMessage]:
        msgs = self._chat.get(table_id, [])
        return [copy.deepcopy(m) for m in msgs[-limit:]]
