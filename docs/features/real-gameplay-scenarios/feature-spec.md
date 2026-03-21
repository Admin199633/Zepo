# Feature Spec — real-gameplay-scenarios

> Agent: Product Manager
> Gate: Feature Spec (Gate 1)
> Status: APPROVED

---

## 1. Feature Goal

The existing simulation suite (S1–S6, DS1–DS5, LL1–LL6) proves the backend is structurally correct: events arrive, sessions are stable, deck injection works, concurrency is safe. What it does not prove is that the game **behaves like a believable poker session** across time.

A real Hold'em table has:
- 3–6 players (not just 2)
- multiple consecutive hands with rotating blinds and dealer buttons
- players folding, raising, and checking — not just calling on every turn
- chips accumulating and depleting across hands
- players joining mid-session, waiting for the next hand, and then participating
- a spectator who watches a real game, not one synthetic hand

This feature adds **realistic gameplay simulation scenarios**: scenarios that represent how a real-world home game actually plays, at a level of fidelity that gives confidence the game is coherent across a longer session.

---

## 2. What "Real Gameplay" Means for This Project Right Now

| Dimension | Definition |
|-----------|-----------|
| Players | 3 to 6 players at a table simultaneously |
| Hands | 3–5 consecutive hands in a single session (enough to see blinds rotate, chip swings, and fold pressure) |
| Actions | All four action types exercised: fold, check, call, raise |
| Sessions | Players who join mid-session wait correctly and then deal in |
| Continuity | Hand numbers increment, stacks change, blinds rotate — session state is coherent across hands |
| Spectators | A spectator who watches multiple consecutive hands and receives no hole cards from any hand |
| Reconnect | A player who disconnects mid-session and reconnects before the next hand |

---

## 3. Scope

### In scope (M0)

Six scenario modules under `simulation/scenarios/gameplay/`:

| ID | Name | Description |
|----|------|-------------|
| RG1 | 3-player multi-hand | 3 players, 3 consecutive hands, all must reach HAND_RESULT; blind rotation verified |
| RG2 | 4-6 player mixed actions | 4 players, ≥2 hands; scripted fold+raise pressure so all 4 action types appear in logs |
| RG3 | Inactive-player continuity | 4 players; after hand 1, one player folds every turn for hands 2–3; session must continue |
| RG4 | Reconnect in multi-hand session | 3 players; player disconnects after hand 1 concludes, reconnects before hand 2 starts, participates in hand 2 |
| RG5 | Spectator over multi-hand session | 3 players + 1 spectator; spectator observes 3 hands; no CARDS_DEALT in spectator log across all hands |
| RG6 | Session continuity summary | 3 players; asserts hand_number increments, stacks conserved, no stuck hands over 4 consecutive hands |

Supporting utilities:

- `simulation/scenarios/gameplay/__init__.py`
- `simulation/scenarios/gameplay/action_driver.py` — `drive_n_player_hand`, `ActionScript` (scripted fold/raise injection)
- `tests/test_gameplay_scenarios.py` — 6 test functions

### Out of scope

- Tournament structures (blind levels, scheduled breaks, prize pools)
- Public matchmaking or lobby systems
- Player eliminations tracked beyond the current session (persistent leaderboards)
- All-in side pot multi-winner simulations (the engine handles this; we assert `pot_total > 0`)
- Mobile client UI
- Production monitoring or metrics
- Seeded-RNG or replay-exact-hand determinism for multi-hand sessions (single-hand DS1–DS5 already covers this)
- `pytest-xdist` parallelism for gameplay scenarios

---

