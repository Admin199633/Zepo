"""
Hand evaluator: finds the best 5-card hand from 5, 6, or 7 cards.

Hand rankings (high to low):
  9 - Royal Flush
  8 - Straight Flush
  7 - Four of a Kind
  6 - Full House
  5 - Flush
  4 - Straight
  3 - Three of a Kind
  2 - Two Pair
  1 - One Pair
  0 - High Card

Returns a HandRank that is comparable: higher is better.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from .models import Card, Rank


# ---------------------------------------------------------------------------
# Numeric rank lookup (2=2 … A=14)
# ---------------------------------------------------------------------------

_RANK_ORDER: list[str] = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"]
_RANK_VAL: dict[str, int] = {r: i + 2 for i, r in enumerate(_RANK_ORDER)}


def _val(card: Card) -> int:
    return _RANK_VAL[card.rank.value]


# ---------------------------------------------------------------------------
# HandRank — comparable tuple
# ---------------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class HandRank:
    """
    Sortable representation of a 5-card hand strength.
    category: 0 (high card) … 9 (royal flush / straight flush)
    tiebreakers: tuple of descending numeric rank values
    cards: the 5 cards that make up the best hand (excluded from ordering)
    """
    category: int
    tiebreakers: tuple[int, ...]
    cards: tuple[Card, ...] = field(compare=False, default_factory=tuple)

    @property
    def category_name(self) -> str:
        names = [
            "High Card","One Pair","Two Pair","Three of a Kind",
            "Straight","Flush","Full House","Four of a Kind",
            "Straight Flush","Royal Flush",
        ]
        return names[self.category]

    def __str__(self) -> str:
        return f"{self.category_name} ({', '.join(str(c) for c in self.cards)})"


# ---------------------------------------------------------------------------
# Internal 5-card evaluator
# ---------------------------------------------------------------------------

def _evaluate_five(cards: Sequence[Card]) -> HandRank:
    assert len(cards) == 5
    vals  = sorted([_val(c) for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush    = len(set(suits)) == 1
    is_straight = (
        vals == list(range(vals[0], vals[0] - 5, -1)) or
        vals == [14, 5, 4, 3, 2]   # A-2-3-4-5 wheel
    )
    wheel = vals == [14, 5, 4, 3, 2]
    straight_high = 5 if wheel else vals[0]

    from collections import Counter
    counts = Counter(vals)
    freq   = sorted(counts.values(), reverse=True)     # e.g. [2, 2, 1]
    groups = sorted(counts.keys(), key=lambda v: (counts[v], v), reverse=True)
    # groups: cards ordered by (frequency desc, value desc) for tiebreaking

    c = tuple(cards)

    if is_straight and is_flush:
        cat = 9 if straight_high == 14 and not wheel else 8
        return HandRank(cat, (straight_high,), c)

    if freq == [4, 1]:
        return HandRank(7, tuple(groups), c)

    if freq == [3, 2]:
        return HandRank(6, tuple(groups), c)

    if is_flush:
        return HandRank(5, tuple(vals), c)

    if is_straight:
        return HandRank(4, (straight_high,), c)

    if freq == [3, 1, 1]:
        return HandRank(3, tuple(groups), c)

    if freq == [2, 2, 1]:
        return HandRank(2, tuple(groups), c)

    if freq == [2, 1, 1, 1]:
        return HandRank(1, tuple(groups), c)

    return HandRank(0, tuple(vals), c)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def best_hand(cards: Sequence[Card]) -> HandRank:
    """
    Given 5–7 cards, return the HandRank of the best 5-card combination.
    """
    if len(cards) < 5:
        raise ValueError(f"Need at least 5 cards, got {len(cards)}")

    best: HandRank | None = None
    for combo in combinations(cards, 5):
        rank = _evaluate_five(combo)
        if best is None or rank > best:
            best = rank
    assert best is not None
    return best


def compare_hands(
    player_cards: dict[str, list[Card]],
    community: list[Card],
) -> list[str]:
    """
    Given a dict of user_id → hole_cards and the 5 community cards,
    return list of user_ids that won (tied winners share the pot).
    """
    rankings: dict[str, HandRank] = {}
    for uid, hole in player_cards.items():
        rankings[uid] = best_hand(hole + community)

    best_rank = max(rankings.values())
    return [uid for uid, rank in rankings.items() if rank == best_rank]
