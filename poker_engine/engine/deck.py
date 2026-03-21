"""
Deck creation and cryptographically secure shuffle.
Uses secrets.SystemRandom — no client influence possible.
"""
from __future__ import annotations

import secrets
from .models import Card, Rank, Suit


_ALL_RANKS = list(Rank)
_ALL_SUITS = list(Suit)


def build_deck() -> list[Card]:
    """Return a fresh, unshuffled 52-card deck."""
    return [Card(rank=r, suit=s) for r in _ALL_RANKS for s in _ALL_SUITS]


def shuffle_deck(deck: list[Card]) -> list[Card]:
    """
    Return a new shuffled copy using a cryptographically secure RNG.
    Fisher-Yates via secrets.SystemRandom ensures uniform distribution
    with no client-side influence.
    """
    rng = secrets.SystemRandom()
    shuffled = list(deck)
    rng.shuffle(shuffled)
    return shuffled


def fresh_shuffled_deck() -> list[Card]:
    """Convenience: build + shuffle in one call."""
    return shuffle_deck(build_deck())


def deal_cards(deck: list[Card], n: int) -> tuple[list[Card], list[Card]]:
    """
    Deal n cards from the top of the deck.
    Returns (dealt_cards, remaining_deck).
    Raises ValueError if not enough cards remain.
    """
    if len(deck) < n:
        raise ValueError(f"Cannot deal {n} cards from deck of {len(deck)}")
    return deck[:n], deck[n:]
