"""
Built-in house rules implementations.

Each rule is self-contained and registered by rule_id string.
The engine loads only rules listed in TableConfig.house_rules.
"""
from __future__ import annotations

from ..engine.models import Card, GameState, Rank
from .base import AutoFoldInstruction, BonusTransfer, HouseRule, StraddleInstruction


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[HouseRule]] = {}


def register_rule(cls: type[HouseRule]) -> type[HouseRule]:
    _REGISTRY[cls.rule_id.fget(cls())] = cls  # type: ignore[attr-defined]
    return cls


def get_rule(rule_id: str) -> HouseRule:
    if rule_id not in _REGISTRY:
        raise KeyError(f"Unknown house rule: {rule_id!r}")
    return _REGISTRY[rule_id]()


def load_rules(rule_ids: list[str]) -> list[HouseRule]:
    return [get_rule(rid) for rid in rule_ids]


# ---------------------------------------------------------------------------
# Rule: Bonus 2-7 (win with 2-7 off-suit → everyone pays a bonus)
# ---------------------------------------------------------------------------

@register_rule
class BonusTwoSeven(HouseRule):
    """
    If a player wins a hand with a 2-7 in their hole cards (off-suit),
    every other active player pays them a bonus equal to the big blind.
    """

    @property
    def rule_id(self) -> str:
        return "bonus_27"

    def on_hand_won(
        self,
        winner_id: str,
        winning_cards: list[Card],
        community_cards: list[Card],
        state: GameState,
    ) -> list[BonusTransfer]:
        hole = state.hand.hole_cards.get(winner_id, []) if state.hand else []
        if len(hole) != 2:
            return []

        ranks = {c.rank for c in hole}
        suits = {c.suit for c in hole}
        has_two   = Rank.TWO   in ranks
        has_seven = Rank.SEVEN in ranks
        is_offsuit = len(suits) == 2

        if not (has_two and has_seven and is_offsuit):
            return []

        bonus_amount = state.config.big_blind
        transfers: list[BonusTransfer] = []
        for uid, player in state.players.items():
            if uid == winner_id:
                continue
            if player.stack <= 0:
                continue
            actual = min(player.stack, bonus_amount)
            transfers.append(BonusTransfer(
                from_user_id=uid,
                to_user_id=winner_id,
                amount=actual,
                rule_id=self.rule_id,
                reason="Bonus: 2-7 offsuit win",
            ))
        return transfers


# ---------------------------------------------------------------------------
# Rule: Invalid Hand 7-10 (auto-fold immediately on deal)
# ---------------------------------------------------------------------------

@register_rule
class InvalidHandSevenTen(HouseRule):
    """
    If a player's hole cards contain both a 7 and a 10, auto-fold immediately.
    """

    @property
    def rule_id(self) -> str:
        return "invalid_hand_710"

    def on_hole_cards_dealt(
        self,
        user_id: str,
        cards: list[Card],
        state: GameState,
    ) -> AutoFoldInstruction | None:
        ranks = {c.rank for c in cards}
        if Rank.SEVEN in ranks and Rank.TEN in ranks:
            return AutoFoldInstruction(
                user_id=user_id,
                reason="Invalid hand: 7-10",
            )
        return None


# ---------------------------------------------------------------------------
# Rule: Straddle (optional UTG straddle = 2x BB)
# ---------------------------------------------------------------------------

@register_rule
class StraddleRule(HouseRule):
    """
    The player to the left of the big blind posts a straddle (2×BB)
    before cards are dealt. They act last pre-flop.
    Straddle is automatic when this rule is active.
    """

    @property
    def rule_id(self) -> str:
        return "straddle"

    def on_pre_deal(self, state: GameState) -> StraddleInstruction | None:
        if state.hand is None:
            return None
        bb_seat = state.hand.big_blind_seat
        active_seats = state.seats_that_can_act()
        if len(active_seats) < 3:
            # Need at least 3 players for straddle to make sense
            return None

        # Find seat immediately left of BB
        all_seats = sorted(state.seat_map.keys())
        bb_idx = all_seats.index(bb_seat) if bb_seat in all_seats else -1
        if bb_idx == -1:
            return None
        straddle_seat = all_seats[(bb_idx + 1) % len(all_seats)]

        if straddle_seat not in active_seats:
            return None

        straddle_uid = state.seat_map[straddle_seat]
        player = state.players.get(straddle_uid)
        if player is None or player.stack < state.config.big_blind * 2:
            return None

        return StraddleInstruction(
            user_id=straddle_uid,
            amount=state.config.big_blind * 2,
        )
