"""
View builder: produce filtered snapshots of GameState for each recipient.

CRITICAL security invariant:
  - Players receive only their own hole cards; opponents shown as masked cards
  - Spectators receive no hole cards until showdown
  - Deck is NEVER included in any client payload

These functions are the single enforcement point for the "no data leaks" rule.
"""
from __future__ import annotations

import time

from .models import Card, GameState, HandPhase, PlayerStatus


_MASKED_CARD = {"rank": "?", "suit": "?"}


def _serialize_card(card: Card) -> dict:
    return {"rank": card.rank.value, "suit": card.suit.value}


def _masked_cards(n: int = 2) -> list[dict]:
    return [_MASKED_CARD] * n


def build_player_view(state: GameState, for_user_id: str) -> dict:
    """
    Full game state as seen by a specific seated player.
    Own hole cards: revealed.
    Opponents' hole cards: masked (["??","??"]).
    Revealed at showdown only (via HAND_RESULT event, not in snapshot).
    """
    return _build_view(state, viewer_user_id=for_user_id, is_spectator=False)


def build_spectator_view(state: GameState) -> dict:
    """
    Full game state as seen by a spectator.
    ALL hole cards masked at all times (until HAND_RESULT event is emitted).
    """
    return _build_view(state, viewer_user_id=None, is_spectator=True)


def _build_view(
    state: GameState,
    viewer_user_id: str | None,
    is_spectator: bool,
) -> dict:
    hand = state.hand

    players_view = {}
    for uid, p in state.players.items():
        players_view[uid] = {
            "user_id": uid,
            "display_name": p.display_name,
            "seat_index": p.seat_index,
            "stack": p.stack,
            "status": p.status.value,
            "is_connected": p.is_connected,
        }

    hand_view: dict | None = None
    if hand is not None:
        # Build hole cards view — per-recipient filtering
        hole_cards_view: dict[str, list[dict]] = {}
        is_showdown = hand.phase in (HandPhase.SHOWDOWN, HandPhase.HAND_END)

        for uid in hand.hole_cards:
            # Folded players' cards are NEVER revealed — not even at showdown.
            # Only non-folded (ACTIVE / ALL_IN) players who reached showdown show cards.
            player = state.players.get(uid)
            is_folded = player is not None and player.status == PlayerStatus.FOLDED

            if uid == viewer_user_id and not is_spectator:
                # Own cards: always revealed (even if you folded, you can see your own)
                hole_cards_view[uid] = [_serialize_card(c) for c in hand.hole_cards[uid]]
            elif is_showdown and hand.winners is not None and not is_folded:
                # Showdown reveal: non-folded opponents / all spectator-visible players
                hole_cards_view[uid] = [_serialize_card(c) for c in hand.hole_cards[uid]]
            else:
                hole_cards_view[uid] = _masked_cards()

        hand_view = {
            "hand_id": hand.hand_id,
            "phase": hand.phase.value,
            "hole_cards": hole_cards_view,
            # deck is NEVER included
            "community_cards": [_serialize_card(c) for c in hand.community_cards],
            "pots": [
                {
                    "amount": pot.amount,
                    "eligible_player_ids": pot.eligible_player_ids,
                }
                for pot in hand.pots
            ],
            "betting": {
                "current_bet": hand.betting.current_bet,
                "min_raise_to": hand.betting.min_raise_to,
                "bets_by_player": dict(hand.betting.bets_by_player),
            },
            "dealer_seat": hand.dealer_seat,
            "small_blind_seat": hand.small_blind_seat,
            "big_blind_seat": hand.big_blind_seat,
            "current_turn_seat": hand.current_turn_seat,
            "turn_deadline": hand.turn_deadline,
            "turn_seconds_remaining": (
                max(0, round(hand.turn_deadline - time.time()))
                if hand.turn_deadline is not None
                else None
            ),
            "winners": hand.winners,
        }

    return {
        "table_id": state.table_id,
        "club_id": state.club_id,
        "phase": state.phase.value,
        "hand_number": state.hand_number,
        "players": players_view,
        "seat_map": {str(k): v for k, v in state.seat_map.items()},
        "config": {
            "starting_stack": state.config.starting_stack,
            "small_blind": state.config.small_blind,
            "big_blind": state.config.big_blind,
            "turn_timer_seconds": state.config.turn_timer_seconds,
            "max_players": state.config.max_players,
            "house_rules": state.config.house_rules,
        },
        "hand": hand_view,
    }
