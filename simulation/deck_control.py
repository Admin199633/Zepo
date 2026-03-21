"""
simulation/deck_control.py
--------------------------
Deterministic deck injection for simulation scenarios.

BOUNDARY RULE: This module must NEVER be imported from poker_engine/ or backend/.
It is exclusively test-harness infrastructure.

The mechanism: monkey-patch poker_engine.engine.game_engine.fresh_shuffled_deck
to return a caller-supplied pre-ordered deck. The original function is restored
unconditionally in a finally block.

Deck position reference (2-player hand, seats sorted ascending):
  deck[0]   → seat 0 hole card 1
  deck[1]   → seat 1 hole card 1
  deck[2]   → seat 0 hole card 2
  deck[3]   → seat 1 hole card 2
  deck[4:7] → flop (3 cards)
  deck[7]   → turn
  deck[8]   → river
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import poker_engine.engine.game_engine as _game_engine_module
from poker_engine.engine.models import Card, Rank, Suit

# Type alias: list of (rank_str, suit_str) pairs.
DeckSpec = list[tuple[str, str]]

# Lookup tables derived from the enums — matches Rank.value and Suit.value exactly.
_RANK_MAP: dict[str, Rank] = {r.value: r for r in Rank}
_SUIT_MAP: dict[str, Suit] = {s.value: s for s in Suit}

# ---------------------------------------------------------------------------
# Deck recipes — first 9 cards define the hand; complete_deck() pads to 52.
# ---------------------------------------------------------------------------

# Dealing order: engine calls deal_cards(deck, 2) per player in ascending seat order.
# seat0 gets deck[0:2], seat1 gets deck[2:4], community starts at deck[4].

# Recipe A: Owner (seat 0) wins with Royal Flush.
# Owner hole: A♠ K♠ | Joiner hole: 2♥ 3♦ | Board: Q♠ J♠ T♠ 2♣ 3♣
RECIPE_A: DeckSpec = [
    ("A", "S"), ("K", "S"),            # seat0 hole cards (owner)
    ("2", "H"), ("3", "D"),            # seat1 hole cards (joiner)
    ("Q", "S"), ("J", "S"), ("T", "S"),  # flop
    ("2", "C"),                        # turn
    ("3", "C"),                        # river
]

# Recipe B: Joiner (seat 1) wins with Trip Aces.
# Owner hole: 2♠ 3♥ | Joiner hole: A♥ A♦ | Board: A♣ K♠ Q♦ 5♥ 6♣
RECIPE_B: DeckSpec = [
    ("2", "S"), ("3", "H"),            # seat0 hole cards (owner)
    ("A", "H"), ("A", "D"),            # seat1 hole cards (joiner)
    ("A", "C"), ("K", "S"), ("Q", "D"),  # flop
    ("5", "H"),                        # turn
    ("6", "C"),                        # river
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_deterministic_deck(cards: DeckSpec) -> list[Card]:
    """
    Convert a list of (rank_str, suit_str) pairs into a list of Card objects.

    rank_str must be one of: "2" "3" "4" "5" "6" "7" "8" "9" "T" "J" "Q" "K" "A"
    suit_str must be one of: "S" "H" "D" "C" (case-insensitive)

    Raises ValueError for any unrecognised rank or suit string.
    """
    result: list[Card] = []
    for rank_str, suit_str in cards:
        rank_upper = rank_str.upper()
        suit_upper = suit_str.upper()
        if rank_upper not in _RANK_MAP:
            raise ValueError(
                f"Unrecognised rank {rank_str!r}. "
                f"Valid ranks: {sorted(_RANK_MAP.keys())}"
            )
        if suit_upper not in _SUIT_MAP:
            raise ValueError(
                f"Unrecognised suit {suit_str!r}. "
                f"Valid suits: {sorted(_SUIT_MAP.keys())}"
            )
        result.append(Card(rank=_RANK_MAP[rank_upper], suit=_SUIT_MAP[suit_upper]))
    return result


def complete_deck(prefix: DeckSpec) -> DeckSpec:
    """
    Pad a DeckSpec prefix to a full 52-card deck with non-duplicate cards.

    The engine's deal_cards() raises ValueError if fewer cards remain than needed.
    Padding ensures the engine never runs out of cards even if more community
    cards are somehow needed (e.g., run-out scenarios).
    """
    used = {(r.upper(), s.upper()) for r, s in prefix}
    all_ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
    all_suits = ["S", "H", "D", "C"]
    padding = [
        (r, s)
        for r in all_ranks
        for s in all_suits
        if (r, s) not in used
    ]
    return list(prefix) + padding


@contextmanager
def injected_deck(cards: DeckSpec) -> Generator[None, None, None]:
    """
    Context manager that patches poker_engine.engine.game_engine.fresh_shuffled_deck
    to return a copy of the pre-ordered deck on every call, then restores the
    original function unconditionally on exit (including exception paths).

    Usage:
        with injected_deck(complete_deck(RECIPE_A)):
            # any start_hand() call in this block uses the pre-ordered deck
            owner.drain_until("HAND_RESULT")
        # original fresh_shuffled_deck restored here

    The lambda returns list(typed_cards) so that each call to fresh_shuffled_deck()
    receives an independent list object (engine slices the deck, not in-place).
    """
    typed_cards: list[Card] = build_deterministic_deck(cards)
    original = _game_engine_module.fresh_shuffled_deck
    _game_engine_module.fresh_shuffled_deck = lambda: list(typed_cards)
    try:
        yield
    finally:
        _game_engine_module.fresh_shuffled_deck = original
