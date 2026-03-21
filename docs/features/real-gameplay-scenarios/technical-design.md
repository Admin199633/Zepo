# Technical Design — real-gameplay-scenarios

> Agent: Senior Mobile Game Developer
> Gate: Technical Design (Gate 3)
> Status: APPROVED

---

## 1. Overview

This document describes the implementation design for the six realistic gameplay simulation scenarios (RG1–RG6). The design extends the existing simulation framework without modifying any production code (`poker_engine/`, `backend/`).

---

## 2. Module Structure

```
simulation/scenarios/gameplay/
├── __init__.py               # exports: run_rg1 … run_rg6
├── action_driver.py          # ActionScript, drive_n_player_hand
├── rg1_three_player_multi_hand.py
├── rg2_mixed_actions.py
├── rg3_inactive_player.py
├── rg4_reconnect_multi_hand.py
├── rg5_spectator_multi_hand.py
└── rg6_session_continuity.py

tests/
└── test_gameplay_scenarios.py   # 6 test functions
```

---

## 3. `action_driver.py` — Core Shared Infrastructure

### 3.1 `ActionScript`

A per-player instruction set that controls when a player injects a non-default action (fold or raise) instead of the default (check/call).

```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class ActionScript:
    """
    Per-player scripted action overrides.

    fold_on_turns: set of (hand_index, turn_within_hand) tuples where
        player sends FOLD instead of check/call.
        turn_within_hand is 0-indexed count of TURN_CHANGED events
        received for this player across the current hand.

    raise_on_turns: set of (hand_index, turn_within_hand) tuples where
        player sends RAISE (amount=2*big_blind) instead of check/call.
        Only injected when can_check=True (no outstanding bet).

    hand_index: 0-indexed count of hands completed so far (incremented
        by drive_n_player_hand before each hand).
    """
    fold_on_turns: set = field(default_factory=set)
    raise_on_turns: set = field(default_factory=set)
```

**Design rationale**: Using (hand_index, turn_index) tuples is the simplest deterministic injection mechanism. It does not require knowing the street or the specific cards — it fires based on observable position in the hand driver loop. This avoids needing to parse engine state.

### 3.2 `drive_n_player_hand`

Generalizes the existing `_drive_hand` (2-player) and `_drive_three_player_hand` (3-player) into an N-player driver.

```python
def drive_n_player_hand(
    http,
    owner,
    players: list,        # all players including owner; owner must be first
    table_id: str,
    hand_index: int = 0,
    scripts: dict | None = None,  # {player_index: ActionScript}
    big_blind: int = 20,
    max_iter: int = 300,
) -> dict:
    """
    Drive one complete hand for N players.

    Returns the HAND_RESULT event payload dict.

    Protocol:
    1. owner waits for BLINDS_POSTED (hand start signal)
    2. Loop: owner drains until TURN_CHANGED
    3. Identify which player's turn it is from TURN_CHANGED payload
    4. That player sends action (check/call/fold/raise per ActionScript)
    5. Repeat until owner receives HAND_RESULT
    6. All players drain HAND_RESULT

    can_check tracking:
    - Reset to True at start of each new street (FLOP/TURN/RIVER/PREFLOP)
    - Set to False when any player RAISEs or BETs
    - Set to True when street advances (next TURN_CHANGED after street card event)
    """
```

**Key design decisions**:

1. **Oracle player**: The `owner` (index 0) is the oracle — it drives the loop by draining `TURN_CHANGED` events. Other players act only when their turn is identified.

2. **Turn identification**: `TURN_CHANGED` payload contains the acting player's `user_id` or `phone`. The driver maps this to a player object.

3. **`can_check` state machine**: Initialized `True` per street. Set `False` on raise/bet. This mirrors the existing `_drive_hand` pattern exactly.

4. **`max_iter` guard**: Prevents infinite loops. 300 iterations is generous for a 4-player hand (typical hand has 12–20 TURN_CHANGED events across all streets).

5. **Script injection**: When `scripts[i]` exists and `(hand_index, player_turn_count)` matches a fold/raise entry, inject that action. Otherwise default to `check` (if `can_check`) or `call`.

6. **Return value**: Returns the `HAND_RESULT` event for caller assertion.

### 3.3 Player turn tracking

