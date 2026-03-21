"""
S1 — Two-Player Hand (Happy Path)

Two players connect, join, and complete at least one full hand.
Both must receive HAND_RESULT with pot_total > 0.
Neither receives the other player's CARDS_DEALT.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555100")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            # Both join as players
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            # Wait for the hand to start (blinds posted = hand underway)
            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            # Drive hand to completion by calling/checking on every turn
            _drive_hand(owner, joiner, table_id)

    # Final assertions on captured logs
    assert owner.log.has_type("HAND_RESULT"), "owner must receive HAND_RESULT"
    assert joiner.log.has_type("HAND_RESULT"), "joiner must receive HAND_RESULT"

    hand_result = owner.log.of_type("HAND_RESULT")[0]
    assert hand_result.payload["pot_total"] > 0, "pot must be > 0"

    # Neither player should see the other's hole cards via CARDS_DEALT
    owner_dealt = owner.log.of_type("CARDS_DEALT")
    joiner_dealt = joiner.log.of_type("CARDS_DEALT")
    assert len(owner_dealt) >= 1, "owner must receive their own CARDS_DEALT"
    assert len(joiner_dealt) >= 1, "joiner must receive their own CARDS_DEALT"
    # Private unicast: owner only sees their own cards (1 CARDS_DEALT per hand)
    assert len(owner_dealt) == 1, f"owner received {len(owner_dealt)} CARDS_DEALT; expected 1"
    assert len(joiner_dealt) == 1, f"joiner received {len(joiner_dealt)} CARDS_DEALT; expected 1"

    assert not owner.log.has_type("ERROR"), f"unexpected ERROR in owner log: {owner.log.of_type('ERROR')}"
    assert not joiner.log.has_type("ERROR"), f"unexpected ERROR in joiner log: {joiner.log.of_type('ERROR')}"


def _drive_hand(owner, joiner, table_id: str, max_iter: int = 100) -> None:
    """
    Drive both players through a complete hand.

    Reads from owner's event stream as the oracle.
    Tracks whether there is a bet outstanding so the correct action
    (check vs call) is sent on each turn — "call" with nothing to call
    is an engine validation error that would stall the hand.

    Initial state: can_check=False because we enter after BLINDS_POSTED
    has been consumed (BB posted a bet that SB must call first).
    """
    players = {owner.user_id: owner, joiner.user_id: joiner}
    # After BLINDS_POSTED, there is an outstanding bet (BB amount)
    can_check = False

    for _ in range(max_iter):
        msg = owner.recv_one()
        t = msg["type"]

        if t == "HAND_RESULT":
            # Drain joiner to HAND_RESULT as well.
            # Joiner's buffer accumulates all broadcast events from the full hand;
            # use a large window so we don't hit the default 30-message limit.
            if not joiner.log.has_type("HAND_RESULT"):
                joiner.drain_until("HAND_RESULT", max_msgs=100)
            return

        elif t == "BLINDS_POSTED":
            # A new hand started inside the drive loop (shouldn't normally happen, but be safe)
            can_check = False

        elif t == "COMMUNITY_CARDS":
            # New street (flop/turn/river) — betting resets
            can_check = True

        elif t == "PHASE_CHANGED":
            # Only reset can_check on post-flop streets.
            # PRE_FLOP and START_HAND must NOT reset — blinds are still outstanding.
            phase = msg["payload"].get("phase", "")
            if phase in ("FLOP", "TURN", "RIVER"):
                can_check = True

        elif t == "PLAYER_ACTED":
            action = msg["payload"].get("action", "")
            if action == "raise":
                # Raise puts a new bet outstanding; others must call
                can_check = False
            elif action == "call":
                # Caller matched the bet; the remaining player can now check
                can_check = True
            # check / fold: can_check stays unchanged

        elif t == "TURN_CHANGED":
            acting_uid = msg["payload"].get("user_id")
            actor = players.get(acting_uid)
            if actor:
                action = "check" if can_check else "call"
                actor.send_action(table_id, action)

    raise AssertionError(
        f"HAND_RESULT not reached within {max_iter} iterations. "
        f"Owner event types: {owner.log.types()[-20:]}"
    )
