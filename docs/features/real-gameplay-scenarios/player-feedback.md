# Player Feedback — real-gameplay-scenarios

> Agent: Poker Player Reviewer
> Gate: Domain Realism Review (Gate 2)
> Status: APPROVED WITH NOTES

---

## Reviewer Profile

Experienced Texas Hold'em player (home games and online). Reviewing this feature spec from the perspective of: does the simulated gameplay match how real poker actually plays out at a home table?

---

## 1. Overall Assessment

The feature spec correctly identifies the gap between "structurally correct" and "believably realistic." The six scenarios cover the right situations. The acceptance criteria are achievable without over-specifying outcomes (which would make tests brittle). My feedback below is mostly confirmations and a few clarifications the engineering team should keep in mind.

---

## 2. Scenario-by-Scenario Review

### RG1 — 3-Player Multi-Hand

**Realistic?** Yes. Three players is the minimum viable home game. Blind rotation every hand is essential — if blinds don't move, the game is broken. The 3-hand minimum is enough to see the button complete one cycle at a 3-player table (button, SB, BB each sit in each seat once).

**Notes for engineering:**
- At a 3-player table: dealer = button = small blind is the standard heads-up rule, but for a full-ring game with 3 players, the button is NOT the small blind — button posts nothing, SB posts small blind, BB posts big blind. Verify the engine uses the correct 3-player blind structure. This is a common source of bugs.
- "Blind rotation verified" (AC-02) is correct. The dealer seat advancing by ≥1 across 3 hands is the right assertion — at 3 players, after 3 hands the button must have visited each position.

**Verdict:** Realistic, spec is correct.

---

### RG2 — 4–6 Player Mixed Actions

**Realistic?** Yes. Four players with scripted fold+raise is exactly how real home games play: someone raises pre-flop, one or two fold, someone calls, post-flop action varies. All 4 action types appearing across 2+ hands is achievable.

**Notes for engineering:**
- The `ActionScript` concept (raise only when `can_check=True`) is correct. You cannot raise when there is already a bet outstanding unless the engine supports a re-raise — which it may. The safest scripted action is to inject the raise on the first post-flop street (flop) if no bet has been placed yet. This guarantees legality.
- A fold at any point (pre-flop, post-flop) is always legal, so the fold injection is safe at any turn.
- AC-03 says "at least one fold and at least one raise" — not per hand, but across ≥2 hands. This is the right bar; demanding it within a single hand could conflict with short-handed scenarios.
- AC-04 ("all 4 players receive CARDS_DEALT in each hand they participate in") is correct. Every active player gets hole cards. If a player folded in hand 1, they are still active for hand 2 (folding within a hand does not remove them from the table).

**Verdict:** Realistic, spec is correct.

---

### RG3 — Inactive Player Continuity

**Realistic?** Yes. The "button refuses to play" (folds every street) is a real home game phenomenon. The game must continue. Three other players completing hand 3 while one player repeatedly folds is the correct behavior.

