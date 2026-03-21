"""
PersistenceAdapter — abstract interface for all storage operations.

Implementations:
  - InMemoryPersistenceAdapter  (tests + dev)
  - PostgresPersistenceAdapter  (production — to be implemented in Phase 4)

Dependency rule: this module may import from poker_engine.models for
serialization only. It must NOT import from any other backend module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from poker_engine.engine.models import PlayerSession

from ..auth.models import User
from ..clubs.models import Club, ClubMembership
from ..tables.models import HandSummary, TableRecord
from ..stats.models import PlayerStats, StatsDelta
from ..chat.models import ChatMessage


class PersistenceAdapter(ABC):

    # -----------------------------------------------------------------------
    # Users
    # -----------------------------------------------------------------------

    @abstractmethod
    async def save_user(self, user: User) -> None: ...

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    async def get_user_by_phone(self, phone_number: str) -> Optional[User]: ...

    # -----------------------------------------------------------------------
    # Clubs
    # -----------------------------------------------------------------------

    @abstractmethod
    async def save_club(self, club: Club) -> None: ...

    @abstractmethod
    async def get_club(self, club_id: str) -> Optional[Club]: ...

    @abstractmethod
    async def get_club_by_invite(self, invite_code: str) -> Optional[Club]: ...

    @abstractmethod
    async def get_clubs_for_user(self, user_id: str) -> list[Club]: ...

    @abstractmethod
    async def save_membership(self, membership: ClubMembership) -> None: ...

    # -----------------------------------------------------------------------
    # Tables
    # -----------------------------------------------------------------------

    @abstractmethod
    async def save_table(self, table: TableRecord) -> None: ...

    @abstractmethod
    async def get_table(self, table_id: str) -> Optional[TableRecord]: ...

    @abstractmethod
    async def get_club_table(self, club_id: str) -> Optional[TableRecord]: ...

    @abstractmethod
    async def save_hand_summary(self, summary: HandSummary) -> None: ...

    @abstractmethod
    async def get_hand_history(
        self, table_id: str, limit: int = 50
    ) -> list[HandSummary]: ...

    # -----------------------------------------------------------------------
    # Game State Snapshots  (for reconnect + crash recovery)
    # Note: deck is NEVER included in the snapshot.
    # -----------------------------------------------------------------------

    @abstractmethod
    async def save_game_state_snapshot(
        self, table_id: str, snapshot: dict
    ) -> None:
        """
        Persist a serialized (dict) game state snapshot.
        The caller is responsible for stripping the deck before calling.
        """
        ...

    @abstractmethod
    async def load_game_state_snapshot(
        self, table_id: str
    ) -> Optional[dict]: ...

    # -----------------------------------------------------------------------
    # Player Sessions  (seat + stack at hand boundaries)
    # -----------------------------------------------------------------------

    @abstractmethod
    async def save_player_session(
        self, table_id: str, session: PlayerSession
    ) -> None: ...

    @abstractmethod
    async def load_player_sessions(
        self, table_id: str
    ) -> list[PlayerSession]: ...

    @abstractmethod
    async def delete_player_session(
        self, table_id: str, user_id: str
    ) -> None: ...

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    @abstractmethod
    async def upsert_player_stats(
        self, club_id: str, user_id: str, display_name: str, delta: StatsDelta
    ) -> None: ...

    @abstractmethod
    async def get_player_stats(
        self, club_id: str, user_id: str
    ) -> Optional[PlayerStats]: ...

    @abstractmethod
    async def get_leaderboard(
        self, club_id: str, limit: int = 20
    ) -> list[PlayerStats]: ...

    # -----------------------------------------------------------------------
    # Chat
    # -----------------------------------------------------------------------

    @abstractmethod
    async def save_chat_message(self, message: ChatMessage) -> None: ...

    @abstractmethod
    async def get_chat_history(
        self, table_id: str, limit: int = 50
    ) -> list[ChatMessage]: ...
