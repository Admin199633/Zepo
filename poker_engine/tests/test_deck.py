"""Tests for deck generation and shuffling."""
import pytest
from ..engine.deck import build_deck, deal_cards, fresh_shuffled_deck, shuffle_deck
from ..engine.models import Card, Rank, Suit


def test_deck_has_52_cards():
    deck = build_deck()
    assert len(deck) == 52


def test_deck_all_unique():
    deck = build_deck()
    assert len(set(deck)) == 52


def test_deck_covers_all_suits_and_ranks():
    deck = build_deck()
    ranks = {c.rank for c in deck}
    suits = {c.suit for c in deck}
    assert ranks == set(Rank)
    assert suits == set(Suit)


def test_shuffle_returns_same_cards():
    deck = build_deck()
    shuffled = shuffle_deck(deck)
    assert len(shuffled) == 52
    assert set(shuffled) == set(deck)


def test_shuffle_is_different_order():
    deck = build_deck()
    shuffled = shuffle_deck(deck)
    # Astronomically unlikely to be identical — but not impossible.
    # Run multiple times to be sure.
    different = any(shuffle_deck(deck) != deck for _ in range(5))
    assert different


def test_deal_cards_splits_correctly():
    deck = build_deck()
    dealt, remaining = deal_cards(deck, 5)
    assert len(dealt) == 5
    assert len(remaining) == 47
    assert set(dealt) | set(remaining) == set(deck)


def test_deal_cards_raises_on_insufficient():
    deck = build_deck()[:3]
    with pytest.raises(ValueError):
        deal_cards(deck, 5)


def test_fresh_shuffled_deck_has_52():
    assert len(fresh_shuffled_deck()) == 52
