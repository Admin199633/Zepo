# Task Breakdown: Deterministic Simulation Scenarios

**Feature ID:** deterministic-simulation-scenarios
**Status:** Ready for Implementation
**Last Updated:** 2026-03-19

---

## Milestones

| Milestone | Description |
|-----------|-------------|
| M0 | Deck control module |
| M1 | Deterministic scenario sub-package |
| M2 | Pytest integration |
| M3 | Patch isolation unit tests |

---

## Tasks

### M0 — Deck Control Module

**T0 — `simulation/deck_control.py`**
- Implement `DeckSpec = list[tuple[str, str]]` type alias
- Implement `_RANK_MAP`, `_SUIT_MAP` lookup tables from enums
- Implement `build_deterministic_deck(cards: DeckSpec) -> list[Card]` with ValueError on invalid input
- Implement `complete_deck(prefix: DeckSpec) -> DeckSpec` padding helper
- Implement `injected_deck(cards: DeckSpec)` context manager (contextlib.contextmanager + try/finally)
- Define `RECIPE_A` and `RECIPE_B` module-level constants (9-card prefixes)
- Dependencies: none

---

### M1 — Deterministic Scenario Sub-Package

**T1 — `simulation/scenarios/deterministic/__init__.py`**
- Export `run_ds1` through `run_ds5`
- Dependencies: T2–T6

**T2 — `simulation/scenarios/deterministic/ds1_known_winner.py`**
- Use `RECIPE_A` (`complete_deck`)
- `_drive_deterministic_hand(owner, joiner, table_id)` — same can_check logic as `_drive_hand` in s1
- Assert hole cards via `CARDS_DEALT`, assert winner via `HAND_RESULT["winners"]`
- Phone prefix: `"+1555700"`
- Dependencies: T0

**T3 — `simulation/scenarios/deterministic/ds2_known_board.py`**
- Use `RECIPE_B` (`complete_deck`)
- Assert exact flop/turn/river cards via `COMMUNITY_CARDS` events
- Assert `hand_description` contains "three" (case-insensitive)
- Phone prefix: `"+1555800"`
- Dependencies: T0

**T4 — `simulation/scenarios/deterministic/ds3_deterministic_reconnect.py`**
- Use `RECIPE_B` (`complete_deck`)
- Drive preflop to completion, then disconnect owner, reconnect
- Assert `STATE_SNAPSHOT.payload["community_cards"]` matches injected flop
- Assert `reserve_until` in PLAYER_STATUS disconnect event
- Phone prefix: `"+1555900"`
- Dependencies: T0

**T5 — `simulation/scenarios/deterministic/ds4_deterministic_spectator.py`**
- Use `RECIPE_A` (`complete_deck`)
- Add spectator after BLINDS_POSTED, drive to showdown
- Assert spectator never receives CARDS_DEALT
- Assert spectator community cards == owner community cards (exact)
- Assert spectator HAND_RESULT winners == owner HAND_RESULT winners
- Phone prefix: `"+1556000"`
- Dependencies: T0

**T6 — `simulation/scenarios/deterministic/ds5_duplicate_request.py`**
- Use `RECIPE_A` (`complete_deck`)
- Drive to first TURN_CHANGED for owner; send ACTION twice with same request_id
- Drive to HAND_RESULT
- Assert PLAYER_ACTED count per turn is not doubled
- Assert hand completes without stalling
- Phone prefix: `"+1556100"`
- Dependencies: T0

---

### M2 — Pytest Integration

**T7 — `tests/test_simulation_deterministic.py`**
- `http` fixture using `make_test_client()` + teardown
- 5 test functions: `test_ds1_known_winner`, `test_ds2_known_board`, `test_ds3_reconnect`, `test_ds4_spectator`, `test_ds5_duplicate`
- Module-level comment: must not run with `pytest-xdist -n > 1`
- Dependencies: T1–T6

---

### M3 — Patch Isolation Unit Tests

**T8 — `tests/test_deck_control.py`**
- `test_patch_applied_inside_context` — deck[0] matches Recipe A
- `test_patch_restored_after_normal_exit` — function object identity restored
- `test_patch_restored_after_exception` — exception inside context does not leak patch
- `test_sequential_invocations` — two sequential contexts each work correctly
- `test_invalid_rank_raises` — ValueError on bad rank
- `test_invalid_suit_raises` — ValueError on bad suit
- `test_complete_deck_no_duplicates` — padded deck has exactly 52 unique cards
- Dependencies: T0

---

## Dependency Graph

```
T0 (deck_control.py)
  ├── T2 (DS1)
  ├── T3 (DS2)
  ├── T4 (DS3)
  ├── T5 (DS4)
  ├── T6 (DS5)
  │     └── T1 (__init__.py)
  │               └── T7 (test_simulation_deterministic.py)
  └── T8 (test_deck_control.py)
```

---

## Must NOT Change During Implementation

- `poker_engine/` — zero file changes
- `backend/` — zero file changes
- `simulation/scenarios/s1_*.py` through `s6_*.py` — no modifications
- `tests/test_simulation_scenarios.py` — no modifications
- `simulation/app_factory.py`, `simulation/client.py`, `simulation/helpers.py` — no modifications

---

## Definition of Done

- [ ] `simulation/deck_control.py` exists with `injected_deck`, `build_deterministic_deck`, `complete_deck`, `RECIPE_A`, `RECIPE_B`
- [ ] `simulation/scenarios/deterministic/__init__.py` exports `run_ds1`–`run_ds5`
- [ ] DS1–DS5 each pass without error or stalling
- [ ] `tests/test_deck_control.py` — all 7 patch isolation tests pass
- [ ] `tests/test_simulation_deterministic.py` — all 5 scenario tests pass
- [ ] `tests/test_simulation_scenarios.py` — all 6 existing tests still pass
- [ ] Full regression: `py -3 -m pytest tests/ poker_engine/tests/ -q` — 180+ passed
