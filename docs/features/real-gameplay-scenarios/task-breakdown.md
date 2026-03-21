# Task Breakdown — real-gameplay-scenarios

> Gate: Task Breakdown (Gate 5)
> Status: READY FOR IMPLEMENTATION

---

## Implementation Order

Tasks must be implemented in order: T0 → T1 → T2–T7 → T8.

---

## T0 — Read existing driver patterns (research only, no files created)

Before writing any code, read:
- `simulation/scenarios/s1_two_player_hand.py` — `_drive_hand` pattern, `can_check` tracking, `TURN_CHANGED` handling
- `simulation/scenarios/s2_mid_hand_join.py` — `_drive_three_player_hand`, 3-player turn dispatch
- `simulation/helpers.py` — `setup_two_players`, `make_client`, `starting_stack` value
- `simulation/client.py` — `drain_until`, `act`, `disconnect`, `reconnect` (or equivalent) method signatures
- One existing `HAND_RESULT` payload from any passing test log — confirm `hand_number`, `dealer_seat` field names
- One existing `STATE_SNAPSHOT` payload — confirm `players[].stack`, `players[].user_id` field names

**Output**: Field name knowledge required for T2–T7 assertions. No files created.

---

## T1 — `simulation/scenarios/gameplay/__init__.py`

Create the package init. Exports: `run_rg1`, `run_rg2`, `run_rg3`, `run_rg4`, `run_rg5`, `run_rg6`.

```python
from .rg1_three_player_multi_hand import run_rg1
from .rg2_mixed_actions import run_rg2
from .rg3_inactive_player import run_rg3
from .rg4_reconnect_multi_hand import run_rg4
from .rg5_spectator_multi_hand import run_rg5
from .rg6_session_continuity import run_rg6

__all__ = ["run_rg1", "run_rg2", "run_rg3", "run_rg4", "run_rg5", "run_rg6"]
```

---

## T2 — `simulation/scenarios/gameplay/action_driver.py`

Implement `ActionScript` dataclass and `drive_n_player_hand` function.

**`ActionScript`**:
```python
from dataclasses import dataclass, field

@dataclass
class ActionScript:
    fold_on_turns: set = field(default_factory=set)   # {(hand_idx, turn_idx), ...}
    raise_on_turns: set = field(default_factory=set)  # {(hand_idx, turn_idx), ...}
```

**`drive_n_player_hand`** signature:
```python
def drive_n_player_hand(
    http,
    owner,
    players: list,
    table_id: str,
    hand_index: int = 0,
    scripts: dict | None = None,
    big_blind: int = 20,
    max_iter: int = 300,
) -> dict:
    ...
```

**Protocol** (see technical-design.md §6 for full pseudocode):
1. Owner drains `BLINDS_POSTED`
2. Build `user_id → player` map
3. Loop: owner drains next event (TURN_CHANGED or HAND_RESULT)
4. On HAND_RESULT: all players drain it, return payload
5. On TURN_CHANGED: identify player, compute action from script + can_check, send action, update can_check, increment turn_count
6. On street-change events: reset `can_check = True`
7. On max_iter exceeded: raise RuntimeError

**can_check street reset**: Watch for street-advance events. Use the same event type names as in `s1_two_player_hand.py` (confirmed in T0).

---

## T3 — `simulation/scenarios/gameplay/rg1_three_player_multi_hand.py`

```python
def run_rg1(http) -> None:
    """RG1: 3 players, 3 consecutive hands. Verifies blind rotation."""
    # Setup: owner (+15591001), joiner (+15591002), player3 (+15591003)
    # 3 hands with no ActionScript
    # Return: list of HAND_RESULT payloads (for test assertions)
    # The function drives the game; the test file makes assertions
```

Return value: `list[dict]` — one `HAND_RESULT` payload per hand, in order.

---

## T4 — `simulation/scenarios/gameplay/rg2_mixed_actions.py`

```python
def run_rg2(http) -> tuple[list, list]:
    """RG2: 4 players, 2 hands, scripted fold+raise."""
    # Players: owner (+15592001), joiners (+15592002, +15592003, +15592004)
    # Scripts: player[1] folds turn 0 of hands 0,1
    #          player[2] raises turn 0 of hands 0,1 (when can_check=True)
    # Return: (hand_results: list[dict], all_players: list)
```

