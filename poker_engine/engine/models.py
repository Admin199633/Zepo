"""
Core data models for the poker engine.
Pure dataclasses — no I/O, no networking.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Suit(str, Enum):
    SPADES   = "S"
    HEARTS   = "H"
    DIAMONDS = "D"
    CLUBS    = "C"


class Rank(str, Enum):
    TWO   = "2"
    THREE = "3"
    FOUR  = "4"
    FIVE  = "5"
    SIX   = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE  = "9"
    TEN   = "T"
    JACK  = "J"
    QUEEN = "Q"
    KING  = "K"
    ACE   = "A"

    @property
    def numeric(self) -> int:
        """Return numeric value for comparison (Ace = 14)."""
        order = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"]
        return order.index(self.value) + 2


class HandPhase(str, Enum):
    WAITING_FOR_PLAYERS = "WAITING_FOR_PLAYERS"
    START_HAND          = "START_HAND"
    DEAL_HOLE_CARDS     = "DEAL_HOLE_CARDS"
    PRE_FLOP            = "PRE_FLOP"
    FLOP                = "FLOP"
    TURN                = "TURN"
    RIVER               = "RIVER"
    SHOWDOWN            = "SHOWDOWN"
    HAND_END            = "HAND_END"


class ActionType(str, Enum):
    FOLD   = "fold"
    CHECK  = "check"
    CALL   = "call"
    RAISE  = "raise"
    ALL_IN = "all_in"


class PlayerStatus(str, Enum):
    ACTIVE  = "active"    # seated, has chips, in hand
    FOLDED  = "folded"    # folded this hand
    ALL_IN  = "all_in"    # committed all chips
    SIT_OUT = "sit_out"   # not participating
    WAITING = "waiting"   # joined mid-hand, starts next hand


# ---------------------------------------------------------------------------
# Card / Deck
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"

    def __repr__(self) -> str:
        return self.__str__()


# ---------------------------------------------------------------------------
# Table Configuration
# ---------------------------------------------------------------------------

VALID_TURN_TIMERS = {15, 30, 60, 90, 120, 300, 900, 1800, 3600}


@dataclass
class TableConfig:
    starting_stack: int
    small_blind: int
    big_blind: int
    turn_timer_seconds: int
    max_players: int = 10
    house_rules: list[str] = field(default_factory=list)
    rule_params: dict = field(default_factory=dict)  # rule_id → {param: value}

    def __post_init__(self) -> None:
        assert self.big_blind == self.small_blind * 2, "BB must be 2x SB"
        assert self.turn_timer_seconds in VALID_TURN_TIMERS, (
            f"turn_timer_seconds must be one of {VALID_TURN_TIMERS}"
        )
        assert 2 <= self.max_players <= 10
        assert self.starting_stack >= self.big_blind * 2


# ---------------------------------------------------------------------------
# Pot
# ---------------------------------------------------------------------------

@dataclass
class Pot:
    amount: int
    eligible_player_ids: list[str]  # user_ids eligible to win this pot

    def __repr__(self) -> str:
        return f"Pot({self.amount}, eligible={self.eligible_player_ids})"


# ---------------------------------------------------------------------------
# Betting state (within a single betting round)
# ---------------------------------------------------------------------------

@dataclass
class BettingState:
    current_bet: int                        # highest bet placed this round
    bets_by_player: dict[str, int]          # user_id → amount bet this round
    min_raise_to: int                       # minimum legal raise-to amount
    last_aggressor_seat: Optional[int]      # seat that last raised
    acted_seats: set[int] = field(default_factory=set)  # seats that have voluntarily acted


# ---------------------------------------------------------------------------
# Hand State
# ---------------------------------------------------------------------------

@dataclass
class HandState:
    hand_id: str
    phase: HandPhase
    deck: list[Card]                            # remaining (server-only, never sent to client)
    hole_cards: dict[str, list[Card]]           # user_id → [Card, Card]
    community_cards: list[Card]
    pots: list[Pot]
    betting: BettingState
    dealer_seat: int
    small_blind_seat: int
    big_blind_seat: int
    current_turn_seat: Optional[int]
    turn_deadline: Optional[float]              # epoch seconds; None if no active turn
    winners: Optional[list[dict]]               # populated at HAND_END
    stacks_at_start: dict[str, int]             # user_id → stack at hand start


# ---------------------------------------------------------------------------
# Player Session
# ---------------------------------------------------------------------------

@dataclass
class PlayerSession:
    user_id: str
    display_name: str
    seat_index: int
    stack: int
    status: PlayerStatus
    timeout_count: int = 0
    is_connected: bool = True
    disconnect_at: Optional[float] = None       # epoch when disconnected
    original_buy_in: int = 0                    # stack at first seat (rebuy cap basis)
    rebuy_count: int = 0                        # number of rebuys performed


# ---------------------------------------------------------------------------
# Game State  (the single source of truth)
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    table_id: str
    club_id: str
    config: TableConfig
    phase: HandPhase
    players: dict[str, PlayerSession]           # user_id → session
    seat_map: dict[int, str]                    # seat_index → user_id
    hand: Optional[HandState]
    hand_number: int = 0

    # ---- helpers --------------------------------------------------------

    def get_player(self, user_id: str) -> Optional[PlayerSession]:
        return self.players.get(user_id)

    def get_player_at_seat(self, seat: int) -> Optional[PlayerSession]:
        uid = self.seat_map.get(seat)
        return self.players.get(uid) if uid else None

    def active_seats_in_hand(self) -> list[int]:
        """Seats still in the hand (ACTIVE or ALL_IN), ordered."""
        seats = []
        for seat, uid in sorted(self.seat_map.items()):
            p = self.players[uid]
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN):
                seats.append(seat)
        return seats

    def seats_that_can_act(self) -> list[int]:
        """Seats that are ACTIVE (not folded, not all-in, have chips)."""
        seats = []
        for seat, uid in sorted(self.seat_map.items()):
            p = self.players[uid]
            if p.status == PlayerStatus.ACTIVE:
                seats.append(seat)
        return seats


# ---------------------------------------------------------------------------
# Action  (input from a player)
# ---------------------------------------------------------------------------

@dataclass
class Action:
    user_id: str
    action_type: ActionType
    amount: int = 0                             # total chips going in this action
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Engine Events  (output produced by the engine)
# ---------------------------------------------------------------------------

@dataclass
class EngineEvent:
    """Base class for all events emitted by the engine."""
    event_type: str


@dataclass
class EvtPhaseChanged(EngineEvent):
    event_type: str = "PHASE_CHANGED"
    phase: HandPhase = HandPhase.WAITING_FOR_PLAYERS


@dataclass
class EvtCardsDealt(EngineEvent):
    """Emitted once per player. Contains ONLY that player's cards."""
    event_type: str = "CARDS_DEALT"
    user_id: str = ""
    cards: list[Card] = field(default_factory=list)


