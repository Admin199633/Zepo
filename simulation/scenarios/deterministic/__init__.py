"""
Deterministic simulation scenarios (DS1–DS5).

Each module exposes a single `run(http: TestClient) -> None` function
compatible with ScenarioRunner.run() and direct pytest invocation.

IMPORTANT: These tests must NOT run in parallel (pytest-xdist -n > 1).
The deck injection mechanism is not thread-safe — concurrent patches to the
same module-level attribute will corrupt the function reference.
"""
from .ds1_known_winner import run as run_ds1
from .ds2_known_board import run as run_ds2
from .ds3_deterministic_reconnect import run as run_ds3
from .ds4_deterministic_spectator import run as run_ds4
from .ds5_duplicate_request import run as run_ds5

__all__ = ["run_ds1", "run_ds2", "run_ds3", "run_ds4", "run_ds5"]
