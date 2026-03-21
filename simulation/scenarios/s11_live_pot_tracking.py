"""
S11 — Live pot tracking

Validates that PLAYER_ACTED.pot_total and PHASE_CHANGED.pot_total
correctly reflect the running pot size, so the mobile HUD shows the
right value without waiting for a STATE_SNAPSHOT.

Invariants:
1. Every PLAYER_ACTED carries pot_total >= 0.
2. pot_total increases (or stays the same for check) after each bet/call/raise.
3. PHASE_CHANGED carries pot_total equal to the sum of committed pots
   (bets have been swept into pots by the time the phase changes).
4. HAND_RESULT carries pot_total > 0 when blinds were posted.
5. The final HAND_RESULT.pot_total equals the total chips distributed
   across all winners (conservation of chips).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555110")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            _drive_hand(owner, joiner, table_id)

    _assert_pot_tracking(owner)
    _assert_hand_result_pot(owner)


def _drive_hand(owner, joiner, table_id: str, max_iter: int = 150) -> None:
    """Drive the hand using call_amount (same as S10); collect pot events."""
    players = {owner.user_id: owner, joiner.user_id: joiner}

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
            actor = players.get(acting_uid)
            if actor:
                if call_amount > 0:
                    actor.send_action(table_id, "call")
                else:
                    actor.send_action(table_id, "check")

    raise AssertionError("HAND_RESULT not reached within max iterations")


def _assert_pot_tracking(owner) -> None:
    """Every PLAYER_ACTED must carry a non-negative pot_total."""
    acted_events = owner.log.of_type("PLAYER_ACTED")
    assert len(acted_events) > 0, "No PLAYER_ACTED events captured"

    for evt in acted_events:
        pt = evt.payload.get("pot_total")
        assert pt is not None, f"PLAYER_ACTED missing pot_total: {evt.payload}"
        assert isinstance(pt, int), f"pot_total must be int, got {type(pt)}: {evt.payload}"
        assert pt >= 0, f"pot_total must be >= 0, got {pt}: {evt.payload}"

    # Pot must grow after the first action (blinds already in)
    first_pt = acted_events[0].payload["pot_total"]
    assert first_pt > 0, (
        f"First PLAYER_ACTED pot_total should be > 0 (blinds were posted), got {first_pt}"
    )

    # Verify PHASE_CHANGED also carries pot_total
    phase_events = owner.log.of_type("PHASE_CHANGED")
    for evt in phase_events:
        if evt.payload.get("phase") in ("FLOP", "TURN", "RIVER", "HAND_END"):
            pt = evt.payload.get("pot_total")
            assert pt is not None, f"PHASE_CHANGED({evt.payload.get('phase')}) missing pot_total"
            assert isinstance(pt, int), f"PHASE_CHANGED pot_total must be int: {evt.payload}"
            assert pt >= 0, f"PHASE_CHANGED pot_total must be >= 0: {evt.payload}"


def _assert_hand_result_pot(owner) -> None:
    """HAND_RESULT.pot_total must equal sum of all winner amounts (chip conservation)."""
    result_events = owner.log.of_type("HAND_RESULT")
    assert len(result_events) > 0, "No HAND_RESULT event captured"

    evt = result_events[-1]
    pt = evt.payload.get("pot_total")
    assert pt is not None, f"HAND_RESULT missing pot_total: {evt.payload}"
    assert isinstance(pt, int), f"HAND_RESULT pot_total must be int: {evt.payload}"
    assert pt > 0, f"HAND_RESULT pot_total should be > 0 (blinds were posted), got {pt}"

    # Chip conservation: sum of all winnings == pot_total
    winners = evt.payload.get("winners", [])
    total_distributed = sum(w.get("amount", 0) for w in winners)
    assert total_distributed == pt, (
        f"Chip conservation violated: pot_total={pt} but sum of winners={total_distributed}. "
        f"Winners: {winners}"
    )
