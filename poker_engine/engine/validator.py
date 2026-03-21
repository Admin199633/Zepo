"""
Action validation layer.

All validation is performed server-side before any state mutation.
Returns a ValidationResult — never trusts client input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import (
    Action, ActionType, GameState, HandPhase, PlayerStatus,
)


@dataclass
class ValidationResult:
    valid: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def fail(cls, code: str, msg: str) -> "ValidationResult":
        return cls(valid=False, error_code=code, error_message=msg)


def validate_action(state: GameState, action: Action) -> ValidationResult:
    """
    Validate a player action against the current game state.
    All checks are independent of client claims.
    """
    hand = state.hand
    if hand is None:
        return ValidationResult.fail("NO_ACTIVE_HAND", "No hand is in progress")

    # Phase must be a betting round
    betting_phases = {
        HandPhase.PRE_FLOP, HandPhase.FLOP,
        HandPhase.TURN, HandPhase.RIVER,
    }
    if hand.phase not in betting_phases:
        return ValidationResult.fail(
            "WRONG_PHASE",
            f"Actions not accepted in phase {hand.phase}",
        )

    # Player must exist and be seated
    player = state.get_player(action.user_id)
    if player is None:
        return ValidationResult.fail("NOT_SEATED", "Player is not at this table")

    # Must be this player's turn
    acting_seat = hand.current_turn_seat
    if acting_seat is None:
        return ValidationResult.fail("NO_ACTIVE_TURN", "No player turn is active")

    if player.seat_index != acting_seat:
        return ValidationResult.fail(
            "NOT_YOUR_TURN",
            f"It is seat {acting_seat}'s turn, not yours (seat {player.seat_index})",
        )

    # Player must be ACTIVE (not folded, not all-in, not sit-out)
    if player.status != PlayerStatus.ACTIVE:
        return ValidationResult.fail(
            "INVALID_STATUS",
            f"Player status is {player.status}, cannot act",
        )

    betting = hand.betting
    player_bet_this_round = betting.bets_by_player.get(action.user_id, 0)
    amount_to_call = betting.current_bet - player_bet_this_round

    match action.action_type:

        case ActionType.FOLD:
            # Always legal during your turn
            return ValidationResult.ok()

        case ActionType.CHECK:
            if amount_to_call > 0:
                return ValidationResult.fail(
                    "CANNOT_CHECK",
                    f"Must call {amount_to_call} or fold (current bet: {betting.current_bet})",
                )
            return ValidationResult.ok()

        case ActionType.CALL:
            if amount_to_call <= 0:
                return ValidationResult.fail(
                    "NOTHING_TO_CALL",
                    "No bet to call — use check",
                )
            if player.stack <= 0:
                return ValidationResult.fail("NO_CHIPS", "Player has no chips")
            # Call amount can be less than full amount if player goes all-in
            return ValidationResult.ok()

        case ActionType.RAISE:
            if player.stack <= 0:
                return ValidationResult.fail("NO_CHIPS", "Player has no chips")
            if action.amount <= 0:
                return ValidationResult.fail(
                    "INVALID_AMOUNT",
                    "Raise amount must be positive",
                )
            # action.amount is total bet (not the increment)
            # Must be at least min_raise_to
            if action.amount < betting.min_raise_to:
                return ValidationResult.fail(
                    "RAISE_TOO_SMALL",
                    f"Minimum raise to {betting.min_raise_to}, got {action.amount}",
                )
            # Cannot raise more than player's total chips available
            max_raise = player_bet_this_round + player.stack
            if action.amount > max_raise:
                return ValidationResult.fail(
                    "RAISE_EXCEEDS_STACK",
                    f"Cannot raise to {action.amount}, max is {max_raise}",
                )
            return ValidationResult.ok()

        case ActionType.ALL_IN:
            if player.stack <= 0:
                return ValidationResult.fail("NO_CHIPS", "Player has no chips")
            return ValidationResult.ok()

        case _:
            return ValidationResult.fail(
                "UNKNOWN_ACTION",
                f"Unknown action type: {action.action_type}",
            )
