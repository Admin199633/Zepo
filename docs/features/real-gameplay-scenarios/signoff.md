# Sign-off — real-gameplay-scenarios

> Gate: Implementation Gate (Gate 6)
> Status: APPROVED — READY FOR IMPLEMENTATION

---

## Feature Summary

Add `simulation/scenarios/gameplay/` — six realistic Texas Hold'em gameplay simulation scenarios (RG1–RG6) covering 3–6 player multi-hand sessions, scripted action coverage, inactive-player continuity, disconnect/reconnect, spectator isolation over multiple hands, and session-level chip conservation. New `ActionScript` mechanism and `drive_n_player_hand` N-player driver generalise existing two- and three-player hand drivers.

---

## PM Approval

- [x] Feature goal defined: validate believable poker gameplay across multi-hand sessions
- [x] 6 scenarios specified with concrete descriptions
- [x] Scope limited to `simulation/scenarios/gameplay/` + `tests/test_gameplay_scenarios.py`
- [x] Out-of-scope items explicitly listed
- [x] 14 acceptance criteria defined (AC-01 through AC-14)
- [x] 7 design questions resolved
- [x] 6 risks documented with mitigations
- Approved by: Product Manager Agent
- Date: 2026-03-19

---

## Poker Player Reviewer Approval

- [x] 3-player blind structure verified as correct concern (engine must handle dealer ≠ SB for 3+ players)
- [x] Raise legality confirmed: inject only when `can_check=True`, amount = `2 × big_blind`
- [x] Fold legality confirmed: always safe at any turn
- [x] Inactive player (RG3) correctly distinct from disconnected player (RG4)
- [x] Reconnect behavior: player retains ACTIVE status, must receive STATE_SNAPSHOT
- [x] Spectator isolation: zero CARDS_DEALT is the correct hard boundary
- [x] Chip conservation (RG6): exact conservation is correct for no-ante, no-house-edge game
- [x] All 6 scenarios pass realism review
- Approved by: Poker Player Reviewer Agent
- Date: 2026-03-19
- Notes: Raise injection guard (`can_check=True`) is critical — confirm engine rejects illegal raises so the guard prevents test errors, not just CI noise.

---

## Technical Design Approval

- [x] `ActionScript` dataclass designed (fold_on_turns, raise_on_turns as `set[tuple[int,int]]`)
- [x] `drive_n_player_hand` protocol specified (oracle owner, user_id map, can_check state machine, max_iter guard)
- [x] Street-advance `can_check` reset specified
- [x] Phone prefix namespace: `+1559[1-6]xxx` — no overlap with existing
- [x] Return values designed for clean test assertion
- [x] Import boundary explicit: no `poker_engine.*` or `backend.*`
- [x] Reconnect approach specified (disconnect WS, reconnect WS, drain STATE_SNAPSHOT)
- [x] Chip conservation extraction path specified (last STATE_SNAPSHOT payload)
- [x] 6 risks with mitigations documented
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
- Notes: T0 (read existing drivers before implementing) is mandatory — field names for `HAND_RESULT` and `STATE_SNAPSHOT` payloads must be confirmed from running tests before asserting them.

---

## QA Approval

- [x] 6 test functions specified, each mapping to named acceptance criteria
- [x] AC-12 (all 4 action types) implemented within test_rg2 — no extra test needed
- [x] AC-02 (dealer seat advance) implemented with conditional field check
- [x] AC-10 (chip conservation) implementation path specified
- [x] 6 flakiness risks documented with mitigations
- [x] `max_msgs=300` for multi-hand drains specified
- [x] Regression gate: 229 + 6 = 235 expected tests
- [x] Import boundary grep check specified (machine-verifiable)
- [x] Out-of-scope items (specific winners, card values) excluded from all assertions
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19
- Notes: Payload field name verification (T0) is the highest-risk step — assertions for `hand_number`, `dealer_seat`, `players[].stack` must match actual engine output. If field names differ, update the test assertions before calling T0 complete.

---

## What Is Approved for Implementation

**Implement now:**
- T0: Read existing drivers (research — no files)
- T1: `simulation/scenarios/gameplay/__init__.py`
- T2: `simulation/scenarios/gameplay/action_driver.py`
- T3: `simulation/scenarios/gameplay/rg1_three_player_multi_hand.py`
- T4: `simulation/scenarios/gameplay/rg2_mixed_actions.py`
- T5: `simulation/scenarios/gameplay/rg3_inactive_player.py`
- T6: `simulation/scenarios/gameplay/rg4_reconnect_multi_hand.py`
- T7: `simulation/scenarios/gameplay/rg5_spectator_multi_hand.py`
- T8: `simulation/scenarios/gameplay/rg6_session_continuity.py`
- T9: `tests/test_gameplay_scenarios.py`

**Must not change during implementation:**
- `poker_engine/` — zero changes
- `backend/` — zero changes
- `simulation/client.py` — zero changes
- `simulation/debug/` — zero changes
- `simulation/load_lite/` — zero changes
- All existing scenario files (S1–S6, DS1–DS5, LL1–LL6)
- All existing test files

---

## Final Decision

- [x] **APPROVED — ready to implement**
- [x] **ALL GATES CLEARED — proceed with coding**
- [ ] **BLOCKED — do not implement**

Decision by: Product Manager Agent + Poker Player Reviewer Agent + Senior Mobile Game Developer Agent + Senior QA Reviewer Agent
Date: 2026-03-19

**GO — proceed with implementation.**

---

## Implementation Status

**COMPLETE — 2026-03-19**

All 10 tasks implemented. Test results:

- `tests/test_gameplay_scenarios.py` — **6/6 passed** (10.19 s)
- Full regression — **235/235 passed** (100.42 s)
- Import boundary check (AC-14) — **CLEAN** (no `poker_engine.*` or `backend.*` imports in `simulation/scenarios/gameplay/`)

Key implementation notes:
- Driver drains `BLINDS_POSTED` internally and initialises per-player bet state from its payload; callers must NOT drain it first.
- Bet tracking uses `amount_to_call = current_bet - bets_this_round.get(uid, 0)`; `can_check = (amount_to_call <= 0)`. Heuristic `can_check=True after call` is incorrect for N>2 players.
- Raise injection guard (`can_check=True` required) confirmed essential — engine rejects illegal CHECK as `CANNOT_CHECK`.
- `HAND_RESULT` payload has no `hand_number`; AC-09 verified via owner reconnect `STATE_SNAPSHOT`.
- Gameplay fixture uses `between_hands_delay=0.5` (not 0.05) to prevent race with multi-player join.
