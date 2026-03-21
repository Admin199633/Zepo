"""
House Rules plugin interface.

Each rule is a stateless object with hook methods.
The engine calls hooks at defined points; rules can:
  - Override an action (e.g. auto-fold an invalid hand)
  - Grant bonus chips after a win
  - Inject a straddle before pre-flop

Rules must NOT mutate GameState directly — they return instruction objects
and the engine applies them. This keeps the engine deterministic and testable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..engine.models import Card, GameState


# ---------------------------------------------------------------------------
# Instruction objects returned by rules
# ---------------------------------------------------------------------------

@dataclass
class AutoFoldInstruction:
    """Tell the engine to immediately fold this player's hand."""
    user_id: str
    reason: str


@dataclass
class BonusTransfer:
    """Transfer chips from one player to another as a bonus."""
    from_user_id: str
    to_user_id: str
    amount: int
    rule_id: str
    reason: str


@dataclass
class StraddleInstruction:
    """Post a straddle blind before pre-flop."""
    user_id: str
    amount: int


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class HouseRule(ABC):
    """
    Abstract base for all house rules.

    Hooks are called in order by the engine. Return None to indicate
    "no action" for that hook.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique string identifier for this rule, e.g. 'bonus_27'."""
        ...

    def on_hole_cards_dealt(
        self,
        user_id: str,
        cards: list[Card],
        state: GameState,
    ) -> Optional[AutoFoldInstruction]:
        """
        Called immediately after hole cards are dealt to a player.
        Return AutoFoldInstruction to force-fold an invalid hand.
        """
        return None

    def on_hand_won(
        self,
        winner_id: str,
        winning_cards: list[Card],
        community_cards: list[Card],
        state: GameState,
    ) -> list[BonusTransfer]:
        """
        Called after winners are determined for a pot.
        Return BonusTransfer list to award bonuses.
        """
        return []

    def on_pre_deal(
        self,
        state: GameState,
    ) -> Optional[StraddleInstruction]:
        """
        Called before hole cards are dealt (after blinds).
        Return StraddleInstruction to inject a straddle.
        """
        return None
