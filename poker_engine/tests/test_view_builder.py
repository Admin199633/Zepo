"""Tests for the view builder — no data leaks."""
from __future__ import annotations

import uuid

from ..engine.models import (
    BettingState, Card, HandPhase, HandState, Pot, Rank, Suit,
)
from ..engine.view_builder import build_player_view, build_spectator_view
from .helpers import make_game_state


def _state_with_hand(n=3):
    state = make_game_state(n_players=n)
    state.hand = HandState(
        hand_id=str(uuid.uuid4()),
        phase=HandPhase.PRE_FLOP,
        deck=[Card(Rank.TWO, Suit.CLUBS)] * 40,
        hole_cards={
            "alice": [Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)],
            "bob":   [Card(Rank.TWO, Suit.DIAMONDS), Card(Rank.THREE, Suit.CLUBS)],
            "carol": [Card(Rank.JACK, Suit.HEARTS), Card(Rank.TEN, Suit.SPADES)],
        },
        community_cards=[],
        pots=[Pot(amount=30, eligible_player_ids=["alice","bob","carol"])],
        betting=BettingState(
            current_bet=20,
            bets_by_player={"alice":10,"bob":20},
            min_raise_to=40,
            last_aggressor_seat=1,
            acted_seats={1},
        ),
        dealer_seat=0,
        small_blind_seat=1,
        big_blind_seat=2,
        current_turn_seat=0,
        turn_deadline=None,
        winners=None,
        stacks_at_start={"alice":1000,"bob":1000,"carol":1000},
    )
    return state


class TestPlayerView:
    def test_own_cards_revealed(self):
        state = _state_with_hand()
        view = build_player_view(state, for_user_id="alice")
        cards = view["hand"]["hole_cards"]["alice"]
        assert cards[0] != {"rank": "?", "suit": "?"}
        assert cards[0]["rank"] == "A"

    def test_opponent_cards_masked(self):
        state = _state_with_hand()
        view = build_player_view(state, for_user_id="alice")
        for uid in ["bob", "carol"]:
            for c in view["hand"]["hole_cards"][uid]:
                assert c == {"rank": "?", "suit": "?"}

    def test_deck_never_in_view(self):
        state = _state_with_hand()
        view = build_player_view(state, for_user_id="alice")
        assert "deck" not in view.get("hand", {})

    def test_all_players_visible(self):
        state = _state_with_hand()
        view = build_player_view(state, for_user_id="alice")
        assert set(view["players"].keys()) == {"alice", "bob", "carol"}


class TestSpectatorView:
    def test_all_cards_masked_preflop(self):
        state = _state_with_hand()
        view = build_spectator_view(state)
        for uid in ["alice", "bob", "carol"]:
            for c in view["hand"]["hole_cards"][uid]:
                assert c == {"rank": "?", "suit": "?"}

    def test_deck_never_in_spectator_view(self):
        state = _state_with_hand()
        view = build_spectator_view(state)
        assert "deck" not in view.get("hand", {})

    def test_cards_revealed_at_showdown(self):
        state = _state_with_hand()
        state.hand.phase = HandPhase.HAND_END
        state.hand.winners = [{"pot_index": 0, "winner_ids": ["alice"]}]
        view = build_spectator_view(state)
        # At hand end with winners set, cards should be revealed
        alice_cards = view["hand"]["hole_cards"]["alice"]
        assert alice_cards[0] != {"rank": "?", "suit": "?"}
