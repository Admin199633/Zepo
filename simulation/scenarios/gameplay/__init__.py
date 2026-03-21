"""
Realistic gameplay simulation scenarios (RG1–RG6).

Each scenario drives a multi-hand poker session through the live backend
and returns data for test assertions.  No imports from poker_engine or backend.
"""
from .rg1_three_player_multi_hand import run_rg1
from .rg2_mixed_actions import run_rg2
from .rg3_inactive_player import run_rg3
from .rg4_reconnect_multi_hand import run_rg4
from .rg5_spectator_multi_hand import run_rg5
from .rg6_session_continuity import run_rg6

__all__ = ["run_rg1", "run_rg2", "run_rg3", "run_rg4", "run_rg5", "run_rg6"]