Each player maintains an independent per-hand turn counter (reset at the start of each hand). This is a simple integer in the driver's local scope, not stored in the player object.

```python
turn_counts = {i: 0 for i in range(len(players))}
```

On each `TURN_CHANGED` identifying player `i`, the driver:
1. Looks up `turn_counts[i]`
2. Checks `scripts[i].fold_on_turns` or `.raise_on_turns` for `(hand_index, turn_counts[i])`
3. Sends the appropriate action
4. Increments `turn_counts[i]`

---

## 4. Scenario Implementations

### 4.1 RG1 — 3-Player Multi-Hand

```python
# rg1_three_player_multi_hand.py
def run_rg1(http) -> None:
    prefix = "+15591"
    owner, joiner = setup_two_players(http, prefix)
    player3 = make_client(http, f"{prefix}003")
    player3.join_table(table_id)

    for hand_idx in range(3):
        result = drive_n_player_hand(
            http, owner, [owner, joiner, player3],
            table_id, hand_index=hand_idx
        )
        # collect hand_result payloads for assertions

    # Assertions: 3 unique hand_numbers, BLINDS_POSTED before each HAND_RESULT,
    # dealer_seat advances
```

**Phone prefix**: `+15591xxx` — owner: `+15591001`, joiner: `+15591002`, player3: `+15591003`.

**Between-hands delay**: `make_test_client()` patches `BETWEEN_HANDS_DELAY = 0.05`. After each `HAND_RESULT`, the next hand auto-starts. The driver's next `drain_until("BLINDS_POSTED")` catches it.

**Dealer seat assertion**: Collect `dealer_seat` from each `HAND_RESULT` payload. Assert that `hand2_dealer != hand1_dealer` OR `hand3_dealer != hand2_dealer` — at least one rotation occurred.

### 4.2 RG2 — 4–6 Player Mixed Actions

```python
# rg2_mixed_actions.py
def run_rg2(http) -> None:
    prefix = "+15592"
    # 4 players: owner + 3 joiners
    scripts = {
        1: ActionScript(fold_on_turns={(0, 0), (1, 0)}),    # player1 folds turn 0 of hand 0,1
        2: ActionScript(raise_on_turns={(0, 0), (1, 0)}),   # player2 raises turn 0 of hand 0,1
    }
    for hand_idx in range(2):
        drive_n_player_hand(..., hand_index=hand_idx, scripts=scripts)
```

**Raise amount**: `2 × big_blind` (default big_blind=20, so raise=40). This is always a legal minimum raise.

**Fold timing**: Fold on turn 0 of each hand means player1 folds pre-flop. After pre-flop fold, player1 is out of that hand but re-enters the next hand automatically.

**Raise timing**: Raise on turn 0 for player2, but only if `can_check=True`. If player2's first turn is post-flop on a checked-to street, the raise is legal. If pre-flop (where BB may have already bet), `can_check=False` and the raise is skipped (falls back to call).

**Assertion**: Scan `owner.log.types()` for at least one `PLAYER_ACTED` with action=fold and one with action=raise.

### 4.3 RG3 — Inactive Player Continuity

```python
# rg3_inactive_player.py
def run_rg3(http) -> None:
    # 4 players; player3 (index 3) folds on every turn in hands 1 and 2
    scripts = {
        3: ActionScript(
            fold_on_turns={(1, 0), (2, 0)}  # fold pre-flop in hands 1 and 2
        )
    }
    for hand_idx in range(3):
        drive_n_player_hand(..., hand_index=hand_idx, scripts=scripts)
```

**Inactive player logic**: Pre-flop fold means player3 is out of that hand immediately. The engine continues with 3 active players for the rest of the hand. The driver must handle `TURN_CHANGED` for only the remaining 3 players in post-flop streets.

**Error assertion**: Scan all player logs for any event of type `ERROR`. None must be present.

### 4.4 RG4 — Reconnect in Multi-Hand Session

```python
# rg4_reconnect_multi_hand.py
def run_rg4(http) -> None:
    # Hand 1: 3 players complete normally
    # After HAND_RESULT for hand 1: player3 disconnects (_ws.close())
    # During BETWEEN_HANDS_DELAY (0.05 s): player3 reconnects (new WS)
    # Hand 2: player3 drains STATE_SNAPSHOT, then participates normally

    drive_n_player_hand(...)  # hand 0

    # Disconnect
    player3.disconnect()

    # Reconnect — must happen before BLINDS_POSTED of hand 2
    player3.reconnect(http, table_id)
    player3.drain_until("STATE_SNAPSHOT")

    drive_n_player_hand(...)  # hand 1 — player3 must participate
```

