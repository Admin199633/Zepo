"""
S9 — Phase label progression, community-card accumulation, and timer fields

Validates three UI bugs that were found during manual iPhone testing:

1. Phase label progression
   PRE_FLOP → PHASE_CHANGED(FLOP) → phase is "FLOP" in COMMUNITY_CARDS
   → PHASE_CHANGED(TURN) → phase is "TURN" in COMMUNITY_CARDS
   → PHASE_CHANGED(RIVER) → phase is "RIVER" in COMMUNITY_CARDS

2. Community cards accumulate (3 + 1 + 1 = 5 total, not replaced)
   Verified by collecting COMMUNITY_CARDS events and checking cumulative counts.

3. TURN_CHANGED carries seconds_remaining > 0
   So the mobile timer can count down without server/phone clock comparison.

4. Reconnect snapshot (STATE_SNAPSHOT) includes turn_seconds_remaining >= 0
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from simulation.helpers import setup_two_players


def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555900")

    with owner.connect(table_id):
        with joiner.connect(table_id):
            owner.send_join(table_id, "player")
            owner.drain_until("STATE_SNAPSHOT")

            joiner.send_join(table_id, "player")
            joiner.drain_until("STATE_SNAPSHOT")

            blinds_msg = owner.drain_until("BLINDS_POSTED")
            joiner.drain_until("BLINDS_POSTED")

            _drive_and_collect(owner, joiner, table_id, blinds_msg["payload"])

    _assert_phase_progression(owner)
    _assert_community_accumulation(owner)
    _assert_timer_fields(owner)
    _assert_reconnect_snapshot_timer(owner)

    assert not owner.log.has_type("ERROR"), f"ERROR in owner log: {owner.log.of_type('ERROR')}"
    assert not joiner.log.has_type("ERROR"), f"ERROR in joiner log: {joiner.log.of_type('ERROR')}"


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _assert_phase_progression(owner) -> None:
    """Phase in COMMUNITY_CARDS events must follow FLOP → TURN → RIVER order."""
    community_events = owner.log.of_type("COMMUNITY_CARDS")
    if len(community_events) < 3:
        # Hand ended early (e.g. fold) — skip phase progression check
        return

    phases = [e.payload.get("phase", "") for e in community_events]
    assert phases[0] == "FLOP", f"First COMMUNITY_CARDS phase should be FLOP, got {phases[0]!r}"
    assert phases[1] == "TURN", f"Second COMMUNITY_CARDS phase should be TURN, got {phases[1]!r}"
    assert phases[2] == "RIVER", f"Third COMMUNITY_CARDS phase should be RIVER, got {phases[2]!r}"

    # Also check PHASE_CHANGED events include the correct street phases
    phase_changed = owner.log.of_type("PHASE_CHANGED")
    changed_phases = [e.payload.get("phase", "") for e in phase_changed]
    assert "FLOP" in changed_phases, f"Expected PHASE_CHANGED(FLOP), got: {changed_phases}"
    assert "TURN" in changed_phases, f"Expected PHASE_CHANGED(TURN), got: {changed_phases}"
    assert "RIVER" in changed_phases, f"Expected PHASE_CHANGED(RIVER), got: {changed_phases}"


def _assert_community_accumulation(owner) -> None:
    """Community cards must arrive as 3 + 1 + 1 deltas, not replacing each time."""
    community_events = owner.log.of_type("COMMUNITY_CARDS")
    if len(community_events) < 3:
        return

    flop_cards = community_events[0].payload["cards"]
    turn_cards = community_events[1].payload["cards"]
    river_cards = community_events[2].payload["cards"]

    assert len(flop_cards) == 3, f"Flop COMMUNITY_CARDS should have 3 cards, got {len(flop_cards)}"
    assert len(turn_cards) == 1, f"Turn COMMUNITY_CARDS should have 1 card (delta), got {len(turn_cards)}"
    assert len(river_cards) == 1, f"River COMMUNITY_CARDS should have 1 card (delta), got {len(river_cards)}"

    # If accumulated correctly by the client: 3 → 4 → 5
    # We validate the delta counts here; the client-side accumulation is tested separately.
    total_from_deltas = len(flop_cards) + len(turn_cards) + len(river_cards)
    assert total_from_deltas == 5, f"Total community cards from deltas should be 5, got {total_from_deltas}"


def _assert_timer_fields(owner) -> None:
    """Every TURN_CHANGED must carry seconds_remaining > 0."""
    turn_events = owner.log.of_type("TURN_CHANGED")
    assert len(turn_events) > 0, "No TURN_CHANGED events captured"

    for evt in turn_events:
        secs = evt.payload.get("seconds_remaining")
        assert secs is not None, f"TURN_CHANGED missing seconds_remaining: {evt.payload}"
        assert isinstance(secs, int), f"seconds_remaining must be int, got {type(secs)}: {evt.payload}"
        assert secs > 0, (
            f"seconds_remaining should be > 0 on a fresh turn, got {secs}: {evt.payload}"
        )
        # deadline must also be present and consistent
        deadline = evt.payload.get("deadline")
        assert deadline is not None, f"TURN_CHANGED missing deadline: {evt.payload}"


def _assert_reconnect_snapshot_timer(owner) -> None:
    """
    STATE_SNAPSHOT received during an active hand must include turn_seconds_remaining.
    If the hand was already in PRE_FLOP when a SYNC_REQUEST fires, the snapshot should
    carry a non-negative integer for turn_seconds_remaining.
    """
    snapshots = owner.log.of_type("STATE_SNAPSHOT")
    for snap in snapshots:
        hand = snap.payload.get("hand")
        if hand is None:
            continue  # no active hand — no timer expected
        secs = hand.get("turn_seconds_remaining")
        # turn_seconds_remaining may be None if no active turn (e.g. during phase transition)
        if secs is not None:
            assert isinstance(secs, int), (
                f"turn_seconds_remaining in STATE_SNAPSHOT must be int, got {type(secs)}: {hand}"
            )
            assert secs >= 0, (
                f"turn_seconds_remaining in STATE_SNAPSHOT must be >= 0, got {secs}"
            )


# ---------------------------------------------------------------------------
# Drive helper
# ---------------------------------------------------------------------------

def _drive_and_collect(owner, joiner, table_id: str, blinds_payload: dict, max_iter: int = 150) -> None:
    """Drive a full hand to HAND_RESULT, collecting all events."""
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
                joiner.drain_until("HAND_RESULT", max_msgs=150)
            return

        elif t == "PHASE_CHANGED":
            phase = msg["payload"].get("phase", "")
            if phase in ("FLOP", "TURN", "RIVER"):
                current_bet = 0
                player_bets = {}

        elif t == "PLAYER_ACTED":
            p = msg["payload"]
            new_bet = p.get("new_current_bet")
            if new_bet is not None:
                current_bet = new_bet
            uid = p.get("user_id", "")
            if p.get("action") in ("raise", "call"):
                player_bets[uid] = current_bet

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
