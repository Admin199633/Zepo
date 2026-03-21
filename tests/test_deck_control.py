"""
Unit tests for simulation/deck_control.py.

Verifies:
  - build_deterministic_deck parses card specs correctly
  - complete_deck pads to exactly 52 unique cards
  - injected_deck patches fresh_shuffled_deck inside the context
  - injected_deck restores original function on normal exit
  - injected_deck restores original function when exception is raised inside context
  - Sequential invocations do not interfere with each other
  - Invalid rank/suit strings raise ValueError
"""
from __future__ import annotations

import pytest
import poker_engine.engine.game_engine as _ge

from simulation.deck_control import (
    RECIPE_A,
    RECIPE_B,
    build_deterministic_deck,
    complete_deck,
    injected_deck,
)


# ---------------------------------------------------------------------------
# build_deterministic_deck
# ---------------------------------------------------------------------------

def test_build_deterministic_deck_recipe_a():
    cards = build_deterministic_deck(RECIPE_A)
    assert len(cards) == len(RECIPE_A)
    # Recipe A: seat0 hole = [deck[0], deck[1]] = A♠ K♠
    assert cards[0].rank.value == "A"
    assert cards[0].suit.value == "S"
    assert cards[1].rank.value == "K"
    assert cards[1].suit.value == "S"


def test_build_deterministic_deck_recipe_b():
    cards = build_deterministic_deck(RECIPE_B)
    # Recipe B: seat0 hole = [deck[0], deck[1]] = 2♠ 3♥
    assert cards[0].rank.value == "2"
    assert cards[0].suit.value == "S"
    assert cards[1].rank.value == "3"
    assert cards[1].suit.value == "H"


def test_build_deterministic_deck_case_insensitive_suit():
    cards = build_deterministic_deck([("A", "s")])
    assert cards[0].suit.value == "S"


def test_build_deterministic_deck_invalid_rank():
    with pytest.raises(ValueError, match="rank"):
        build_deterministic_deck([("X", "S")])


def test_build_deterministic_deck_invalid_suit():
    with pytest.raises(ValueError, match="suit"):
        build_deterministic_deck([("A", "Z")])


# ---------------------------------------------------------------------------
# complete_deck
# ---------------------------------------------------------------------------

def test_complete_deck_length():
    full = complete_deck(RECIPE_A)
    assert len(full) == 52


def test_complete_deck_no_duplicates():
    full = complete_deck(RECIPE_A)
    seen = set()
    for r, s in full:
        key = (r.upper(), s.upper())
        assert key not in seen, f"Duplicate card in complete_deck: {key}"
        seen.add(key)


def test_complete_deck_prefix_preserved():
    full = complete_deck(RECIPE_A)
    for i, (r, s) in enumerate(RECIPE_A):
        assert full[i] == (r, s), f"Prefix position {i} changed: {full[i]} != {(r, s)}"


def test_complete_deck_recipe_b_no_duplicates():
    full = complete_deck(RECIPE_B)
    assert len(full) == 52
    seen = set()
    for r, s in full:
        key = (r.upper(), s.upper())
        assert key not in seen
        seen.add(key)


# ---------------------------------------------------------------------------
# injected_deck — patch behaviour
# ---------------------------------------------------------------------------

def test_patch_applied_inside_context():
    original = _ge.fresh_shuffled_deck
    with injected_deck(complete_deck(RECIPE_A)):
        assert _ge.fresh_shuffled_deck is not original
        deck = _ge.fresh_shuffled_deck()
        # First card must be Ace of Spades (Recipe A deck[0])
        assert deck[0].rank.value == "A"
        assert deck[0].suit.value == "S"


def test_patch_restored_after_normal_exit():
    original = _ge.fresh_shuffled_deck
    with injected_deck(complete_deck(RECIPE_A)):
        pass
    assert _ge.fresh_shuffled_deck is original, (
        "fresh_shuffled_deck must be restored to the original function after normal context exit"
    )


def test_patch_restored_after_exception():
    original = _ge.fresh_shuffled_deck
    try:
        with injected_deck(complete_deck(RECIPE_A)):
            raise RuntimeError("simulated crash inside deterministic context")
    except RuntimeError:
        pass
    assert _ge.fresh_shuffled_deck is original, (
        "fresh_shuffled_deck must be restored even when an exception is raised inside the context"
    )


def test_sequential_invocations_do_not_interfere():
    original = _ge.fresh_shuffled_deck

    with injected_deck(complete_deck(RECIPE_A)):
        d1 = _ge.fresh_shuffled_deck()

    with injected_deck(complete_deck(RECIPE_B)):
        d2 = _ge.fresh_shuffled_deck()

    # Both contexts exited — original must be restored
    assert _ge.fresh_shuffled_deck is original

    # Recipe A: deck[0]=A♠, deck[1]=K♠ (seat0 hole cards)
    assert d1[0].rank.value == "A" and d1[0].suit.value == "S"
    assert d1[1].rank.value == "K" and d1[1].suit.value == "S"

    # Recipe B: deck[0]=2♠, deck[1]=3♥ (seat0 hole cards)
    assert d2[0].rank.value == "2" and d2[0].suit.value == "S"
    assert d2[1].rank.value == "3" and d2[1].suit.value == "H"


def test_injected_deck_returns_independent_list_each_call():
    """Each call to the patched function returns a new list object."""
    with injected_deck(complete_deck(RECIPE_A)):
        d1 = _ge.fresh_shuffled_deck()
        d2 = _ge.fresh_shuffled_deck()
    assert d1 is not d2, "Each call must return a new list (not the same object)"
    assert d1 == d2, "Both calls must return lists with identical card content"