**Reconnect API**: Use `player3._connect_ws(table_id)` or equivalent re-entry point. The simulation client's `reconnect` must re-establish the WS and receive the initial STATE_SNAPSHOT that the server sends on join.

**Timing**: After hand 0's `HAND_RESULT`, the server starts its `BETWEEN_HANDS_DELAY = 0.05 s` timer. The test reconnects synchronously (no sleep needed — Python code is fast enough). The reconnect call must complete before the delay expires and `BLINDS_POSTED` fires for hand 1.

**Assertion**: `player3.log` must contain `STATE_SNAPSHOT` AND `CARDS_DEALT` for hand 1.

### 4.5 RG5 — Spectator Over Multi-Hand Session

```python
# rg5_spectator_multi_hand.py
def run_rg5(http) -> None:
    # 3 players + 1 spectator
    # Spectator watches all 3 hands without participating

    spectator = make_client(http, "+15595004")
    spectator.watch_table(table_id)  # spectator join, not player join

    for hand_idx in range(3):
        drive_n_player_hand(...)
        spectator.drain_until("HAND_RESULT")  # spectator also drains

    # Assertions
    assert spectator.log.count("HAND_RESULT") >= 3
    assert not spectator.log.has_type("CARDS_DEALT")
```

**Spectator join**: Different from player join — no seat assignment. The spectator's WS receives broadcast events only (community cards, actions, results) but not hole cards.

**Multi-hand drain for spectator**: Spectator must drain events for each hand. Since the spectator is not acting, it doesn't need to send any messages — only drain. The spectator's `drain_until("HAND_RESULT")` after each hand ensures its log is current.

### 4.6 RG6 — Session Continuity Summary

```python
# rg6_session_continuity.py
def run_rg6(http) -> None:
    # 3 players, 4 hands, no scripts (pure structural test)
    hand_results = []
    for hand_idx in range(4):
        result = drive_n_player_hand(..., hand_index=hand_idx)
        hand_results.append(result)

    # Assertions
    hand_numbers = [r["hand_number"] for r in hand_results]
    assert hand_numbers == sorted(set(hand_numbers))  # strictly increasing

    # Chip conservation: fetch final stacks from last STATE_SNAPSHOT
    # total = sum of all player stacks == N * starting_stack
```

**Chip conservation implementation**: After 4 hands, request each player's current stack. Options:
1. Parse the last `STATE_SNAPSHOT` payload from each player's log for their stack value
2. Parse the last `HAND_RESULT` payload which may include updated stacks

The simplest approach: after all hands complete, each player drains any pending events, then extract `stack` from the last `STATE_SNAPSHOT` event in each player's log.

**starting_stack**: Default is 1000 chips (verify from `simulation/helpers.py` or `TableConfig`). Three players × 1000 = 3000 total chips must be conserved.

---

## 5. Phone Prefix Assignment

| Scenario | Prefix | Owner | Joiner | P3 | P4 |
|----------|--------|-------|--------|----|----|
| RG1 | +15591 | +155910**01** | +155910**02** | +155910**03** | — |
| RG2 | +15592 | +155920**01** | +155920**02** | +155920**03** | +155920**04** |
| RG3 | +15593 | +155930**01** | +155930**02** | +155930**03** | +155930**04** |
| RG4 | +15594 | +155940**01** | +155940**02** | +155940**03** | — |
| RG5 | +15595 | +155950**01** | +155950**02** | +155950**03** | +155950**04** (spectator) |
| RG6 | +15596 | +155960**01** | +155960**02** | +155960**03** | — |

No overlap with existing prefixes: `+1555xxx` (S1–S6), `+1556xxx` (DS1–DS5), `+1557xxx`/`+1558xxx` (LL1–LL6).

---

## 6. `drive_n_player_hand` — Detailed Protocol

