"""
Realistic gameplay simulation scenario tests (RG1–RG6).

Each test drives a multi-hand poker session through the live backend and
asserts structural correctness: event presence/ordering, chip conservation,
hand_number progression.  No specific card values or winners are asserted.
"""
from __future__ import annotations

import pytest

from simulation.app_factory import make_test_client, restore_delays
from simulation.scenarios.gameplay import (
    run_rg1,
    run_rg2,
    run_rg3,
    run_rg4,
    run_rg5,
    run_rg6,
)


@pytest.fixture
def http():
    """
    Live TestClient with deterministic auth.

    Uses between_hands_delay=0.5 s so that all players in multi-player
    scenarios (3–4 players) have time to join the table before the first
    hand auto-starts.  With an in-process TestClient each join takes
    ~5–20 ms, so 500 ms gives ample margin.
    """
    client = make_test_client(between_hands_delay=0.5)
    yield client
    try:
        client.__exit__(None, None, None)
    except Exception:
        pass
    restore_delays()


# ---------------------------------------------------------------------------
# RG1 — 3-Player Multi-Hand
# ---------------------------------------------------------------------------

def test_rg1_three_player_multi_hand(http):
    hand_results, players = run_rg1(http)
    owner = players[0]

    # AC-01: exactly 3 hands completed, each with a different hand_number not applicable
    # (HAND_RESULT payload has no hand_number); assert 3 HAND_RESULT events reached
    assert len(hand_results) == 3, \
        f"Expected 3 hand results, got {len(hand_results)}"

    # AC-01: pot_total > 0 in each hand (real hands with blinds)
    for i, hr in enumerate(hand_results):
        assert hr["pot_total"] > 0, f"Hand {i+1} pot_total is 0"

    # AC-01: BLINDS_POSTED appears before HAND_RESULT in owner log
    types = owner.log.types()
    assert "BLINDS_POSTED" in types, "owner missing BLINDS_POSTED"
    assert "HAND_RESULT" in types, "owner missing HAND_RESULT"
    assert types.index("BLINDS_POSTED") < types.index("HAND_RESULT"), \
        "BLINDS_POSTED must appear before HAND_RESULT"

    # AC-02: all 3 players received CARDS_DEALT (participated in hands)
    for p in players:
        assert p.log.has_type("CARDS_DEALT"), \
            f"{p.display_name} never received CARDS_DEALT"

    # No ERROR events in any player's log
    for p in players:
        assert not p.log.has_type("ERROR"), \
            f"{p.display_name} has ERROR event: {p.log.of_type('ERROR')}"


# ---------------------------------------------------------------------------
# RG2 — 4-Player Mixed Actions
# ---------------------------------------------------------------------------

def test_rg2_mixed_actions(http):
    hand_results, players = run_rg2(http)
    owner = players[0]

    assert len(hand_results) == 2, \
        f"Expected 2 hand results, got {len(hand_results)}"

    # AC-03: fold and raise appear in owner's PLAYER_ACTED events
    acted_events = owner.log.of_type("PLAYER_ACTED")
    actions = [e.payload.get("action") for e in acted_events]
    assert "fold" in actions, \
        f"No fold action found in owner log. Actions seen: {actions}"
    assert "raise" in actions, \
        f"No raise action found in owner log. Actions seen: {actions}"

    # AC-04: all 4 players received CARDS_DEALT (participated in each hand)
    for p in players:
        assert p.log.has_type("CARDS_DEALT"), \
            f"{p.display_name} never received CARDS_DEALT"

    # AC-12: all 4 action types appear in owner's combined log
    assert any(a in actions for a in ("check", "call")), \
        f"No check or call found in owner log. Actions: {actions}"

    # No ERROR events
    for p in players:
        assert not p.log.has_type("ERROR"), \
            f"{p.display_name} has ERROR event: {p.log.of_type('ERROR')}"


# ---------------------------------------------------------------------------
# RG3 — Inactive Player Continuity
# ---------------------------------------------------------------------------

