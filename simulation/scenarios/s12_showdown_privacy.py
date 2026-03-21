"""
S12 — Showdown privacy and winner reveal

Split into two sub-scenarios that each run a single hand:

S12a — Uncontested hand (fold): verifies HAND_RESULT when no showdown occurs.
  - showdown_hands must be empty
  - winners carry 'uncontested' hand_description

S12b — Showdown hand (check to river): verifies HAND_RESULT at showdown.
  - showdown_hands contains only the non-folded players
  - each entry has a valid hand_description category name
  - final_board has 5 cards
  - chip conservation: sum(winners.amount) == pot_total

Privacy invariant: folded players' hole cards must NOT appear in showdown_hands.
With 2 players, a fold means 0 players in showdown_hands; a check-to-river
means 2 players in showdown_hands (neither folded).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players

VALID_HAND_DESCRIPTIONS = {
    "High Card", "One Pair", "Two Pair", "Three of a Kind",
    "Straight", "Flush", "Full House", "Four of a Kind",
    "Straight Flush", "Royal Flush", "uncontested",
}


# ---------------------------------------------------------------------------
# S12a — Uncontested fold: no showdown
# ---------------------------------------------------------------------------

def run_fold(http: TestClient) -> None:
    """Drive one hand where the first actor folds immediately."""
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555120")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")
            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            result_payload = _drive_fold(owner, joiner, table_id)

    _assert_uncontested(result_payload)


def _drive_fold(owner, joiner, table_id: str, max_iter: int = 60) -> dict:
    """First TURN_CHANGED actor folds; returns HAND_RESULT payload."""
    players = {owner.user_id: owner, joiner.user_id: joiner}
    folded = False

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            joiner.drain_until("HAND_RESULT", max_msgs=60)
            return msg["payload"]

        elif t == "TURN_CHANGED":
            acting_uid = msg["payload"].get("user_id")
            actor = players.get(acting_uid)
            if actor and not folded:
                actor.send_action(table_id, "fold")
                folded = True

    raise AssertionError("HAND_RESULT not reached within fold scenario")


def _assert_uncontested(payload: dict) -> None:
    """Uncontested fold: showdown_hands empty, winner has 'uncontested' description."""
    showdown_hands = payload.get("showdown_hands", [])
    assert showdown_hands == [], (
        f"Uncontested fold: showdown_hands must be empty, got {showdown_hands}"
    )

    winners = payload.get("winners", [])
    assert len(winners) > 0, "Must have at least one winner"
    for w in winners:
        assert w.get("amount", 0) > 0, f"Winner amount must be > 0: {w}"
        assert w.get("hand_description") == "uncontested", (
            f"Uncontested hand must have description 'uncontested', got: {w.get('hand_description')!r}"
        )


# ---------------------------------------------------------------------------
# S12b — Showdown hand: both players check to river
# ---------------------------------------------------------------------------

def run_showdown(http: TestClient) -> None:
    """Drive one hand where both players call/check through to showdown."""
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555121")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")
            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            result_payload = _drive_to_showdown(owner, joiner, table_id)

    _assert_showdown(result_payload)


def _drive_to_showdown(owner, joiner, table_id: str, max_iter: int = 150) -> dict:
    """Both players call/check on every street to force showdown. Returns HAND_RESULT payload."""
    players = {owner.user_id: owner, joiner.user_id: joiner}

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            joiner.drain_until("HAND_RESULT", max_msgs=150)
            return msg["payload"]

        elif t == "TURN_CHANGED":
            payload = msg["payload"]
            acting_uid = payload.get("user_id")
            call_amount = payload.get("call_amount", 0)
            actor = players.get(acting_uid)
            if actor:
                if call_amount > 0:
                    actor.send_action(table_id, "call")
                else:
                    actor.send_action(table_id, "check")

    raise AssertionError(
        f"HAND_RESULT not reached within {max_iter} iterations. "
        f"Owner events: {owner.log.types()[-20:]}"
    )


def _assert_showdown(payload: dict) -> None:
    """Showdown: showdown_hands non-empty, valid descriptions, 5-card board."""
    showdown_hands = payload.get("showdown_hands", [])
    assert len(showdown_hands) > 0, "Showdown hand: showdown_hands must be non-empty"

    for sh in showdown_hands:
        uid = sh.get("user_id")
        cards = sh.get("hole_cards", [])
        desc = sh.get("hand_description", "")

        assert uid, f"showdown_hands entry missing user_id: {sh}"
        assert len(cards) == 2, f"showdown_hands entry must have 2 hole cards, got {len(cards)}"
        assert desc in VALID_HAND_DESCRIPTIONS, (
            f"hand_description {desc!r} not in valid set {VALID_HAND_DESCRIPTIONS}"
        )
        assert desc != "uncontested", (
            f"Showdown hand should not have 'uncontested' description: {sh}"
        )

    final_board = payload.get("final_board", [])
    assert len(final_board) == 5, (
        f"Showdown final_board must have 5 cards, got {len(final_board)}"
    )

    winners = payload.get("winners", [])
    assert len(winners) > 0, "Must have at least one winner"
    total_won = sum(w.get("amount", 0) for w in winners)
    pot_total = payload.get("pot_total", 0)
    assert total_won == pot_total, (
        f"Chip conservation: sum of winners ({total_won}) must equal pot_total ({pot_total})"
    )
    for w in winners:
        assert w.get("hand_description", "") in VALID_HAND_DESCRIPTIONS, (
            f"Winner hand_description invalid: {w}"
        )


# ---------------------------------------------------------------------------
# Combined entry point (called by test runner)
# ---------------------------------------------------------------------------

def run(http: TestClient) -> None:
    """Run both sub-scenarios sequentially (each uses a fresh club/table)."""
    run_fold(http)
    run_showdown(http)