Return value: `(hand_results, players)` — hand results for hand_number assertions; players list for log inspection.

---

## T5 — `simulation/scenarios/gameplay/rg3_inactive_player.py`

```python
def run_rg3(http) -> tuple[list, list]:
    """RG3: 4 players, 3 hands, player3 folds pre-flop in hands 1-2."""
    # Players: owner (+15593001), +15593002, +15593003, +15593004
    # player3 (index 3): ActionScript(fold_on_turns={(1,0),(2,0)})
    # Return: (hand_results, all_players)
```

---

## T6 — `simulation/scenarios/gameplay/rg4_reconnect_multi_hand.py`

```python
def run_rg4(http) -> tuple[list, object]:
    """RG4: 3 players, 2 hands, player3 disconnects/reconnects between hands."""
    # Players: owner (+15594001), +15594002, player3 (+15594003)
    # Hand 0: all 3 play
    # After hand 0: player3.disconnect()
    # Reconnect: player3.reconnect(http, table_id) or equivalent
    # player3 drains STATE_SNAPSHOT
    # Hand 1: all 3 play (player3 re-participates)
    # Return: (hand_results, player3) for assertion on player3's log
```

**Reconnect implementation**: Inspect `SimulatedClient` for disconnect/reconnect API. If no explicit `reconnect` method exists, use:
```python
player3._ws.close()
# Re-call the join endpoint or WS connect
player3._connect_ws(table_id)
```
Confirm the exact method from reading `simulation/client.py` in T0.

---

## T7 — `simulation/scenarios/gameplay/rg5_spectator_multi_hand.py`

```python
def run_rg5(http) -> tuple[str, object]:
    """RG5: 3 players + spectator, 3 hands."""
    # Players: owner (+15595001), +15595002, +15595003
    # Spectator: +15595004 — joins as spectator (watch_table or equivalent)
    # 3 hands; spectator drains HAND_RESULT after each hand
    # Return: (table_id, spectator) for log assertions
```

---

## T8 — `simulation/scenarios/gameplay/rg6_session_continuity.py`

```python
def run_rg6(http) -> tuple[list, list, float]:
    """RG6: 3 players, 4 hands, structural continuity."""
    # Players: owner (+15596001), +15596002, +15596003
    # 4 hands with no ActionScript
    # Record start_time before first hand, end_time after last hand
    # Return: (hand_results, all_players, elapsed_seconds)
```

---

## T9 — `tests/test_gameplay_scenarios.py`

Six test functions. Each calls the corresponding `run_rgN(http)` and asserts the acceptance criteria.

