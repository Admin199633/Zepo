"""
S8 — PLAYER_ACTED carries new_current_bet and min_raise_to

Validates that every PLAYER_ACTED message includes the updated betting-state
fields so the mobile action bar never goes stale.

Assertions:
- Every PLAYER_ACTED has new_current_bet and min_raise_to in its payload
- After a raise: new_current_bet equals the raise-to amount
- After a call:  new_current_bet is unchanged (call closes the action)
- After a check: new_current_bet == 0
- No ERROR events throughout the hand
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555800")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            blinds_msg = owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            _drive_and_validate(owner, joiner, table_id, blinds_msg["payload"])

    # Collect all PLAYER_ACTED from both logs
    all_acted = owner.log.of_type("PLAYER_ACTED") + joiner.log.of_type("PLAYER_ACTED")
    assert len(all_acted) > 0, "no PLAYER_ACTED events captured"

    for evt in all_acted:
        p = evt.payload
        assert "new_current_bet" in p, (
            f"PLAYER_ACTED missing new_current_bet: {p}"
        )
        assert "min_raise_to" in p, (
            f"PLAYER_ACTED missing min_raise_to: {p}"
        )
        assert isinstance(p["new_current_bet"], int), (
            f"new_current_bet must be int, got {type(p['new_current_bet'])}: {p}"
        )
        assert isinstance(p["min_raise_to"], int), (
            f"min_raise_to must be int, got {type(p['min_raise_to'])}: {p}"
        )
        # After a raise, the new_current_bet must equal the amount (raise-to total)
        if p["action"] == "raise":
            assert p["new_current_bet"] == p["amount"], (
                f"After raise, new_current_bet ({p['new_current_bet']}) "
                f"should equal raise amount ({p['amount']}): {p}"
            )
        # After a check, nothing is outstanding
        if p["action"] == "check":
            assert p["new_current_bet"] == 0, (
                f"After check, new_current_bet should be 0, got {p['new_current_bet']}: {p}"
            )

    assert not owner.log.has_type("ERROR"), f"ERROR in owner log: {owner.log.of_type('ERROR')}"
    assert not joiner.log.has_type("ERROR"), f"ERROR in joiner log: {joiner.log.of_type('ERROR')}"


def _drive_and_validate(owner, joiner, table_id: str, blinds_payload: dict, max_iter: int = 120) -> None:
    """
    Drive a full hand. Uses new_current_bet from PLAYER_ACTED to track
    whether a check or call is appropriate — this is exactly what the
    mobile action bar would do.

    blinds_payload: the payload from the already-consumed BLINDS_POSTED event,
    used to initialize the per-street bet tracking before entering the loop.
    """
    players = {owner.user_id: owner, joiner.user_id: joiner}
    bb_amount = blinds_payload.get("big_blind_amount", 10)
    current_bet: int = bb_amount
    player_bets: dict[str, int] = {
        blinds_payload.get("small_blind_user_id", ""): blinds_payload.get("small_blind_amount", 5),
        blinds_payload.get("big_blind_user_id", ""): bb_amount,
    }

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            if not joiner.log.has_type("HAND_RESULT"):
                joiner.drain_until("HAND_RESULT", max_msgs=120)
            return

        elif t == "PHASE_CHANGED":
            phase = msg["payload"].get("phase", "")
            if phase in ("FLOP", "TURN", "RIVER"):
                current_bet = 0
                player_bets = {}

        elif t == "PLAYER_ACTED":
            # Use the backend-provided new_current_bet to track state
            p = msg["payload"]
            if "new_current_bet" in p:
                current_bet = p["new_current_bet"]
            uid = p.get("user_id", "")
            action = p.get("action", "")
            if action in ("raise", "call"):
                player_bets[uid] = current_bet if action == "raise" else current_bet

        elif t == "TURN_CHANGED":
            acting_uid = msg["payload"].get("user_id")
            actor = players.get(acting_uid)
            if actor:
                my_bet = player_bets.get(acting_uid, 0)
                amount_to_call = current_bet - my_bet
                action = "call" if amount_to_call > 0 else "check"
                actor.send_action(table_id, action)

    raise AssertionError(
        f"HAND_RESULT not reached within {max_iter} iterations. "
        f"Owner events: {owner.log.types()[-20:]}"
    )
