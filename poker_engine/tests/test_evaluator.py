"""Tests for hand evaluation — all 9 hand categories."""
import pytest
from ..engine.evaluator import best_hand, compare_hands
from ..engine.models import Card, Rank, Suit

S, H, D, C = Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS


def card(rank_val: str, suit: Suit) -> Card:
    return Card(rank=Rank(rank_val), suit=suit)


# --- helpers to build hands ---

def royal_flush():
    return [card("A",S), card("K",S), card("Q",S), card("J",S), card("T",S)]

def straight_flush():
    return [card("9",H), card("8",H), card("7",H), card("6",H), card("5",H)]

def four_of_a_kind():
    return [card("A",S), card("A",H), card("A",D), card("A",C), card("K",S)]

def full_house():
    return [card("K",S), card("K",H), card("K",D), card("Q",S), card("Q",H)]

def flush():
    return [card("A",D), card("J",D), card("9",D), card("5",D), card("2",D)]

def straight():
    return [card("T",S), card("9",H), card("8",D), card("7",C), card("6",S)]

def wheel_straight():
    """A-2-3-4-5 — the wheel."""
    return [card("A",S), card("2",H), card("3",D), card("4",C), card("5",S)]

def three_of_a_kind():
    return [card("Q",S), card("Q",H), card("Q",D), card("7",S), card("2",H)]

def two_pair():
    return [card("J",S), card("J",H), card("9",D), card("9",C), card("A",S)]

def one_pair():
    return [card("T",S), card("T",H), card("8",D), card("5",C), card("2",S)]

def high_card():
    return [card("A",S), card("K",H), card("J",D), card("8",C), card("3",S)]


# --- category tests ---

class TestHandCategories:
    def test_royal_flush(self):
        assert best_hand(royal_flush()).category == 9

    def test_straight_flush(self):
        assert best_hand(straight_flush()).category == 8

    def test_four_of_a_kind(self):
        assert best_hand(four_of_a_kind()).category == 7

    def test_full_house(self):
        assert best_hand(full_house()).category == 6

    def test_flush(self):
        assert best_hand(flush()).category == 5

    def test_straight(self):
        assert best_hand(straight()).category == 4

    def test_wheel_straight(self):
        rank = best_hand(wheel_straight())
        assert rank.category == 4
        assert rank.tiebreakers == (5,)  # high card is 5, not Ace

    def test_three_of_a_kind(self):
        assert best_hand(three_of_a_kind()).category == 3

    def test_two_pair(self):
        assert best_hand(two_pair()).category == 2

    def test_one_pair(self):
        assert best_hand(one_pair()).category == 1

    def test_high_card(self):
        assert best_hand(high_card()).category == 0


# --- ranking comparison ---

class TestHandRanking:
    def test_royal_beats_straight_flush(self):
        assert best_hand(royal_flush()) > best_hand(straight_flush())

    def test_four_of_a_kind_beats_full_house(self):
        assert best_hand(four_of_a_kind()) > best_hand(full_house())

    def test_full_house_beats_flush(self):
        assert best_hand(full_house()) > best_hand(flush())

    def test_flush_beats_straight(self):
        assert best_hand(flush()) > best_hand(straight())

    def test_straight_beats_trips(self):
        assert best_hand(straight()) > best_hand(three_of_a_kind())

    def test_trips_beats_two_pair(self):
        assert best_hand(three_of_a_kind()) > best_hand(two_pair())

    def test_two_pair_beats_one_pair(self):
        assert best_hand(two_pair()) > best_hand(one_pair())

    def test_one_pair_beats_high_card(self):
        assert best_hand(one_pair()) > best_hand(high_card())


# --- 7-card best hand ---

class TestSevenCardBest:
    def test_picks_best_5_of_7(self):
        # Community has a flush, player has a pair — flush should win
        community = [card("A",S), card("K",S), card("Q",S), card("J",S), card("9",S)]
        hole = [card("2",H), card("2",D)]
        all_cards = hole + community
        rank = best_hand(all_cards)
        assert rank.category == 5  # flush (or higher)

    def test_royal_flush_from_7(self):
        hole = [card("A",S), card("K",S)]
        community = [card("Q",S), card("J",S), card("T",S), card("2",H), card("3",D)]
        assert best_hand(hole + community).category == 9


# --- compare_hands ---

class TestCompareHands:
    def test_single_winner(self):
        community = [card("2",H), card("5",D), card("9",C), card("K",S), card("3",H)]
        players = {
            "alice": [card("A",S), card("A",H)],   # pair of aces
            "bob":   [card("7",S), card("8",D)],    # high card
        }
        winners = compare_hands(players, community)
        assert winners == ["alice"]

    def test_tie_both_win(self):
        community = [card("A",S), card("K",H), card("Q",D), card("J",C), card("T",S)]
        # Both players have a broadway straight on the board
        players = {
            "alice": [card("2",H), card("3",D)],
            "bob":   [card("4",H), card("5",D)],
        }
        winners = compare_hands(players, community)
        assert set(winners) == {"alice", "bob"}

    def test_kicker_breaks_tie(self):
        community = [card("A",S), card("A",H), card("2",D), card("3",C), card("4",S)]
        players = {
            "alice": [card("K",H), card("Q",D)],   # pair of aces, K kicker
            "bob":   [card("K",D), card("J",H)],   # pair of aces, K kicker too
        }
        # Both have same kicker sequence: A A K Q 4 vs A A K J 4
        winners = compare_hands(players, community)
        assert "alice" in winners  # alice wins with Q > J kicker
        assert "bob" not in winners