## 4. Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC-01 | RG1: 3 players complete exactly 3 consecutive hands; each hand has a unique `hand_number`; `BLINDS_POSTED` appears before each `HAND_RESULT` |
| AC-02 | RG1: The dealer seat advances by at least 1 seat across 3 hands (blind rotation is happening) |
| AC-03 | RG2: At least one `PLAYER_ACTED{action=fold}` and at least one `PLAYER_ACTED{action=raise}` appear in the owner's event log across ≥2 hands |
| AC-04 | RG2: All 4 players receive `CARDS_DEALT` in each hand they participate in |
| AC-05 | RG3: After one player's repeated folds, the remaining 3 players still complete hand 3; no `ERROR` events |
| AC-06 | RG4: After reconnect, the returning player receives `STATE_SNAPSHOT`; they participate in hand 2 (their `CARDS_DEALT` is present) |
| AC-07 | RG5: Spectator log contains ≥3 `HAND_RESULT` events and zero `CARDS_DEALT` events across the full session |
| AC-08 | RG5: Every event in the spectator log where `payload.get("table_id")` is set matches the spectator's expected table_id |
| AC-09 | RG6: `hand_number` in each successive `HAND_RESULT` payload is strictly greater than the previous |
| AC-10 | RG6: After 4 hands, total chips across all players equal `N × starting_stack` (chips conserved) |
| AC-11 | RG6: No thread ever exceeds 90 seconds total; stuck-scenario detection active |
| AC-12 | All 4 action types (`fold`, `check`, `call`, `raise`) appear in the combined event log of at least one multi-hand scenario |
| AC-13 | All 229 existing tests continue to pass after this feature is added |
| AC-14 | `simulation/scenarios/gameplay/` has zero imports from `poker_engine/` internals or `backend/` |

---

## 5. Design Questions (Resolved)

| # | Question | Resolution |
|---|----------|------------|
| Q1 | How many players per table? | 3–6; RG1/RG4/RG5/RG6 use 3; RG2 uses 4; RG3 uses 4. Engine supports up to 10. |
| Q2 | How many consecutive hands define a session? | 3 hands minimum (RG1/RG3/RG5); 4 hands for the continuity summary (RG6). Enough to see blind rotation and chip variance without excessive runtime. |
| Q3 | Which scenarios are deterministic vs semi-random? | RG1/RG6: structural only (real shuffle); RG2: scripted raise injection on known phase transitions; RG3: scripted fold driver; RG4/RG5: real shuffle, structural assertions. No hand outcome is asserted — only structural event presence/ordering. |
| Q4 | How to achieve richer action coverage without a fake poker AI? | `ActionScript` in `action_driver.py` — a simple per-player fold/raise scheduler that triggers on specific turn counts or phases, injected into the N-player hand driver. |
| Q5 | How to validate realism without brittle assertions? | Assert event presence and ordering (structural), chip conservation, hand_number monotonicity. Never assert specific card values, specific winners, or specific chip amounts in multi-hand scenarios. |
| Q6 | How to bound longer sessions for CI safety? | 3–4 hands at 0.05 s between-hands delay; `drive_n_player_hand` has a `max_iter` guard; each scenario thread has a 90 s timeout via `stuck_diagnostic`. |
| Q7 | What gaps does this feature close? | No existing test covers: >2 players in a sustained session; fold/raise actions in scenario tests; hand_number progression; chip conservation across hands; spectator over multi-hand; reconnect in a multi-hand context. |

---

## 6. Dependencies

| Dependency | Kind | Status |
|-----------|------|--------|
| `simulation.helpers.setup_two_players`, `make_client` | Existing | Available |
| `simulation.scenarios.s1_two_player_hand._drive_hand` | Existing hand driver (reference) | Available |
| `simulation.scenarios.s2_mid_hand_join._drive_three_player_hand` | Existing 3-player driver (reference) | Available |
| `simulation.debug` | Existing observability package | Available |
| `simulation.app_factory.make_test_client` | Existing | Available |
| `poker_engine.engine.models.PlayerStatus` | Engine model (read-only reference) | Available |
| `threading` (stdlib) | For RG6 stuck detection if needed | Available |

---

## 7. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | Multi-hand sessions accumulate WS messages faster than `drain_until` drains them, causing timeout | Medium | Large `max_msgs` windows (200+) for multi-hand drains; `drive_n_player_hand` reads from oracle player's stream |
| R2 | Scripted raises cause illegal-action errors (raising when not allowed) | Medium | `ActionScript.raise` only injects a raise in post-flop streets when `can_check=True` (no bet outstanding) |
| R3 | Phone prefix collision with existing scenarios | Low | Gameplay scenarios use `+1559xxx` range, distinct from all prior prefixes |
| R4 | Chip conservation assertion fails due to ante/penalty/house rules | Low | Default club creation uses no house rules; chip conservation is exact |
| R5 | 4-player `max_players` constraint | Low | Default `TableConfig.max_players=10`; 4 players is well within range |
| R6 | Reconnect in RG4 races with hand 2 auto-start | Medium | RG4 reconnects during `BETWEEN_HANDS_DELAY` window (0.05 s patched); player must rejoin before `BLINDS_POSTED` of hand 2 |
