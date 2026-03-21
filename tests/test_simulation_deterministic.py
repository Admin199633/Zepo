"""
Deterministic simulation scenario tests (DS1–DS5).

Each test drives the real backend through a scenario that uses a pre-ordered
deck, allowing exact assertion of winners, community cards, and event payloads.

IMPORTANT: These tests must NOT run with pytest-xdist parallelism (-n > 1).
The deck injection in simulation/deck_control.py is not thread-safe — concurrent
patches to the same module-level attribute will corrupt the function reference.
pytest.ini addopts deliberately omits -n to ensure sequential execution.

Delay override: BETWEEN_HANDS_DELAY = 0.05 s (via make_test_client).
"""
from __future__ import annotations

import pytest

from simulation.app_factory import make_test_client, restore_delays
from simulation.scenarios.deterministic import (
    run_ds1,
    run_ds2,
    run_ds3,
    run_ds4,
    run_ds5,
)


@pytest.fixture
def http():
    """Live TestClient with fast delays and deterministic auth."""
    client = make_test_client(between_hands_delay=0.05)
    yield client
    try:
        client.__exit__(None, None, None)
    except Exception:
        pass
    restore_delays()


# ---------------------------------------------------------------------------
# DS1 — Two-Player Hand with Known Winner
# ---------------------------------------------------------------------------

def test_ds1_known_winner(http):
    run_ds1(http)


# ---------------------------------------------------------------------------
# DS2 — Known Board/Runout with Expected Showdown Result
# ---------------------------------------------------------------------------

def test_ds2_known_board(http):
    run_ds2(http)


# ---------------------------------------------------------------------------
# DS3 — Deterministic Reconnect Snapshot Contents
# ---------------------------------------------------------------------------

def test_ds3_deterministic_reconnect(http):
    run_ds3(http)


# ---------------------------------------------------------------------------
# DS4 — Spectator Filtering Under Deterministic Conditions
# ---------------------------------------------------------------------------

def test_ds4_deterministic_spectator(http):
    run_ds4(http)


# ---------------------------------------------------------------------------
# DS5 — Duplicate Request Idempotency
# ---------------------------------------------------------------------------

def test_ds5_duplicate_request(http):
    run_ds5(http)
