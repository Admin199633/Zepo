"""
DS4 — Spectator Filtering Under Deterministic Conditions

Deck (Recipe A — Owner wins with Royal Flush):
  Owner hole: A♠ K♠ | Joiner hole: 2♥ 3♦ | Board: Q♠ J♠ T♠ 2♣ 3♣

A spectator connects after BLINDS_POSTED and observes the full hand.
Winner is known in advance, so we can assert the spectator's HAND_RESULT
winner exactly matches the players' HAND_RESULT winner.

Assertions:
  - Spectator NEVER receives CARDS_DEALT
  - Spectator receives exactly 3 COMMUNITY_CARDS events
  - Spectator community cards match owner's community cards (exact card values)
  - Spectator HAND_RESULT winners == owner HAND_RESULT winners
  - No ERROR events in any log
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.deck_control import RECIPE_A, complete_deck, injected_deck
from simulation.helpers import make_client, setup_two_players
from simulation.scenarios.deterministic.ds1_known_winner import _drive_to_showdown


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, invite_code = setup_two_players(http, "+1556000")

    spectator = make_client(http, "+15560001003", "Spectator")
    spectator.join_club(club_id, invite_code)

    with injected_deck(complete_deck(RECIPE_A)):
        with owner.connect(table_id):
            with joiner.connect(table_id):
                owner.send_join(table_id, "player")
                owner.drain_until("STATE_SNAPSHOT")

                joiner.send_join(table_id, "player")
                joiner.drain_until("STATE_SNAPSHOT")

                owner.drain_until("BLINDS_POSTED")
                joiner.drain_until("BLINDS_POSTED")

                with spectator.connect(table_id):
                    spectator.send_join(table_id, "spectator")
                    spectator.drain_until("STATE_SNAPSHOT")

                    _drive_to_showdown(owner, joiner, table_id)

                    # Spectator drains to HAND_RESULT passively
                    spectator.drain_until("HAND_RESULT", max_msgs=100)

    # --- Assertions ---

    # Critical: spectator must NEVER receive CARDS_DEALT
    assert not spectator.log.has_type("CARDS_DEALT"), (
        f"spectator MUST NOT receive CARDS_DEALT. "
        f"Event types: {spectator.log.types()}"
    )

    # Spectator must receive all 3 community card events
    spec_community = spectator.log.of_type("COMMUNITY_CARDS")
    owner_community = owner.log.of_type("COMMUNITY_CARDS")
    assert len(spec_community) == 3, (
        f"spectator must receive 3 COMMUNITY_CARDS events, got {len(spec_community)}"
    )
    assert len(owner_community) == 3, (
        f"owner must receive 3 COMMUNITY_CARDS events, got {len(owner_community)}"
    )

    # Spectator community cards exactly match owner's
    def cards_as_tuples(event) -> list[tuple[str, str]]:
        return [(c["rank"], c["suit"]) for c in event.payload["cards"]]

    for i in range(3):
        spec_cards = cards_as_tuples(spec_community[i])
        own_cards = cards_as_tuples(owner_community[i])
        assert spec_cards == own_cards, (
            f"COMMUNITY_CARDS[{i}] mismatch: spectator={spec_cards} owner={own_cards}"
        )

    # Spectator HAND_RESULT winners must match owner's exactly
    spec_result = spectator.log.of_type("HAND_RESULT")
    owner_result = owner.log.of_type("HAND_RESULT")
    assert spec_result, "spectator must receive HAND_RESULT"
    assert owner_result, "owner must receive HAND_RESULT"

    assert spec_result[0].payload["winners"] == owner_result[0].payload["winners"], (
        f"spectator HAND_RESULT winners differ from owner's. "
        f"Spectator: {spec_result[0].payload['winners']} "
        f"Owner: {owner_result[0].payload['winners']}"
    )

    assert not spectator.log.has_type("ERROR"), (
        f"unexpected ERROR in spectator log: {spectator.log.of_type('ERROR')}"
    )
    assert not owner.log.has_type("ERROR"), (
        f"unexpected ERROR in owner log: {owner.log.of_type('ERROR')}"
    )
    assert not joiner.log.has_type("ERROR"), (
        f"unexpected ERROR in joiner log: {joiner.log.of_type('ERROR')}"
    )
