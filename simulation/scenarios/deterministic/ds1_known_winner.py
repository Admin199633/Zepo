"""
DS1 — Two-Player Hand with a Known Winner

Deck (Recipe A):
  deck[0:2] = A♠ K♠ → owner (seat 0) hole cards
  deck[2:4] = 2♥ 3♦ → joiner (seat 1) hole cards
  deck[4] = Q♠  → flop 1
  deck[5] = J♠  → flop 2
  deck[6] = T♠  → flop 3
  deck[7] = 2♣  → turn
  deck[8] = 3♣  → river

Owner holds A♠ K♠: Royal Flush on the Q♠ J♠ T♠ board.
Joiner holds 2♥ 3♦: best possible hand is a weak straight or pair.
Expected winner: the player whose CARDS_DEALT contains A♠ K♠.

Assertions:
  - CARDS_DEALT confirms which user_id holds A♠ K♠ (seat order not assumed)
  - HAND_RESULT winners[0]["winner_ids"] contains that user_id
  - No ERROR events
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.deck_control import RECIPE_A, complete_deck, injected_deck
from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555700")

    with injected_deck(complete_deck(RECIPE_A)):
        with owner.connect(table_id):
            with joiner.connect(table_id):
                owner.send_join(table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")

                joiner.send_join(table_id, "player")
                joiner.drain_until("STATE_SNAPSHOT")

                owner.drain_until("BLINDS_POSTED")
                joiner.drain_until("BLINDS_POSTED")

                _drive_to_showdown(owner, joiner, table_id)

    # --- Assertions (outside WS contexts; logs are complete) ---

    # Confirm hole card assignment from CARDS_DEALT payloads
    owner_dealt = owner.log.of_type("CARDS_DEALT")
    joiner_dealt = joiner.log.of_type("CARDS_DEALT")

    assert len(owner_dealt) == 1, f"owner must receive exactly 1 CARDS_DEALT, got {len(owner_dealt)}"
    assert len(joiner_dealt) == 1, f"joiner must receive exactly 1 CARDS_DEALT, got {len(joiner_dealt)}"

    owner_cards = {(c["rank"], c["suit"]) for c in owner_dealt[0].payload["your_cards"]}
    joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt[0].payload["your_cards"]}

    # Recipe A: seat0 gets deck[0:2] = A♠ K♠, seat1 gets deck[2:4] = 2♥ 3♦.
    # Seat assignment is first-come; owner always creates and joins first.
    # We verify via CARDS_DEALT to be robust to any seat ordering edge cases.
    royal_flush_hole = {("A", "S"), ("K", "S")}
    weak_hole = {("2", "H"), ("3", "D")}

    if royal_flush_hole <= owner_cards:
        expected_winner_id = owner.user_id
        assert weak_hole <= joiner_cards, f"joiner should hold weak cards, got {joiner_cards}"
    elif royal_flush_hole <= joiner_cards:
        expected_winner_id = joiner.user_id
        assert weak_hole <= owner_cards, f"owner should hold weak cards, got {owner_cards}"
    else:
        raise AssertionError(
            f"Neither player holds the Royal Flush hole cards A♠ K♠. "
            f"Owner: {owner_cards}, Joiner: {joiner_cards}"
        )

    # Assert winner from HAND_RESULT
    hand_result = owner.log.of_type("HAND_RESULT")
    assert hand_result, "owner must receive HAND_RESULT"
    winners = hand_result[0].payload["winners"]
    assert len(winners) == 1, f"must be exactly 1 winner record (no split pot), got {len(winners)}"

    winner_ids = winners[0]["winner_ids"]
    assert expected_winner_id in winner_ids, (
        f"Expected {expected_winner_id} to win (Royal Flush), "
        f"but winner_ids={winner_ids}"
    )

    assert hand_result[0].payload["pot_total"] > 0, "pot must be > 0"

    assert not owner.log.has_type("ERROR"), f"unexpected ERROR in owner log: {owner.log.of_type('ERROR')}"
    assert not joiner.log.has_type("ERROR"), f"unexpected ERROR in joiner log: {joiner.log.of_type('ERROR')}"


def _drive_to_showdown(owner, joiner, table_id: str, max_iter: int = 120) -> None:
    """
    Drive both players through a complete hand using check/call tracking.
    Same can_check logic as s1_two_player_hand._drive_hand.
    """
    players = {owner.user_id: owner, joiner.user_id: joiner}
    can_check = False  # entered after BLINDS_POSTED; BB bet outstanding

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            if not joiner.log.has_type("HAND_RESULT"):
                joiner.drain_until("HAND_RESULT", max_msgs=100)
            return

        elif t == "BLINDS_POSTED":
            can_check = False

        elif t == "COMMUNITY_CARDS":
            can_check = True

        elif t == "PHASE_CHANGED":
            phase = msg["payload"].get("phase", "")
            if phase in ("FLOP", "TURN", "RIVER"):
                can_check = True

        elif t == "PLAYER_ACTED":
            action = msg["payload"].get("action", "")
            if action == "raise":
                can_check = False
            elif action == "call":
                can_check = True

        elif t == "TURN_CHANGED":
            acting_uid = msg["payload"].get("user_id")
            actor = players.get(acting_uid)
            if actor:
                actor.send_action(table_id, "check" if can_check else "call")

    raise AssertionError(
        f"HAND_RESULT not reached within {max_iter} iterations. "
        f"Owner event types: {owner.log.types()[-20:]}"
    )
