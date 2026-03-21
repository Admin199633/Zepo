"""
Realtime WebSocket message schemas.

All messages are validated with Pydantic v2.

Envelope structure
──────────────────
Server → Client:
  {
    "v": 1,                     # protocol version
    "seq": 47,                  # monotonic per-table counter
    "table_id": "t_abc",
    "type": "PLAYER_ACTED",
    "payload": { ... },
    "ts": 1710000123.456        # server epoch
  }

Client → Server:
  {
    "type": "ACTION",
    "request_id": "c_uuid4",   # idempotency key; duplicate = silently dropped
    "table_id": "t_abc",
    "payload": { "action": "raise", "amount": 200 }
  }
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class CardDTO(BaseModel):
    rank: str   # "A","K","Q","J","T","9".."2"  or "?" for masked
    suit: str   # "S","H","D","C"               or "?" for masked

    @field_validator("rank")
    @classmethod
    def valid_rank(cls, v: str) -> str:
        valid = {"A","K","Q","J","T","9","8","7","6","5","4","3","2","?"}
        if v not in valid:
            raise ValueError(f"Invalid rank: {v!r}")
        return v

    @field_validator("suit")
    @classmethod
    def valid_suit(cls, v: str) -> str:
        if v not in {"S","H","D","C","?"}:
            raise ValueError(f"Invalid suit: {v!r}")
        return v


class PotDTO(BaseModel):
    amount: int
    eligible_player_ids: list[str]


class BettingStateDTO(BaseModel):
    current_bet: int
    min_raise_to: int
    bets_by_player: dict[str, int]


class PlayerViewDTO(BaseModel):
    user_id: str
    display_name: str
    seat_index: int
    stack: int
    status: str
    is_connected: bool


class HandViewDTO(BaseModel):
    hand_id: str
    phase: str
    hole_cards: dict[str, list[CardDTO]]    # masked for non-owners & spectators
    community_cards: list[CardDTO]
    pots: list[PotDTO]
    betting: BettingStateDTO
    dealer_seat: int
    small_blind_seat: int
    big_blind_seat: int
    current_turn_seat: Optional[int]
    turn_deadline: Optional[float]
    winners: Optional[list[dict[str, Any]]]
    # NOTE: deck is explicitly absent


class TableConfigDTO(BaseModel):
    starting_stack: int
    small_blind: int
    big_blind: int
    turn_timer_seconds: int
    max_players: int
    house_rules: list[str]


class StateSnapshotDTO(BaseModel):
    """Full game state — filtered per recipient before sending."""
    table_id: str
    club_id: str
    phase: str
    hand_number: int
    players: dict[str, PlayerViewDTO]
    seat_map: dict[str, str]           # "seat_index" → user_id (keys are strings)
    config: TableConfigDTO
    hand: Optional[HandViewDTO]


# ---------------------------------------------------------------------------
# Server → Client event payloads
# ---------------------------------------------------------------------------

class PhaseChangedPayload(BaseModel):
    phase: str
    pot_total: int = 0   # carried pots after the phase transition (for live pot display)


class CardsDealtPayload(BaseModel):
    """Sent ONLY to the player whose cards these are."""
    your_cards: list[CardDTO]


class CommunityCardsPayload(BaseModel):
    cards: list[CardDTO]
    phase: str


class PlayerActedPayload(BaseModel):
    user_id: str
    action: str         # "fold" | "check" | "call" | "raise" | "all_in"
    amount: int
    stack_remaining: int
    new_current_bet: int = 0   # outstanding bet on this street after the action
    min_raise_to: int = 0      # minimum legal raise-to after the action
    pot_total: int = 0         # committed pots + current-street bets (for live pot display)


class TurnChangedPayload(BaseModel):
    seat: int
    user_id: str
    deadline: Optional[float]           # None = no timer (e.g. admin pause)
    seconds_remaining: Optional[int] = None  # server-computed at send time; use for client countdown
    call_amount: int = 0        # player-specific: max(0, current_bet − player_bet_this_round)
    min_raise_to: int = 0       # minimum legal raise-to amount for this player
    max_raise: int = 0          # effective stack cap: min(my_total, max_active_opponent_total)


class PotUpdatedPayload(BaseModel):
    pots: list[PotDTO]


class PlayerStatusPayload(BaseModel):
    user_id: str
    status: str
    stack: int
    reserve_until: Optional[float] = None   # populated only when status == "disconnected"


class WinnerEntryDTO(BaseModel):
    user_id: str
    amount: int
    hand_description: str   # "Full House", "uncontested", etc.


class ShowdownHandDTO(BaseModel):
    user_id: str
    hole_cards: list[CardDTO]
    hand_description: str   # "Full House", "One Pair", etc.


class HandResultPayload(BaseModel):
    hand_id: str = ""
    hand_number: int = 0
    winners: list[WinnerEntryDTO]
    final_board: list[CardDTO]
    showdown_hands: list[ShowdownHandDTO]
    pot_total: int


class BlindsPostedPayload(BaseModel):
    small_blind_user_id: str
    small_blind_amount: int
    big_blind_user_id: str
    big_blind_amount: int


class BonusAwardedPayload(BaseModel):
    rule_id: str
    from_user_id: str
    to_user_id: str
    amount: int


class ChatMessagePayload(BaseModel):
    message_id: str
    user_id: str
    display_name: str
    message: str
    ts: float


class PlayerJoinedPayload(BaseModel):
    user_id: str
    display_name: str
    seat_index: int
    stack: int
    role: Literal["player", "spectator"]


class PlayerLeftPayload(BaseModel):
    user_id: str
    role: Literal["player", "spectator"]


class ErrorPayload(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Server event type registry
# ---------------------------------------------------------------------------

class ServerEventType(str, Enum):
    STATE_SNAPSHOT    = "STATE_SNAPSHOT"
    PHASE_CHANGED     = "PHASE_CHANGED"
    CARDS_DEALT       = "CARDS_DEALT"
    COMMUNITY_CARDS   = "COMMUNITY_CARDS"
    PLAYER_ACTED      = "PLAYER_ACTED"
    TURN_CHANGED      = "TURN_CHANGED"
    POT_UPDATED       = "POT_UPDATED"
    PLAYER_STATUS     = "PLAYER_STATUS"
    HAND_RESULT       = "HAND_RESULT"
    BLINDS_POSTED     = "BLINDS_POSTED"
    BONUS_AWARDED     = "BONUS_AWARDED"
    CHAT_MESSAGE      = "CHAT_MESSAGE"
    PLAYER_JOINED     = "PLAYER_JOINED"
    PLAYER_LEFT       = "PLAYER_LEFT"
    ERROR             = "ERROR"


# ---------------------------------------------------------------------------
# Server → Client envelope
# ---------------------------------------------------------------------------

class ServerEnvelope(BaseModel):
    v: int = 1
    seq: int
    table_id: str
    type: ServerEventType
    payload: dict[str, Any]
    ts: float = Field(default_factory=time.time)

    @classmethod
    def build(
        cls,
        *,
        seq: int,
        table_id: str,
        event_type: ServerEventType,
        payload: BaseModel | dict,
    ) -> "ServerEnvelope":
        if isinstance(payload, BaseModel):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload
        return cls(
            seq=seq,
            table_id=table_id,
            type=event_type,
            payload=payload_dict,
        )

    def to_json(self) -> str:
        return self.model_dump_json()


# ---------------------------------------------------------------------------
# Client → Server message types
# ---------------------------------------------------------------------------

class ClientMessageType(str, Enum):
    ACTION       = "ACTION"
    CHAT         = "CHAT"
    JOIN_TABLE   = "JOIN_TABLE"
    LEAVE_TABLE  = "LEAVE_TABLE"
    SYNC_REQUEST = "SYNC_REQUEST"
    SIT_OUT      = "SIT_OUT"
    SIT_IN       = "SIT_IN"


class ClientEnvelope(BaseModel):
    """Base envelope for all client → server messages."""
    type: ClientMessageType
    request_id: str              # UUID4, used for idempotency + error correlation
    table_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Client payload schemas (validated from ClientEnvelope.payload)
# ---------------------------------------------------------------------------

class ActionPayload(BaseModel):
    action: Literal["fold", "check", "call", "raise", "all_in"]
    amount: int = 0             # required for "raise"; ignored for others

    @field_validator("amount")
    @classmethod
    def amount_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("amount must be >= 0")
        return v


class ChatPayload(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty")
        if len(v) > 500:
            raise ValueError("message too long (max 500 chars)")
        return v


class JoinTablePayload(BaseModel):
    role: Literal["player", "spectator"] = "player"
