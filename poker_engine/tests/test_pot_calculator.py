"""Tests for pot calculation including side pots."""
from ..engine.pot_calculator import award_pots, calculate_pots


class TestMainPot:
    def test_single_pot_all_equal(self):
        contributions = {"alice": 100, "bob": 100, "carol": 100}
        active = {"alice", "bob", "carol"}
        pots = calculate_pots(contributions, active)
        assert len(pots) == 1
        assert pots[0].amount == 300
        assert set(pots[0].eligible_player_ids) == {"alice", "bob", "carol"}

    def test_folded_player_contributes_but_not_eligible(self):
        contributions = {"alice": 100, "bob": 100, "carol": 50}
        active = {"alice", "bob"}  # carol folded
        pots = calculate_pots(contributions, active)
        total = sum(p.amount for p in pots)
        assert total == 250
        for pot in pots:
            assert "carol" not in pot.eligible_player_ids


class TestSidePots:
    def test_one_all_in_creates_side_pot(self):
        # alice all-in for 50, bob and carol have 100 each
        contributions = {"alice": 50, "bob": 100, "carol": 100}
        active = {"alice", "bob", "carol"}
        pots = calculate_pots(contributions, active)

        assert len(pots) == 2

        # Main pot: 50×3 = 150, all 3 eligible
        main = pots[0]
        assert main.amount == 150
        assert set(main.eligible_player_ids) == {"alice", "bob", "carol"}

        # Side pot: 50×2 = 100, only bob and carol eligible
        side = pots[1]
        assert side.amount == 100
        assert set(side.eligible_player_ids) == {"bob", "carol"}
        assert "alice" not in side.eligible_player_ids

    def test_two_all_ins_create_two_side_pots(self):
        contributions = {"a": 30, "b": 60, "c": 100}
        active = {"a", "b", "c"}
        pots = calculate_pots(contributions, active)

        total = sum(p.amount for p in pots)
        assert total == 190

        # Each pot should have decreasing eligible sets
        for pot in pots:
            assert len(pot.eligible_player_ids) >= 1


class TestAwardPots:
    def test_single_winner_gets_full_pot(self):
        from ..engine.models import Pot
        pots = [Pot(amount=300, eligible_player_ids=["alice","bob","carol"])]
        winnings = award_pots(pots, {0: ["alice"]})
        assert winnings == {"alice": 300}

    def test_tie_splits_evenly(self):
        from ..engine.models import Pot
        pots = [Pot(amount=200, eligible_player_ids=["alice","bob"])]
        winnings = award_pots(pots, {0: ["alice","bob"]})
        assert winnings["alice"] == 100
        assert winnings["bob"] == 100

    def test_odd_chip_goes_to_first_winner(self):
        from ..engine.models import Pot
        pots = [Pot(amount=301, eligible_player_ids=["alice","bob"])]
        winnings = award_pots(pots, {0: ["alice","bob"]})
        # alice gets the extra chip
        assert winnings["alice"] == 151
        assert winnings["bob"] == 150
        assert sum(winnings.values()) == 301

    def test_multiple_pots(self):
        from ..engine.models import Pot
        pots = [
            Pot(amount=150, eligible_player_ids=["a","b","c"]),
            Pot(amount=100, eligible_player_ids=["b","c"]),
        ]
        winnings = award_pots(pots, {0: ["a"], 1: ["b"]})
        assert winnings["a"] == 150
        assert winnings["b"] == 100
