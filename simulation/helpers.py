"""
High-level scenario helpers — composite operations reused across scenarios.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from .client import SimulatedClient


def make_client(http: TestClient, phone: str, name: str) -> SimulatedClient:
    """Create and immediately authenticate a SimulatedClient."""
    return SimulatedClient(http, phone, name).authenticate()


def setup_two_players(
    http: TestClient,
    phone_prefix: str = "+1555000",
) -> tuple[SimulatedClient, SimulatedClient, str, str, str]:
    """
    Create two authenticated clients, a club, and return:
        (owner, joiner, club_id, table_id, invite_code)
    """
    owner = make_client(http, f"{phone_prefix}1001", "Owner")
    joiner = make_client(http, f"{phone_prefix}1002", "Joiner")

    data = owner.create_club("Sim Club")
    club_id = data["club_id"]
    table_id = data["table_id"]
    invite_code = data["invite_code"]

    joiner.join_club(club_id, invite_code)
    return owner, joiner, club_id, table_id, invite_code


def drive_to_hand_result(
    active: SimulatedClient,
    observers: list[SimulatedClient],
    table_id: str,
    max_actions: int = 20,
) -> dict:
    """
    Drive the active player's turn until HAND_RESULT is received.
    On each TURN_CHANGED for the active player, sends a "check" or "call" action.
    Observers drain events passively until they all see HAND_RESULT.

    Returns the HAND_RESULT payload from the active player's log.
    """
    for _ in range(max_actions):
        msg = active.recv_one()
        if msg["type"] == "HAND_RESULT":
            # Drain observers to HAND_RESULT too
            for obs in observers:
                if not obs.log.has_type("HAND_RESULT"):
                    obs.drain_until("HAND_RESULT")
            return msg
        if msg["type"] == "TURN_CHANGED":
            if msg["payload"].get("user_id") == active.user_id:
                active.send_action(table_id, "call")
    raise AssertionError(
        f"HAND_RESULT not reached within {max_actions} actions. "
        f"Last events: {active.log.types()[-10:]}"
    )
