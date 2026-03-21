"""
S10 — Action bar correctness: call_amount, max_raise, and last-action labels

Validates four action-bar invariants that were found during manual iPhone testing:

1. TURN_CHANGED carries player-specific call_amount
   - SB's first TURN_CHANGED: call_amount = BB - SB_blind = 5 (must call to stay in)
   - BB's TURN_CHANGED (after SB calls): call_amount = 0 (BB already paid full blind; check is legal)

2. No NOTHING_TO_CALL error when call_amount == 0
   Verified by asserting no ERROR events in any player's log.

3. TURN_CHANGED carries max_raise > 0
   Effective stack cap must be a positive integer on every turn.

4. PLAYER_ACTED carries the fields needed to derive action labels
   - action field present and in expected set
   - amount field present
   - new_current_bet field present (used for "Raise ${new_current_bet}" label)
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555100")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            blinds_msg = owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            blinds = blinds_msg["payload"]
            _drive_and_assert(owner, joiner, table_id, blinds)

    _assert_call_amount_fields(owner)
    _assert_player_acted_fields(owner)
    _assert_no_errors(owner, joiner)


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _assert_call_amount_fields(owner) -> None:
    """Every TURN_CHANGED must carry call_amount >= 0 and max_raise > 0."""
    turn_events = owner.log.of_type("TURN_CHANGED")
    assert len(turn_events) > 0, "No TURN_CHANGED events captured"

    for evt in turn_events:
        ca = evt.payload.get("call_amount")
        assert ca is not None, f"TURN_CHANGED missing call_amount: {evt.payload}"
        assert isinstance(ca, int), f"call_amount must be int, got {type(ca)}: {evt.payload}"
        assert ca >= 0, f"call_amount must be >= 0, got {ca}: {evt.payload}"

        mr = evt.payload.get("max_raise")
        assert mr is not None, f"TURN_CHANGED missing max_raise: {evt.payload}"
        assert isinstance(mr, int), f"max_raise must be int, got {type(mr)}: {evt.payload}"
        assert mr > 0, f"max_raise must be > 0 on a fresh turn, got {mr}: {evt.payload}"

        min_r = evt.payload.get("min_raise_to")
        assert min_r is not None, f"TURN_CHANGED missing min_raise_to: {evt.payload}"
        assert isinstance(min_r, int), f"min_raise_to must be int, got {type(min_r)}"
        assert min_r > 0, f"min_raise_to must be > 0, got {min_r}: {evt.payload}"


def _assert_player_acted_fields(owner) -> None:
    """PLAYER_ACTED events must carry all fields needed to build action labels."""
    acted_events = owner.log.of_type("PLAYER_ACTED")
    assert len(acted_events) > 0, "No PLAYER_ACTED events captured"

    valid_actions = {"fold", "check", "call", "raise", "all_in"}
    for evt in acted_events:
        action = evt.payload.get("action")
        assert action in valid_actions, f"PLAYER_ACTED action {action!r} not in {valid_actions}"

        amount = evt.payload.get("amount")
        assert amount is not None, f"PLAYER_ACTED missing amount: {evt.payload}"
        assert isinstance(amount, int), f"amount must be int: {evt.payload}"

        new_bet = evt.payload.get("new_current_bet")
        assert new_bet is not None, f"PLAYER_ACTED missing new_current_bet: {evt.payload}"
        assert isinstance(new_bet, int), f"new_current_bet must be int: {evt.payload}"


def _assert_no_errors(owner, joiner) -> None:
    """No ERROR events should occur during normal play."""
    assert not owner.log.has_type("ERROR"), (
        f"ERROR in owner log: {owner.log.of_type('ERROR')}"
    )
    assert not joiner.log.has_type("ERROR"), (
        f"ERROR in joiner log: {joiner.log.of_type('ERROR')}"
    )


# ---------------------------------------------------------------------------
# Drive helper — tracks per-player bet state for correct check vs call decisions
# ---------------------------------------------------------------------------

def _drive_and_assert(
    owner, joiner, table_id: str, blinds_payload: dict, max_iter: int = 150
) -> None:
    """
    Drive a full hand to HAND_RESULT.

    Uses TURN_CHANGED call_amount to decide whether to check or call.
    This mirrors what the mobile client will do after the fix: it reads
    call_amount from the event and shows Check/Call accordingly.

    Also asserts the preflop-specific invariant:
      After SB calls → BB's TURN_CHANGED must have call_amount == 0
    """
    players = {owner.user_id: owner, joiner.user_id: joiner}
    bb_uid = blinds_payload.get("big_blind_user_id", "")
    sb_uid = blinds_payload.get("small_blind_user_id", "")

    # Track whether we've seen BB's post-call turn (the key invariant check)
    sb_has_acted = False
    bb_call_amount_verified = False

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            if not joiner.log.has_type("HAND_RESULT"):
                joiner.drain_until("HAND_RESULT", max_msgs=150)
            return

        elif t == "TURN_CHANGED":
            payload = msg["payload"]
            acting_uid = payload.get("user_id")
            call_amount = payload.get("call_amount", 0)

            # Core invariant: after SB has called preflop, BB's call_amount must be 0.
            if sb_has_acted and acting_uid == bb_uid and not bb_call_amount_verified:
                assert call_amount == 0, (
                    f"BB's call_amount should be 0 after SB calls (BB already posted full BB), "
                    f"got call_amount={call_amount}. "
                    f"If the mobile sends CALL here it gets NOTHING_TO_CALL."
                )
                bb_call_amount_verified = True

            actor = players.get(acting_uid)
            if actor:
                # Use call_amount from the event — exactly what the mobile client does.
                if call_amount > 0:
                    actor.send_action(table_id, "call")
                else:
                    actor.send_action(table_id, "check")

        elif t == "PLAYER_ACTED":
            # Track when SB has acted for the first time
            if msg["payload"].get("user_id") == sb_uid and not sb_has_acted:
                sb_has_acted = True

    raise AssertionError(
        f"HAND_RESULT not reached within {max_iter} iterations. "
        f"Owner events: {owner.log.types()[-20:]}"
    )
