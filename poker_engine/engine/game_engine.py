"""
Game Engine — the authoritative state machine.

Public API:
    GameEngine.start_hand(state)  → (new_state, events)
    GameEngine.apply_action(state, action)  → (new_state, events)
    GameEngine.handle_timeout(state)  → (new_state, events)

All methods are pure: they receive a GameState and return a new GameState
plus a list of EngineEvents. No I/O, no side effects.

The engine never mutates state in-place — it returns a new (copied) state
so that the caller can diff, persist, or discard as needed.
"""
from __future__ import annotations

import copy
import time
import uuid
from typing import TYPE_CHECKING

from .deck import deal_cards, fresh_shuffled_deck
from .evaluator import best_hand, compare_hands
from .models import (
    Action, ActionType, BettingState, EngineEvent,
    EvtBlindsPosted, EvtBonusAwarded, EvtCardsDealt,
    EvtCommunityCards, EvtHandResult, EvtPhaseChanged,
    EvtPlayerActed, EvtPlayerStatus, EvtPotUpdated, EvtTurnChanged,
    GameState, HandPhase, HandState, Pot, PlayerStatus,
)
from .pot_calculator import award_pots, calculate_pots
from .validator import validate_action

if TYPE_CHECKING:
    from ..rules.base import HouseRule

