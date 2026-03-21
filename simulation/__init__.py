"""
Simulation harness for the Zepo Poker backend.

Drives the real FastAPI application through realistic multi-client scenarios
without a mobile client. Uses synchronous FastAPI TestClient.

Exports:
    SimulatedClient  -- one logical player or spectator
    ScenarioRunner   -- optional multi-scenario orchestrator
"""
from .client import SimulatedClient
from .runner import ScenarioRunner

__all__ = ["SimulatedClient", "ScenarioRunner"]
