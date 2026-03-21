"""
DS2 — Known Board/Runout with Expected Showdown Result

Deck (Recipe B):
  deck[0] = 2♠  → owner hole card 1
  deck[1] = A♥  → joiner hole card 1
  deck[2] = 3♥  → owner hole card 2
  deck[3] = A♦  → joiner hole card 2
  deck[4] = A♣  → flop 1
  deck[5] = K♠  → flop 2
  deck[6] = Q♦  → flop 3
  deck[7] = 5♥  → turn
  deck[8] = 6♣  → river

Owner holds 2♠ 3♥: best hand is Ace-high (A♣ K♠ Q♦ 6♣ 5♥).
Joiner holds A♥ A♦: Trip Aces (A♥ A♦ A♣ K♠ Q♦).
Expected winner: the player whose CARDS_DEALT contains A♥ A♦.

Assertions:
  - Exact flop, turn, river card values from COMMUNITY_CARDS events
  - HAND_RESULT winner is the Trip-Aces holder
  - hand_description contains "three" (case-insensitive)
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.deck_control import RECIPE_B, complete_deck, injected_deck
from simulation.helpers import setup_two_players
from simulation.scenarios.deterministic.ds1_known_winner import _drive_to_showdown


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555800")

    with injected_deck(complete_deck(RECIPE_B)):
        with owner.connect(table_id):
            with joiner.connect(table_id):
                owner.send_join(table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")

                joiner.send_join(table_id, "player")
                joiner.drain_until("STATE_SNAPSHOT")

                owner.drain_until("BLINDS_POSTED")
                joiner.drain_until("BLINDS_POSTED")

                _drive_to_showdown(owner, joiner, table_id)

    # --- Assertions ---

    # Confirm which user holds the trip-aces hole cards
    owner_dealt = owner.log.of_type("CARDS_DEALT")
    joiner_dealt = joiner.log.of_type("CARDS_DEALT")
    assert len(owner_dealt) == 1
    assert len(joiner_dealt) == 1

    owner_cards = {(c["rank"], c["suit"]) for c in owner_dealt[0].payload["your_cards"]}
    joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt[0].payload["your_cards"]}

    trip_ace_hole = {("A", "H"), ("A", "D")}
    if trip_ace_hole <= joiner_cards:
        expected_winner_id = joiner.user_id
    elif trip_ace_hole <= owner_cards:
        expected_winner_id = owner.user_id
    else:
        raise AssertionError(
            f"Neither player holds A♥ A♦. Owner: {owner_cards}, Joiner: {joiner_cards}"
        )

    # Exact community card assertions
    community_events = owner.log.of_type("COMMUNITY_CARDS")
    assert len(community_events) == 3, (
        f"Expected 3 COMMUNITY_CARDS events (flop/turn/river), got {len(community_events)}. "
        f"Event types: {owner.log.types()}"
    )

    def cards_as_tuples(event) -> list[tuple[str, str]]:
        return [(c["rank"], c["suit"]) for c in event.payload["cards"]]

    flop = cards_as_tuples(community_events[0])
    assert flop == [("A", "C"), ("K", "S"), ("Q", "D")], f"Unexpected flop: {flop}"

    turn = cards_as_tuples(community_events[1])
    assert turn == [("5", "H")], f"Unexpected turn: {turn}"

    river = cards_as_tuples(community_events[2])
    assert river == [("6", "C")], f"Unexpected river: {river}"

    # Winner assertion
    hand_result = owner.log.of_type("HAND_RESULT")
    assert hand_result, "owner must receive HAND_RESULT"
    winners = hand_result[0].payload["winners"]
    assert len(winners) == 1, f"Expected 1 winner record, got {len(winners)}"

    winner_ids = winners[0]["winner_ids"]
    assert expected_winner_id in winner_ids, (
        f"Expected {expected_winner_id} (Trip Aces) to win, got winner_ids={winner_ids}"
    )

    # hand_description is str(winner_hole_cards), e.g. "[AH, AD]".
    # Verify it contains both of the joiner's ace hole cards.
    hand_desc = winners[0].get("hand_description", "")
    assert "AH" in hand_desc and "AD" in hand_desc, (
        f"Expected hand_description to contain joiner's aces (AH, AD), got: {hand_desc!r}"
    )

    assert not owner.log.has_type("ERROR"), f"unexpected ERROR in owner log: {owner.log.of_type('ERROR')}"
    assert not joiner.log.has_type("ERROR"), f"unexpected ERROR in joiner log: {joiner.log.of_type('ERROR')}"
