"""
End-to-end simulation scenario tests.

Each test drives the real backend (create_app()) through a realistic
multi-client scenario using SimulatedClient + synchronous TestClient.

Delay overrides:
  - BETWEEN_HANDS_DELAY: 0.05 s (default 3.0 s)
  - turn_timer_seconds: 2 s for timeout scenario (S6 only)

All six tests must pass in under 30 seconds total.
"""
from __future__ import annotations

import pytest

from simulation.app_factory import make_test_client, restore_delays
from simulation.scenarios import (
    s1_two_player_hand,
    s2_mid_hand_join,
    s3_spectator_filtering,
    s4_reconnect,
    s5_full_table_rejection,
    s6_timeout_auto_action,
    s7_disconnect_reserve_expiry,
    s8_player_acted_fields,
    s9_phase_community_timer,
    s10_action_bar_correctness,
    s11_live_pot_tracking,
    s12_showdown_privacy,
)


@pytest.fixture
def http():
    """Live TestClient with fast delays and deterministic auth."""
    client = make_test_client(between_hands_delay=0.05)
    yield client
    # Teardown: close TestClient and restore production delays
    try:
        client.__exit__(None, None, None)
    except Exception:
        pass
    restore_delays()


# ---------------------------------------------------------------------------
# S1 — Two-Player Hand (Happy Path)
# ---------------------------------------------------------------------------

def test_s1_two_player_hand(http):
    s1_two_player_hand.run(http)


# ---------------------------------------------------------------------------
# S2 — Mid-Hand Join
# ---------------------------------------------------------------------------

def test_s2_mid_hand_join(http):
    s2_mid_hand_join.run(http)


# ---------------------------------------------------------------------------
# S3 — Spectator Event Filtering
# ---------------------------------------------------------------------------

def test_s3_spectator_filtering(http):
    s3_spectator_filtering.run(http)


# ---------------------------------------------------------------------------
# S4 — Reconnect Within 60 Seconds
# ---------------------------------------------------------------------------

def test_s4_reconnect(http):
    s4_reconnect.run(http)


# ---------------------------------------------------------------------------
# S5 — Full-Table Rejection
# ---------------------------------------------------------------------------

def test_s5_full_table_rejection(http):
    s5_full_table_rejection.run(http)


# ---------------------------------------------------------------------------
# S6 — Timeout Auto-Action
# ---------------------------------------------------------------------------

def test_s6_timeout_auto_action(http):
    s6_timeout_auto_action.run(http)


# ---------------------------------------------------------------------------
# S7 — Disconnect Reserve Expiry
# ---------------------------------------------------------------------------

def test_s7_disconnect_reserve_expiry(http):
    # The scenario patches manager._disconnect_reserve_seconds = 0.1 internally
    # after the manager instance is created on first WS connect.
    s7_disconnect_reserve_expiry.run(http)


# ---------------------------------------------------------------------------
# S8 — PLAYER_ACTED carries new_current_bet and min_raise_to
# ---------------------------------------------------------------------------

def test_s8_player_acted_fields(http):
    s8_player_acted_fields.run(http)


# ---------------------------------------------------------------------------
# S9 — Phase label progression, community cards accumulation, timer fields
# ---------------------------------------------------------------------------

def test_s9_phase_community_timer(http):
    s9_phase_community_timer.run(http)

# ---------------------------------------------------------------------------
# S10 — Action bar correctness: call_amount, max_raise, last-action labels
# ---------------------------------------------------------------------------

def test_s10_action_bar_correctness(http):
    s10_action_bar_correctness.run(http)


# ---------------------------------------------------------------------------
# S11 — Live pot tracking: PLAYER_ACTED and PHASE_CHANGED carry pot_total
# ---------------------------------------------------------------------------

def test_s11_live_pot_tracking(http):
    s11_live_pot_tracking.run(http)


# ---------------------------------------------------------------------------
# S12 — Showdown privacy: folded players absent; showdown cards + hand ranks correct
# ---------------------------------------------------------------------------

def test_s12_showdown_privacy(http):
    s12_showdown_privacy.run(http)