```
OWNER drains BLINDS_POSTED        ← hand has started
reset can_check = True
reset turn_counts = {0: 0, 1: 0, ..., N-1: 0}

loop (max_iter times):
    OWNER drains next event (TURN_CHANGED or HAND_RESULT)

    if HAND_RESULT:
        all players drain HAND_RESULT
        return HAND_RESULT payload

    if TURN_CHANGED:
        acting_player = identify_player(event.payload.user_id)
        acting_index = players.index(acting_player)

        # Determine action
        action = default_action(can_check)  # "check" or "call"
        amount = None

        script = scripts.get(acting_index)
        if script:
            key = (hand_index, turn_counts[acting_index])
            if key in script.fold_on_turns:
                action = "fold"
            elif key in script.raise_on_turns and can_check:
                action = "raise"
                amount = 2 * big_blind

        # Send action
        acting_player.act(table_id, action, amount)

        # Update can_check
        if action == "raise":
            can_check = False
        elif action == "call":
            can_check = False

        # Increment turn counter
        turn_counts[acting_index] += 1

    if STREET_CHANGE event (FLOP/TURN/RIVER):
        can_check = True  # new street, no bets outstanding

raise RuntimeError(f"max_iter={max_iter} exceeded without HAND_RESULT")
```

**Street change detection**: The owner's drain loop watches for both `TURN_CHANGED` and street-advance events (e.g., `COMMUNITY_CARDS`, `FLOP`, `TURN`, `RIVER` — check exact event type names in the engine). When a street-advance event is received, `can_check` resets to `True`.

---

## 7. Dependencies and Import Boundaries

### Allowed imports in `simulation/scenarios/gameplay/`
- `simulation.helpers` — `setup_two_players`, `make_client`
- `simulation.app_factory` — `make_test_client`
- `simulation.debug` — `stuck_diagnostic` (for RG6 timeout detection)
- Standard library: `time`, `threading`

### Forbidden imports (AC-14)
- `poker_engine.*` — no internal engine imports
- `backend.*` — no backend imports

### Reference-only (not imported)
- `poker_engine.engine.models.PlayerStatus` — understand WAITING/ACTIVE behavior; do not import
- `poker_engine.engine.models.ActionType` — understand action names; use string literals `"fold"`, `"check"`, `"call"`, `"raise"`

---

## 8. Test Structure (`tests/test_gameplay_scenarios.py`)

```python
import pytest
from simulation.app_factory import make_test_client

@pytest.fixture
def http():
    with make_test_client() as client:
        yield client

def test_rg1_three_player_multi_hand(http): ...
def test_rg2_mixed_actions(http): ...
def test_rg3_inactive_player_continuity(http): ...
def test_rg4_reconnect_multi_hand(http): ...
def test_rg5_spectator_multi_hand(http): ...
def test_rg6_session_continuity(http): ...
```

Each test calls `run_rgN(http)` and makes the assertions in the test body (not inside the scenario module). Assertions in the test body keep scenario modules pure — they drive the game; tests verify outcomes.

---

## 9. Risks and Mitigations

| # | Risk | Mitigation |
|---|------|------------|
| R1 | `drive_n_player_hand` misidentifies acting player | Use `user_id` from `TURN_CHANGED` payload; build a `{user_id: player}` lookup map at hand start |
| R2 | Street change event name differs from expected | Read existing scenario code (s1, s2) to confirm exact event type names before implementing |
| R3 | Raise injection on pre-flop raises when `can_check=False` | Script guard: only inject raise when `can_check=True` |
| R4 | RG4 reconnect race: hand 2 starts before reconnect completes | Patch `BETWEEN_HANDS_DELAY=0.05`; reconnect is synchronous; no sleep needed; assert `STATE_SNAPSHOT` before hand 2 driver |
| R5 | Multi-hand drain accumulates 200+ messages causing timeout | Set `max_msgs=300` for all multi-hand `drain_until` calls |
| R6 | Chip conservation fails if starting_stack is not 1000 | Read `starting_stack` from the `STATE_SNAPSHOT` payload; compute expected total dynamically |

---

## 10. Approval

The design is sound. It reuses proven patterns (`can_check` tracking, oracle player, `drain_until` loops) while extending them cleanly to N players. The `ActionScript` mechanism is minimal and correct. Import boundaries are respected. Phone prefix namespace is isolated.

**Approved.** Proceed to QA test plan.

- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