@dataclass
class EvtCommunityCards(EngineEvent):
    event_type: str = "COMMUNITY_CARDS"
    cards: list[Card] = field(default_factory=list)
    phase: HandPhase = HandPhase.FLOP


@dataclass
class EvtPlayerActed(EngineEvent):
    event_type: str = "PLAYER_ACTED"
    user_id: str = ""
    action_type: ActionType = ActionType.FOLD
    amount: int = 0
    stack_remaining: int = 0


@dataclass
class EvtTurnChanged(EngineEvent):
    event_type: str = "TURN_CHANGED"
    seat: int = 0
    user_id: str = ""
    deadline: Optional[float] = None


@dataclass
class EvtPotUpdated(EngineEvent):
    event_type: str = "POT_UPDATED"
    pots: list[Pot] = field(default_factory=list)


@dataclass
class EvtPlayerStatus(EngineEvent):
    event_type: str = "PLAYER_STATUS"
    user_id: str = ""
    status: PlayerStatus = PlayerStatus.ACTIVE
    stack: int = 0


@dataclass
class EvtHandResult(EngineEvent):
    event_type: str = "HAND_RESULT"
    winners: list[dict] = field(default_factory=list)
    showdown_cards: dict[str, list[Card]] = field(default_factory=dict)
    pot_total: int = 0
    winnings: dict[str, int] = field(default_factory=dict)           # uid → chips won
    hand_descriptions: dict[str, str] = field(default_factory=dict)  # uid → "Full House" etc.


@dataclass
class EvtBlindsPosted(EngineEvent):
    event_type: str = "BLINDS_POSTED"
    small_blind_user_id: str = ""
    small_blind_amount: int = 0
    big_blind_user_id: str = ""
    big_blind_amount: int = 0


@dataclass
class EvtBonusAwarded(EngineEvent):
    event_type: str = "BONUS_AWARDED"
    rule_id: str = ""
    from_user_id: str = ""
    to_user_id: str = ""
    amount: int = 0