def test_rg3_inactive_player_continuity(http):
    hand_results, players = run_rg3(http)

    # AC-05: all 3 hands completed
    assert len(hand_results) == 3, \
        f"Expected 3 hand results, got {len(hand_results)}"

    for i, hr in enumerate(hand_results):
        assert hr["pot_total"] > 0, f"Hand {i+1} pot_total is 0"

    # AC-05: no ERROR events in any player's log
    for p in players:
        assert not p.log.has_type("ERROR"), \
            f"{p.display_name} has ERROR event: {p.log.of_type('ERROR')}"

    # All players received CARDS_DEALT (inactive player still gets hole cards)
    for p in players:
        assert p.log.has_type("CARDS_DEALT"), \
            f"{p.display_name} never received CARDS_DEALT"


# ---------------------------------------------------------------------------
# RG4 — Reconnect in Multi-Hand Session
# ---------------------------------------------------------------------------

def test_rg4_reconnect_multi_hand(http):
    hand_results, player3 = run_rg4(http)

    assert len(hand_results) == 2, \
        f"Expected 2 hand results, got {len(hand_results)}"

    # AC-06: returning player received STATE_SNAPSHOT after reconnect
    assert player3.log.has_type("STATE_SNAPSHOT"), \
        "player3 must receive STATE_SNAPSHOT after reconnect"

    # AC-06: returning player received CARDS_DEALT in hand 2
    assert player3.log.has_type("CARDS_DEALT"), \
        "player3 must receive CARDS_DEALT in hand 2 (confirming participation)"

    # hand 2 produced a real pot
    assert hand_results[1]["pot_total"] > 0, "Hand 2 pot_total is 0"


# ---------------------------------------------------------------------------
# RG5 — Spectator Over Multi-Hand Session
# ---------------------------------------------------------------------------

def test_rg5_spectator_multi_hand(http):
    table_id, spectator = run_rg5(http)

    # AC-07: spectator saw HAND_RESULT for all 3 hands
    hr_count = len(spectator.log.of_type("HAND_RESULT"))
    assert hr_count >= 3, \
        f"Spectator saw only {hr_count} HAND_RESULT events; expected >= 3"

    # AC-07: spectator never received CARDS_DEALT
    assert not spectator.log.has_type("CARDS_DEALT"), \
        "Spectator received CARDS_DEALT — hole card isolation violated"

    # AC-08: all table_id fields in spectator's log match expected table
    for event in spectator.log.all():
        tid = event.payload.get("table_id")
        if tid is not None:
            assert tid == table_id, \
                f"Spectator received event with wrong table_id: " \
                f"expected={table_id!r} got={tid!r} event_type={event.type!r}"


# ---------------------------------------------------------------------------
# RG6 — Session Continuity Summary
# ---------------------------------------------------------------------------

def test_rg6_session_continuity(http):
    hand_results, players, elapsed, final_stacks = run_rg6(http)

    # AC-09: 4 hands completed; hand_number in STATE_SNAPSHOT == 4
    assert len(hand_results) == 4, \
        f"Expected 4 hand results, got {len(hand_results)}"

    hand_number = final_stacks.pop("__hand_number__", -1)
    assert hand_number == 4, \
        f"Expected hand_number=4 in post-session STATE_SNAPSHOT, got {hand_number}"

    # All 4 hands produced real pots
    for i, hr in enumerate(hand_results):
        assert hr["pot_total"] > 0, f"Hand {i+1} pot_total is 0"

    # AC-10: chip conservation — total chips == N * starting_stack
    assert len(final_stacks) == len(players), \
        f"final_stacks has {len(final_stacks)} entries; expected {len(players)}"

    # Read starting_stack from any player's initial STATE_SNAPSHOT
    initial_snap = players[0].log.of_type("STATE_SNAPSHOT")
    if initial_snap:
        starting_stack = initial_snap[0].payload.get("config", {}).get("starting_stack", 1000)
    else:
        starting_stack = 1000

    total_chips = sum(final_stacks.values())
    expected_total = len(players) * starting_stack
    assert total_chips == expected_total, \
        f"Chip conservation failed: sum={total_chips} expected={expected_total} " \
        f"stacks={final_stacks}"

    # AC-11: session completed within 90 seconds
    assert elapsed < 90, \
        f"Session exceeded 90 s budget: {elapsed:.1f} s"