**Notes for engineering:**
- A player who folds pre-flop is immediately out of that hand's action, so the remaining 3 players play post-flop among themselves. The engine should handle this correctly — verify that a 3-way (not 4-way) showdown or decision tree works when one player folds pre-flop on every hand.
- AC-05 ("no ERROR events") is the right safety check. Repeated folds should never error.
- The "inactive" player still receives CARDS_DEALT at the start of each hand — they just fold immediately. The scenario should not confuse "inactive player" with "disconnected player" (that's RG4). An inactive player is seated and connected but passive.

**Verdict:** Realistic. The distinction between inactive (passive, folding) vs disconnected (RG4) is important — spec handles this correctly.

---

### RG4 — Reconnect in Multi-Hand Session

**Realistic?** Yes. Disconnect-reconnect between hands is a real concern for online poker. The critical window is: player must reconnect before the BETWEEN_HANDS_DELAY expires and hand 2 starts.

**Notes for engineering:**
- AC-06 ("returning player receives STATE_SNAPSHOT") is the right check. A reconnecting player needs to know the current table state — their stack, blind levels, who's the dealer. STATE_SNAPSHOT is the correct mechanism.
- After reconnect, the player should be ACTIVE for hand 2 — not WAITING. They were already seated, just disconnected. Verify the engine handles this: a seated player who disconnects and reconnects should retain their seat and ACTIVE status for the next hand, not be demoted to WAITING.
- The spec correctly notes the race risk (R6): the BETWEEN_HANDS_DELAY window is 0.05 s (patched for tests). Reconnect must happen within that window. The test should reconnect synchronously before hand 2's BLINDS_POSTED arrives.

**Verdict:** Realistic. The BETWEEN_HANDS_DELAY race is a real engineering risk, well-documented.

---

### RG5 — Spectator Over Multi-Hand Session

**Realistic?** Yes. Spectators watching a home game never get dealt cards. They watch all public events (community cards, pot sizes, winner announcements) but never see hole cards.

**Notes for engineering:**
- AC-07 ("≥3 HAND_RESULT events and zero CARDS_DEALT events") is the correct realism check. A spectator should see every hand complete but never receive private cards.
- AC-08 (table_id consistency) catches cross-table event leakage — important for the multi-table load-lite context but also a correctness check for single-table spectating.
- The spectator's event stream should include: BLINDS_POSTED, community cards (COMMUNITY_CARDS / FLOP / TURN / RIVER depending on engine naming), pot updates, PLAYER_ACTED (public actions), HAND_RESULT. Verify the engine broadcasts these to spectators.
- The spec correctly asserts zero CARDS_DEALT — not "zero CARDS_DEALT with real cards." Even an empty CARDS_DEALT would be a protocol violation for a spectator.

**Verdict:** Realistic, spec is correct.

---

### RG6 — Session Continuity Summary

**Realistic?** Yes. This is the meta-correctness check: does the game stay coherent over 4 hands? In a real home game, the chip count is always exactly conserved (no chips appear or disappear), and the hand count increments.

**Notes for engineering:**
- AC-09 (hand_number strictly increasing): This is a fundamental invariant. Any implementation bug where hand_number resets or stalls is a serious correctness failure.
- AC-10 (chip conservation: `sum(stacks) == N × starting_stack`): This is exact. In a no-ante, no-house-edge game, chips are perfectly conserved. The spec correctly notes "no house rules" in R4's mitigation. Verify the test's club is created without antes or rake.
- AC-11 (90s timeout): Four hands with 3 players and 0.05 s delays should complete in well under 10 seconds in practice. The 90 s limit is very generous — this is a CI safety net, not a real constraint.

**Verdict:** Realistic and correct. Chip conservation is a strong signal of engine correctness.

---

## 3. Action Realism Notes

The spec resolves action coverage via `ActionScript` (raise on flop when no bet outstanding; fold at any point). Two observations:

**Check vs Call distinction**: In real poker, `check` is only legal when no bet is outstanding. `call` is legal when there is a bet. The existing `_drive_hand` pattern tracks `can_check` to distinguish these — the new `drive_n_player_hand` must carry this same logic for all N players. If any player sends `check` when they should `call`, the engine should reject it. The scenario should not produce action errors.

**Raise legality**: A raise is legal when it's the player's turn AND the raise amount meets the minimum raise rule. The `ActionScript` should inject raises with a valid amount (e.g., `2 × big_blind` or `pot`). If the engine requires a specific raise format, confirm what `PLAYER_ACT{raise, amount}` payload structure is expected.

**Fold is always safe**: A player can fold on their turn regardless of street or bet state. Fold injection carries zero legality risk.

---

## 4. Blind Structure Verification

At a real poker table:
- **2 players**: Dealer = Small Blind; other player = Big Blind
- **3+ players**: Dealer button is separate; player to dealer's left = Small Blind; player two seats left = Big Blind

The engine must implement the 3+ player structure correctly. AC-02 (dealer seat advances) catches the rotation — but not the absolute seat assignments. If the test needs to verify blind structure, check that `BLINDS_POSTED` payload contains correct player IDs for SB and BB positions relative to the dealer seat.

This is a "should verify" not a blocking concern — the engine already handles 2-player games correctly per the existing tests.

---

## 5. Concerns and Resolutions

| # | Concern | Severity | Resolution |
|---|---------|----------|------------|
| C1 | 3-player blind structure (dealer vs SB) may be incorrect | Medium | Review engine's `_assign_blinds` for 3-player edge case; test verifies rotation not structure |
| C2 | Reconnected player status (ACTIVE vs WAITING) after reconnect | Medium | Covered by RG4 — STATE_SNAPSHOT assertion confirms player is correctly re-admitted |
| C3 | Raise injection with incorrect amount rejected by engine | Low | Use `2 × big_blind` as raise amount — safe minimum |
| C4 | Scripted fold on every hand for inactive player causes bot detection | Not applicable | This is a simulation, not a live game — no bot detection |
| C5 | 4-hand RG6 running slow in CI due to message volume | Low | 90 s timeout is generous; `max_msgs=200+` for multi-hand drains |

---

## 6. Approval

The six scenarios cover real poker realism gaps correctly. The acceptance criteria are structurally sound and non-brittle. The `ActionScript` approach is pragmatic — it achieves action coverage without a full poker AI.

**Approved.** Proceed to technical design.

- Reviewed by: Poker Player Reviewer Agent
- Date: 2026-03-19