# How many consecutive timeouts before auto-sit-out
TIMEOUT_SIT_OUT_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class GameEngine:
    """
    Stateless engine — all state is passed in and returned as new objects.
    House rules are injected at construction.
    """

    def __init__(self, rules: list["HouseRule"] | None = None) -> None:
        self._rules: list["HouseRule"] = rules or []

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def start_hand(
        self, state: GameState
    ) -> tuple[GameState, list[EngineEvent]]:
        """
        Begin a new hand.  Requires ≥ 2 active players with chips.
        Transitions: WAITING_FOR_PLAYERS / HAND_END → START_HAND → DEAL_HOLE_CARDS → PRE_FLOP
        """
        assert state.phase in (HandPhase.WAITING_FOR_PLAYERS, HandPhase.HAND_END), (
            f"Cannot start hand from phase {state.phase}"
        )
        state = copy.deepcopy(state)
        events: list[EngineEvent] = []

        eligible = self._eligible_players(state)
        assert len(eligible) >= 2, "Need at least 2 players to start a hand"

        # Reset statuses
        for uid, p in state.players.items():
            if p.status == PlayerStatus.WAITING:
                p.status = PlayerStatus.ACTIVE
            elif p.status in (PlayerStatus.FOLDED, PlayerStatus.ALL_IN):
                p.status = PlayerStatus.ACTIVE if p.stack > 0 else PlayerStatus.SIT_OUT

        state.hand_number += 1
        state.phase = HandPhase.START_HAND
        events.append(EvtPhaseChanged(phase=HandPhase.START_HAND))

        # Advance dealer button
        dealer_seat = self._next_dealer(state)

        # Post blinds
        sb_seat, bb_seat = self._blind_seats(state, dealer_seat)
        sb_uid = state.seat_map[sb_seat]
        bb_uid = state.seat_map[bb_seat]

        deck = fresh_shuffled_deck()

        # Build hand state before posting blinds
        hand = HandState(
            hand_id=str(uuid.uuid4()),
            phase=HandPhase.START_HAND,
            deck=deck,
            hole_cards={},
            community_cards=[],
            pots=[],
            betting=BettingState(
                current_bet=0,
                bets_by_player={},
                min_raise_to=state.config.big_blind,
                last_aggressor_seat=None,
                acted_seats=set(),
            ),
            dealer_seat=dealer_seat,
            small_blind_seat=sb_seat,
            big_blind_seat=bb_seat,
            current_turn_seat=None,
            turn_deadline=None,
            winners=None,
            stacks_at_start={uid: p.stack for uid, p in state.players.items()},
        )
        state.hand = hand

        # Post small blind
        sb_amount = self._post_forced_bet(state, sb_uid, state.config.small_blind)
        # Post big blind
        bb_amount = self._post_forced_bet(state, bb_uid, state.config.big_blind)

        events.append(EvtBlindsPosted(
            small_blind_user_id=sb_uid,
            small_blind_amount=sb_amount,
            big_blind_user_id=bb_uid,
            big_blind_amount=bb_amount,
        ))

        # House rule: straddle
        for rule in self._rules:
            instr = rule.on_pre_deal(state)
            if instr is not None:
                straddle_amount = self._post_forced_bet(
                    state, instr.user_id, instr.amount
                )
                events.append(EvtPlayerActed(
                    user_id=instr.user_id,
                    action_type=ActionType.RAISE,
                    amount=straddle_amount,
                    stack_remaining=state.players[instr.user_id].stack,
                ))

        # Deal hole cards
        state, deal_events = self._deal_hole_cards(state)
        events.extend(deal_events)

        # Advance to PRE_FLOP betting
        state, pre_flop_events = self._begin_betting_round(state, HandPhase.PRE_FLOP)
        events.extend(pre_flop_events)

        return state, events

    def apply_action(
        self, state: GameState, action: Action
    ) -> tuple[GameState, list[EngineEvent]]:
        """
        Validate and apply a player action.
        Returns (new_state, events).  Raises ValueError on invalid action.
        """
        result = validate_action(state, action)
        if not result.valid:
            raise ValueError(f"{result.error_code}: {result.error_message}")

        state = copy.deepcopy(state)
        events: list[EngineEvent] = []

        player = state.players[action.user_id]
        hand   = state.hand
        assert hand is not None

        # Reset timeout counter on voluntary action
        player.timeout_count = 0

        match action.action_type:

            case ActionType.FOLD:
                player.status = PlayerStatus.FOLDED
                hand.betting.acted_seats.add(player.seat_index)
                events.append(EvtPlayerActed(
                    user_id=action.user_id,
                    action_type=ActionType.FOLD,
                    amount=0,
                    stack_remaining=player.stack,
                ))
                events.append(EvtPlayerStatus(
                    user_id=action.user_id,
                    status=PlayerStatus.FOLDED,
                    stack=player.stack,
                ))

            case ActionType.CHECK:
                hand.betting.acted_seats.add(player.seat_index)
                events.append(EvtPlayerActed(
                    user_id=action.user_id,
                    action_type=ActionType.CHECK,
                    amount=0,
                    stack_remaining=player.stack,
                ))

            case ActionType.CALL:
                amount_to_call = hand.betting.current_bet - hand.betting.bets_by_player.get(action.user_id, 0)
                actual_call = min(amount_to_call, player.stack)  # may be all-in call
                player.stack -= actual_call
                hand.betting.bets_by_player[action.user_id] = (
                    hand.betting.bets_by_player.get(action.user_id, 0) + actual_call
                )
                hand.betting.acted_seats.add(player.seat_index)
                if player.stack == 0:
                    player.status = PlayerStatus.ALL_IN
                    events.append(EvtPlayerStatus(
                        user_id=action.user_id, status=PlayerStatus.ALL_IN, stack=0
                    ))
                events.append(EvtPlayerActed(
                    user_id=action.user_id,
                    action_type=ActionType.CALL,
                    amount=actual_call,
                    stack_remaining=player.stack,
                ))

            case ActionType.RAISE:
                # action.amount is the total bet for this round (raise-to)
                existing_bet = hand.betting.bets_by_player.get(action.user_id, 0)
                chips_needed = action.amount - existing_bet
                player.stack -= chips_needed
                hand.betting.bets_by_player[action.user_id] = action.amount

                # Update min raise: next raise must be at least as large
                raise_increment = action.amount - hand.betting.current_bet
                hand.betting.current_bet = action.amount
                hand.betting.min_raise_to = action.amount + raise_increment
                hand.betting.last_aggressor_seat = player.seat_index
                hand.betting.acted_seats = {player.seat_index}  # others must re-act

                if player.stack == 0:
                    player.status = PlayerStatus.ALL_IN
                    events.append(EvtPlayerStatus(
                        user_id=action.user_id, status=PlayerStatus.ALL_IN, stack=0
                    ))
                events.append(EvtPlayerActed(
                    user_id=action.user_id,
                    action_type=ActionType.RAISE,
                    amount=chips_needed,
                    stack_remaining=player.stack,
                ))

            case ActionType.ALL_IN:
                existing_bet = hand.betting.bets_by_player.get(action.user_id, 0)
                all_in_total = existing_bet + player.stack
                player.stack = 0
                player.status = PlayerStatus.ALL_IN
                hand.betting.bets_by_player[action.user_id] = all_in_total

                if all_in_total > hand.betting.current_bet:
                    # This is a raise
                    raise_increment = all_in_total - hand.betting.current_bet
                    hand.betting.min_raise_to = all_in_total + raise_increment
                    hand.betting.current_bet = all_in_total
                    hand.betting.last_aggressor_seat = player.seat_index
                    hand.betting.acted_seats = {player.seat_index}
                else:
                    hand.betting.acted_seats.add(player.seat_index)

                events.append(EvtPlayerStatus(
                    user_id=action.user_id, status=PlayerStatus.ALL_IN, stack=0
                ))
                events.append(EvtPlayerActed(
                    user_id=action.user_id,
                    action_type=ActionType.ALL_IN,
                    amount=all_in_total,
                    stack_remaining=0,
                ))

        self._update_pots(state)
        events.append(EvtPotUpdated(pots=list(hand.pots)))

        # Advance turn or phase
        state, advance_events = self._advance(state)
        events.extend(advance_events)

        return state, events

    def handle_timeout(
        self, state: GameState
    ) -> tuple[GameState, list[EngineEvent]]:
        """
        Called by the session manager when a player's turn timer expires.
        Auto-checks if possible, else auto-folds.
        After TIMEOUT_SIT_OUT_THRESHOLD consecutive timeouts → sit out.
        """
        state = copy.deepcopy(state)
        events: list[EngineEvent] = []
        hand = state.hand
        if hand is None or hand.current_turn_seat is None:
            return state, events

        uid = state.seat_map.get(hand.current_turn_seat)
        if uid is None:
            return state, events

        # Capture count BEFORE apply_action resets it
        prev_timeout_count = state.players[uid].timeout_count

        # Determine auto-action
        can_check = (
            hand.betting.current_bet == hand.betting.bets_by_player.get(uid, 0)
        )
        auto_action = ActionType.CHECK if can_check else ActionType.FOLD
        synthetic = Action(user_id=uid, action_type=auto_action)

        state, action_events = self.apply_action(state, synthetic)
        events.extend(action_events)

        # apply_action reset timeout_count to 0 (treats as voluntary); restore + increment
        player = state.players[uid]
        player.timeout_count = prev_timeout_count + 1

        # Sit out if too many consecutive timeouts
        if player.timeout_count >= TIMEOUT_SIT_OUT_THRESHOLD:
            player.status = PlayerStatus.SIT_OUT
            events.append(EvtPlayerStatus(
                user_id=uid, status=PlayerStatus.SIT_OUT, stack=player.stack
            ))

        return state, events

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _eligible_players(self, state: GameState) -> list[str]:
        """User IDs of players who can participate in a new hand."""
        return [
            uid for uid, p in state.players.items()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.WAITING)
            and p.stack > 0
        ]

    def _next_dealer(self, state: GameState) -> int:
        """
        Return the seat index for the next dealer.
        On first hand, starts at lowest seat. Subsequently advances clockwise.
        """
        seats = sorted(state.seat_map.keys())
        if state.hand is None:
            return seats[0]
        current_dealer = state.hand.dealer_seat
        idx = seats.index(current_dealer) if current_dealer in seats else -1
        next_idx = (idx + 1) % len(seats)
        # Skip sit-out players
        for _ in range(len(seats)):
            candidate = seats[next_idx]
            uid = state.seat_map[candidate]
            if state.players[uid].status == PlayerStatus.ACTIVE:
                return candidate
            next_idx = (next_idx + 1) % len(seats)
        return seats[(idx + 1) % len(seats)]

    def _blind_seats(
        self, state: GameState, dealer_seat: int
    ) -> tuple[int, int]:
        """Return (small_blind_seat, big_blind_seat) after the dealer."""
        seats = sorted(state.seat_map.keys())
        active_seats = [
            s for s in seats
            if state.players[state.seat_map[s]].status == PlayerStatus.ACTIVE
            and state.players[state.seat_map[s]].stack > 0
        ]
        n = len(active_seats)
        assert n >= 2

        if n == 2:
            # Heads-up: dealer = small blind
            d_idx = active_seats.index(dealer_seat) if dealer_seat in active_seats else 0
            sb_idx = d_idx
            bb_idx = (d_idx + 1) % n
        else:
            d_idx = active_seats.index(dealer_seat) if dealer_seat in active_seats else 0
            sb_idx = (d_idx + 1) % n
            bb_idx = (d_idx + 2) % n

        return active_seats[sb_idx], active_seats[bb_idx]

    def _post_forced_bet(
        self, state: GameState, uid: str, amount: int
    ) -> int:
        """
        Deduct a forced bet (blind/straddle) from player stack.
        Returns actual amount posted (may be less if stack is small).
        Mutates state in place (called only during hand setup before return).
        """
        player = state.players[uid]
        actual = min(amount, player.stack)
        player.stack -= actual
        hand = state.hand
        assert hand is not None

        existing = hand.betting.bets_by_player.get(uid, 0)
        hand.betting.bets_by_player[uid] = existing + actual

        if actual + existing > hand.betting.current_bet:
            hand.betting.current_bet = actual + existing
            hand.betting.min_raise_to = hand.betting.current_bet + amount

        if player.stack == 0:
            player.status = PlayerStatus.ALL_IN

        return actual

    def _deal_hole_cards(
        self, state: GameState
    ) -> tuple[GameState, list[EngineEvent]]:
        """Deal 2 hole cards to each active player. Apply house rules."""
        hand = state.hand
        assert hand is not None
        events: list[EngineEvent] = []
        hand.phase = HandPhase.DEAL_HOLE_CARDS

        active_seats = sorted([
            seat for seat, uid in state.seat_map.items()
            if state.players[uid].status == PlayerStatus.ACTIVE
        ])

        for seat in active_seats:
            uid = state.seat_map[seat]
            cards, hand.deck = deal_cards(hand.deck, 2)
            hand.hole_cards[uid] = cards
            events.append(EvtCardsDealt(user_id=uid, cards=list(cards)))

        # House rule: invalid hand checks
        auto_folds: list[str] = []
        for rule in self._rules:
            for seat in active_seats:
                uid = state.seat_map[seat]
                instr = rule.on_hole_cards_dealt(
                    uid, hand.hole_cards[uid], state
                )
                if instr is not None:
                    auto_folds.append(instr.user_id)
                    events.append(EvtPlayerActed(
                        user_id=instr.user_id,
                        action_type=ActionType.FOLD,
                        amount=0,
                        stack_remaining=state.players[instr.user_id].stack,
                    ))

        for uid in auto_folds:
            state.players[uid].status = PlayerStatus.FOLDED

        return state, events

    def _begin_betting_round(
        self, state: GameState, phase: HandPhase
    ) -> tuple[GameState, list[EngineEvent]]:
        """
        Open a new betting round.
        Resets per-round bet tracking (NOT pots — those carry over).
        Determines first-to-act seat and emits PHASE_CHANGED + TURN_CHANGED.
        """
        hand = state.hand
        assert hand is not None
        events: list[EngineEvent] = []

        hand.phase = phase
        state.phase = phase
        events.append(EvtPhaseChanged(phase=phase))

        if phase == HandPhase.PRE_FLOP:
            # Pre-flop: BB's bet is already in; reset acted_seats
            # but do NOT reset current_bet (BB counts as a bet)
            hand.betting.acted_seats = set()
        else:
            # Post-flop rounds: fresh betting starts at 0
            hand.betting.current_bet = 0
            hand.betting.bets_by_player = {}
            hand.betting.min_raise_to = state.config.big_blind
            hand.betting.last_aggressor_seat = None
            hand.betting.acted_seats = set()

        # Check if betting can even happen
        can_act = state.seats_that_can_act()
        if len(can_act) <= 1:
            # No meaningful betting possible — run out the board
            state, runout_events = self._run_out_board(state)
            return state, events + runout_events

        first_seat = self._first_to_act(state, phase)
        if first_seat is None:
            state, runout_events = self._run_out_board(state)
            return state, events + runout_events

        hand.current_turn_seat = first_seat
        hand.turn_deadline = time.time() + state.config.turn_timer_seconds
        uid = state.seat_map[first_seat]
        events.append(EvtTurnChanged(
            seat=first_seat,
            user_id=uid,
            deadline=hand.turn_deadline,
        ))

        return state, events

    def _first_to_act(
        self, state: GameState, phase: HandPhase
    ) -> int | None:
        """
        Determine first-to-act seat for the given phase.
        Pre-flop: UTG (left of BB, or straddle).
        Post-flop: first active player left of dealer.
        """
        hand = state.hand
        assert hand is not None
        seats = sorted(state.seat_map.keys())
        active_can_act = state.seats_that_can_act()

        if not active_can_act:
            return None

        if phase == HandPhase.PRE_FLOP:
            # Start left of the current_bet poster (BB or straddle)
            anchor = hand.big_blind_seat
            # If straddle was posted, find the highest non-BB poster
            straddle_seat = self._find_straddle_seat(state)
            if straddle_seat is not None:
                anchor = straddle_seat
            idx = seats.index(anchor) if anchor in seats else 0
            # UTG = seat after the anchor
            for i in range(1, len(seats) + 1):
                candidate = seats[(idx + i) % len(seats)]
                if candidate in active_can_act:
                    return candidate
        else:
            # Post-flop: left of dealer
            d_idx = seats.index(hand.dealer_seat) if hand.dealer_seat in seats else 0
            for i in range(1, len(seats) + 1):
                candidate = seats[(d_idx + i) % len(seats)]
                if candidate in active_can_act:
                    return candidate

        return None

    def _find_straddle_seat(self, state: GameState) -> int | None:
        """Return seat of straddle poster if one exists, else None."""
        if state.hand is None:
            return None
        bb_amount = state.config.big_blind
        # Straddle = someone bet 2×BB as forced bet
        for uid, bet in state.hand.betting.bets_by_player.items():
            if bet == bb_amount * 2:
                player = state.players.get(uid)
                if player:
                    return player.seat_index
        return None

    def _advance(
        self, state: GameState
    ) -> tuple[GameState, list[EngineEvent]]:
        """
        After an action, determine whether to:
          (a) move to next player in current round
          (b) advance to next phase
          (c) go to showdown / hand_end
        """
        events: list[EngineEvent] = []
        hand = state.hand
        assert hand is not None

        # Check if only 1 player remains (everyone else folded)
        active_in_hand = [
            uid for uid, p in state.players.items()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
        ]
        if len(active_in_hand) == 1:
            # Only one player left — they win without showdown
            state, end_events = self._award_hand(state, showdown=False)
            return state, end_events

        # Check if betting round is complete
        if self._betting_round_complete(state):
            self._update_pots(state)
            state, next_events = self._next_phase(state)
            return state, next_events

        # Move to next player
        next_seat = self._next_active_seat(state)
        if next_seat is None:
            # This shouldn't happen — but guard it
            state, next_events = self._next_phase(state)
            return state, next_events

        hand.current_turn_seat = next_seat
        hand.turn_deadline = time.time() + state.config.turn_timer_seconds
        uid = state.seat_map[next_seat]
        events.append(EvtTurnChanged(
            seat=next_seat,
            user_id=uid,
            deadline=hand.turn_deadline,
        ))

        return state, events

    def _betting_round_complete(self, state: GameState) -> bool:
        """
        Betting round is complete when:
        - All active (non-all-in) players have acted, AND
        - All active players' bets equal the current_bet (or they are all-in)
        """
        hand = state.hand
        assert hand is not None
        active_can_act = state.seats_that_can_act()

        if not active_can_act:
            return True

        for seat in active_can_act:
            uid = state.seat_map[seat]
            # Must have acted this round
            if seat not in hand.betting.acted_seats:
                return False
            # Must have matched current bet
            player_bet = hand.betting.bets_by_player.get(uid, 0)
            if player_bet < hand.betting.current_bet:
                return False

        return True

    def _next_active_seat(self, state: GameState) -> int | None:
        """Next seat after current_turn_seat that can still act."""
        hand = state.hand
        assert hand is not None
        if hand.current_turn_seat is None:
            return None

        seats = sorted(state.seat_map.keys())
        can_act = state.seats_that_can_act()
        if not can_act:
            return None

        cur_idx = seats.index(hand.current_turn_seat) if hand.current_turn_seat in seats else 0
        for i in range(1, len(seats) + 1):
            candidate = seats[(cur_idx + i) % len(seats)]
            if candidate in can_act:
                uid = state.seat_map[candidate]
                # Check they still need to act
                if (
                    candidate not in hand.betting.acted_seats
                    or hand.betting.bets_by_player.get(uid, 0) < hand.betting.current_bet
                ):
                    return candidate

        return None

    def _next_phase(
        self, state: GameState
    ) -> tuple[GameState, list[EngineEvent]]:
        """Advance the hand to the next phase (Flop → Turn → River → Showdown)."""
        hand = state.hand
        assert hand is not None
        events: list[EngineEvent] = []

        phase_order = [
            HandPhase.PRE_FLOP, HandPhase.FLOP,
            HandPhase.TURN, HandPhase.RIVER, HandPhase.SHOWDOWN,
        ]
        current_idx = phase_order.index(hand.phase) if hand.phase in phase_order else 0
        next_phase = phase_order[current_idx + 1] if current_idx + 1 < len(phase_order) else HandPhase.SHOWDOWN

        # Deal community cards
        if next_phase == HandPhase.FLOP:
            cards, hand.deck = deal_cards(hand.deck, 3)
            hand.community_cards.extend(cards)
            events.append(EvtCommunityCards(cards=list(cards), phase=HandPhase.FLOP))
            state, betting_events = self._begin_betting_round(state, HandPhase.FLOP)
            return state, events + betting_events

        elif next_phase == HandPhase.TURN:
            cards, hand.deck = deal_cards(hand.deck, 1)
            hand.community_cards.extend(cards)
            events.append(EvtCommunityCards(cards=list(cards), phase=HandPhase.TURN))
            state, betting_events = self._begin_betting_round(state, HandPhase.TURN)
            return state, events + betting_events

        elif next_phase == HandPhase.RIVER:
            cards, hand.deck = deal_cards(hand.deck, 1)
            hand.community_cards.extend(cards)
            events.append(EvtCommunityCards(cards=list(cards), phase=HandPhase.RIVER))
            state, betting_events = self._begin_betting_round(state, HandPhase.RIVER)
            return state, events + betting_events

        elif next_phase == HandPhase.SHOWDOWN:
            state, showdown_events = self._award_hand(state, showdown=True)
            return state, events + showdown_events

        return state, events

    def _run_out_board(
        self, state: GameState
    ) -> tuple[GameState, list[EngineEvent]]:
        """
        When only all-in players remain (or 1 active + all-in players),
        deal remaining community cards without betting, then go to showdown.
        """
        hand = state.hand
        assert hand is not None
        events: list[EngineEvent] = []
        hand.current_turn_seat = None

        cards_needed = 5 - len(hand.community_cards)
        if cards_needed > 0:
            cards, hand.deck = deal_cards(hand.deck, cards_needed)
            hand.community_cards.extend(cards)
            events.append(EvtCommunityCards(cards=list(cards), phase=HandPhase.SHOWDOWN))

        state, end_events = self._award_hand(state, showdown=True)
        return state, events + end_events

    def _update_pots(self, state: GameState) -> None:
        """
        Recalculate all pots from current bets.
        Mutates state.hand.pots in place.
        """
        hand = state.hand
        if hand is None:
            return
        active_ids = {
            uid for uid, p in state.players.items()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
        }
        # contributions = bets this round + previously committed
        # For simplicity: track total_committed per player across all rounds
        # We do this by accumulating into pots incrementally each round end
        # For pot calculation we use bets_by_player which reflects this round
        # + the existing pot amounts. Full implementation tracks total_in_hand.
        contributions = self._total_contributions(state)
        hand.pots = calculate_pots(contributions, active_ids)

    def _total_contributions(self, state: GameState) -> dict[str, int]:
        """
        Total chips put in by each player across ALL betting rounds of this hand.
        = (starting stack - current stack)
        """
        hand = state.hand
        assert hand is not None
        result: dict[str, int] = {}
        for uid, start_stack in hand.stacks_at_start.items():
            player = state.players.get(uid)
            current_stack = player.stack if player else 0
            result[uid] = start_stack - current_stack
        return result

    def _award_hand(
        self, state: GameState, showdown: bool
    ) -> tuple[GameState, list[EngineEvent]]:
        """Determine winners, distribute pots, apply house rules, emit HAND_RESULT."""
        hand = state.hand
        assert hand is not None
        events: list[EngineEvent] = []

        self._update_pots(state)

        active_ids = [
            uid for uid, p in state.players.items()
            if p.status in (PlayerStatus.ACTIVE, PlayerStatus.ALL_IN)
        ]

        # Determine winners per pot
        winners_by_pot: dict[int, list[str]] = {}
        showdown_cards: dict[str, list[Card]] = {}

        for i, pot in enumerate(hand.pots):
            eligible = [uid for uid in pot.eligible_player_ids if uid in active_ids]
            if len(eligible) == 1:
                winners_by_pot[i] = eligible
            else:
                hole_cards_eligible = {
                    uid: hand.hole_cards[uid]
                    for uid in eligible
                    if uid in hand.hole_cards
                }
                winners = compare_hands(hole_cards_eligible, hand.community_cards)
                winners_by_pot[i] = winners
                if showdown:
                    showdown_cards.update({
                        uid: hand.hole_cards[uid]
                        for uid in eligible
                        if uid in hand.hole_cards
                    })

        winnings = award_pots(hand.pots, winners_by_pot)

        # Apply winnings to stacks
        for uid, amount in winnings.items():
            state.players[uid].stack += amount

        # House rule: bonus transfers
        bonus_events: list[EngineEvent] = []
        for uid, amount in winnings.items():
            if amount <= 0:
                continue
            winner_cards = hand.hole_cards.get(uid, [])
            for rule in self._rules:
                transfers = rule.on_hand_won(
                    uid, winner_cards, hand.community_cards, state
                )
                for t in transfers:
                    payer = state.players.get(t.from_user_id)
                    recipient = state.players.get(t.to_user_id)
                    if payer and recipient and payer.stack >= t.amount:
                        payer.stack -= t.amount
                        recipient.stack += t.amount
                        bonus_events.append(EvtBonusAwarded(
                            rule_id=t.rule_id,
                            from_user_id=t.from_user_id,
                            to_user_id=t.to_user_id,
                            amount=t.amount,
                        ))

        # Build per-player hand descriptions for showdown participants
        hand_descriptions: dict[str, list] = {}
        if showdown:
            for uid, cards in showdown_cards.items():
                all_cards = list(cards) + list(hand.community_cards)
                if len(all_cards) >= 5:
                    hand_descriptions[uid] = best_hand(all_cards).category_name
                else:
                    hand_descriptions[uid] = ""

        # Build winner list for the event
        winner_records = []
        all_pot_winners: set[str] = set()
        for pot_idx, winner_ids in winners_by_pot.items():
            pot = hand.pots[pot_idx]
            all_pot_winners.update(winner_ids)
            desc = hand_descriptions.get(winner_ids[0], "uncontested") if winner_ids and showdown else "uncontested"
            winner_records.append({
                "pot_index": pot_idx,
                "pot_amount": pot.amount,
                "winner_ids": winner_ids,
                "hand_description": desc,
            })

        hand.winners = winner_records
        hand.phase = HandPhase.HAND_END
        state.phase = HandPhase.HAND_END
        hand.current_turn_seat = None

        events.append(EvtPhaseChanged(phase=HandPhase.HAND_END))
        events.append(EvtHandResult(
            winners=winner_records,
            showdown_cards=showdown_cards,
            pot_total=sum(p.amount for p in hand.pots),
            winnings=winnings,
            hand_descriptions=hand_descriptions,
        ))
        events.extend(bonus_events)

        # Emit updated stacks
        for uid in winnings:
            events.append(EvtPlayerStatus(
                user_id=uid,
                status=state.players[uid].status,
                stack=state.players[uid].stack,
            ))

        # Transition ready for next hand
        state.phase = HandPhase.WAITING_FOR_PLAYERS
        events.append(EvtPhaseChanged(phase=HandPhase.WAITING_FOR_PLAYERS))

        return state, events