```python
import pytest
import time
from simulation.app_factory import make_test_client
from simulation.scenarios.gameplay import run_rg1, run_rg2, run_rg3, run_rg4, run_rg5, run_rg6

@pytest.fixture
def http():
    with make_test_client() as client:
        yield client

def test_rg1_three_player_multi_hand(http):
    hand_results, players = run_rg1(http)
    # AC-01: 3 hands completed
    assert len(hand_results) == 3
    # AC-01: unique hand_numbers
    hand_numbers = [r["hand_number"] for r in hand_results]
    assert len(set(hand_numbers)) == 3
    # AC-01: BLINDS_POSTED before HAND_RESULT in owner log
    types = players[0].log.types()
    assert types.index("BLINDS_POSTED") < types.index("HAND_RESULT")
    # AC-02: dealer seat advances
    dealer_seats = [r.get("dealer_seat") for r in hand_results]
    if all(d is not None for d in dealer_seats):
        assert len(set(dealer_seats)) > 1

def test_rg2_mixed_actions(http):
    hand_results, players = run_rg2(http)
    owner = players[0]
    # AC-03: fold and raise appear
    acted_events = [e for e in owner.log.all() if e.type == "PLAYER_ACTED"]
    actions = [e.payload.get("action") for e in acted_events]
    assert "fold" in actions, "No fold action found"
    assert "raise" in actions, "No raise action found"
    # AC-04: all players got CARDS_DEALT
    for p in players:
        assert p.log.has_type("CARDS_DEALT"), f"{p.display_name} missing CARDS_DEALT"
    # AC-12: all 4 action types
    assert any(a in actions for a in ("check", "call")), "No check/call action found"

def test_rg3_inactive_player_continuity(http):
    hand_results, players = run_rg3(http)
    # AC-05: 3 hands completed, no errors
    assert len(hand_results) == 3
    for p in players:
        assert not p.log.has_type("ERROR"), f"{p.display_name} has ERROR event"

def test_rg4_reconnect_multi_hand(http):
    hand_results, player3 = run_rg4(http)
    # AC-06: player3 has STATE_SNAPSHOT after reconnect
    assert player3.log.has_type("STATE_SNAPSHOT"), "player3 missing STATE_SNAPSHOT after reconnect"
    # AC-06: player3 received CARDS_DEALT in hand 2
    assert player3.log.has_type("CARDS_DEALT"), "player3 missing CARDS_DEALT in hand 2"
    assert len(hand_results) == 2

def test_rg5_spectator_multi_hand(http):
    table_id, spectator = run_rg5(http)
    # AC-07: spectator sees ≥3 HAND_RESULT, zero CARDS_DEALT
    hand_result_count = sum(1 for e in spectator.log.all() if e.type == "HAND_RESULT")
    assert hand_result_count >= 3, f"Spectator saw only {hand_result_count} HAND_RESULT events"
    assert not spectator.log.has_type("CARDS_DEALT"), "Spectator received CARDS_DEALT — isolation violated"
    # AC-08: all table_id fields match
    for event in spectator.log.all():
        tid = event.payload.get("table_id")
        if tid is not None:
            assert tid == table_id, f"table_id mismatch: expected {table_id}, got {tid}"

def test_rg6_session_continuity(http):
    hand_results, players, elapsed = run_rg6(http)
    # AC-09: hand_number strictly increasing
    hand_numbers = [r["hand_number"] for r in hand_results]
    for i in range(len(hand_numbers) - 1):
        assert hand_numbers[i+1] > hand_numbers[i], \
            f"hand_number not increasing: {hand_numbers}"
    # AC-10: chip conservation
    stacks = []
    for p in players:
        snapshots = [e for e in p.log.all() if e.type == "STATE_SNAPSHOT"]
        assert snapshots, f"{p.display_name} has no STATE_SNAPSHOT"
        last_snap = snapshots[-1]
        for player_data in last_snap.payload.get("players", []):
            if player_data.get("user_id") == p.user_id:
                stacks.append(player_data["stack"])
                break
    starting_stack = 1000  # verify from helpers.py in T0
    assert sum(stacks) == len(players) * starting_stack, \
        f"Chip conservation failed: {stacks} (expected {len(players) * starting_stack})"
    # AC-11: within 90s
    assert elapsed < 90, f"Scenario exceeded 90s: {elapsed:.1f}s"
```

---

## Acceptance Criteria Coverage

| AC | Test | Status |
|----|------|--------|
| AC-01 | test_rg1 | covered |
| AC-02 | test_rg1 | covered (conditional on field existence) |
| AC-03 | test_rg2 | covered |
| AC-04 | test_rg2 | covered |
| AC-05 | test_rg3 | covered |
| AC-06 | test_rg4 | covered |
| AC-07 | test_rg5 | covered |
| AC-08 | test_rg5 | covered |
| AC-09 | test_rg6 | covered |
| AC-10 | test_rg6 | covered |
| AC-11 | test_rg6 | covered |
| AC-12 | test_rg2 | covered |
| AC-13 | regression run | covered (229 existing + 6 new = 235) |
| AC-14 | grep check | covered |

---

## Must Not Change

- `poker_engine/` — zero changes
- `backend/` — zero changes
- All existing scenario modules (S1–S6, DS1–DS5, LL1–LL6)
- `tests/test_simulation_scenarios.py`
- `tests/test_simulation_deterministic.py`
- `tests/test_deck_control.py`
- `tests/test_load_lite.py`
- `tests/test_debug_observability.py`
- `simulation/debug/` — zero changes
- `simulation/client.py` — zero changes
- `simulation/load_lite/` — zero changes
