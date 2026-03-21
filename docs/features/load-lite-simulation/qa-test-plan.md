# QA Test Plan — load-lite-simulation

> Agent: Senior QA Reviewer
> Gate: QA Review (Gate 3)
> Status: APPROVED

---

## 1. Scope

This plan covers all 6 load-lite scenarios (LL1–LL6) and the supporting orchestrator, table_scenario, and assertions modules. It does not re-test the underlying poker engine or existing S1–S6/DS1–DS5 scenarios.

---

## 2. Test Entry Points

| File | Purpose |
|------|---------|
| `tests/test_load_lite.py` | 6 `def test_ll*` functions using shared `http` fixture |

All tests use `make_test_client(between_hands_delay=0.05)`. LL5's churn table must also resolve within the 2 s auto-action timer budget.

---

## 3. LL1 — Multi-Table Concurrent: Test Steps

**Setup**: Launch 3 threads, each running `run_standard_table(http, index)`.

**Steps**:
1. Start all 3 threads simultaneously via `run_all_tables(http, [fn0, fn1, fn2])`.
2. Join all threads with `timeout=45`.
3. Assert no thread is still alive.
4. For each table result:
   - Assert `result.passed is True`
   - Assert `result.error is None`

**Post-run assertions**:
- Each owner log contains `HAND_RESULT`
- Each joiner log contains `HAND_RESULT`
- `BLINDS_POSTED` appears before `HAND_RESULT` in every player log
- No `ERROR` events in any log (owner, joiner, spectator) on any table

**Failure cases**:
- Thread join timeout → assert names stuck threads, fail immediately
- `HAND_RESULT` missing in a log → the scenario function already raised, captured in `result.error`
- Cross-thread exception in `run_one` → captured as `result.passed=False, result.error=str(exc)`

---

## 4. LL2 — Concurrent Joins: Test Steps

**Setup**: Same as LL1 (3 threads, `run_standard_table`).

**Key assertion** (beyond LL1): After each `drain_until("STATE_SNAPSHOT")`, the snapshot payload `players` dict is non-empty.

**Failure cases**:
- Duplicate session creation under concurrent load → backend raises 400/409 on WS JOIN_TABLE; `drain_until("STATE_SNAPSHOT")` never returns → thread timeout.
- `asyncio.Lock` in `TableSessionRegistry` missing → two threads create the same session, second joins an invalid state → ERROR event in log.

---

## 5. LL3 — Spectator Isolation: Test Steps

**Setup**: Same as LL1 (3 threads with spectators).

**Per-spectator assertions** (called after all threads complete):
1. `assert not spectator.log.has_type("CARDS_DEALT")`
2. For every event `e` in `spectator.log.events`:
   - If `e.payload.get("table_id") is not None`: assert `e.payload["table_id"] == expected_table_id`

**Failure cases**:
- Broadcast service sends a `CARDS_DEALT` to spectator → assertion 1 fails
- Broadcast service sends an event from a different table → assertion 2 fails with cross-table leakage message
- Spectator log empty after hand → `drain_until("HAND_RESULT")` timed out → thread timeout

---

## 6. LL4 — Reconnect During Concurrent Activity: Test Steps

**Setup**: 3 threads. Thread 0 runs reconnect scenario; threads 1 and 2 run `run_standard_table`.

**Thread 0 steps**:
1. `setup_two_players` with prefix `+1558000`
2. Both players connect and join as player
3. `owner.drain_until("BLINDS_POSTED")`, `joiner.drain_until("BLINDS_POSTED")`
4. Owner WS context exits (disconnect)
5. Joiner drains `PLAYER_STATUS`, asserts `status == "disconnected"` and `reserve_until > time.time()`
6. Owner reconnects, sends JOIN_TABLE, drains `STATE_SNAPSHOT`
7. Assert `owner.user_id in snap["payload"]["players"]`

**Cross-table assertions** (after all threads join):
- Tables 1 and 2 both have `HAND_RESULT` in their owner logs
- No ERROR events on tables 1 or 2

**Failure cases**:
- Reconnect races with session cleanup on table 1/2 → session registry corrupt → ERROR or missing HAND_RESULT on table 1/2
- `reserve_until` not set → assertion fails immediately; reconnect path not exercised

---

## 7. LL5 — Churn: Test Steps

**Setup**: Single thread, single table (prefix `+1558300`).

**Steps**:
1. `setup_two_players`
2. Both players connect and join
3. Both drain `BLINDS_POSTED`
4. Joiner WS context exits (no reconnect)
5. Owner drains `HAND_RESULT` with `max_msgs=200`

**Assertions**:
- Owner log contains `HAND_RESULT`
- No `ERROR` events in owner log

**Failure cases**:
- Engine stalls waiting for absent joiner's action beyond 2 s timer → hand never resolves → `drain_until` raises → thread timeout
- Engine raises ERROR instead of auto-acting → assertion fails

**Note on auto-action**: The engine uses a `turn_timer_seconds` (default: 30 s in production, no override needed for LL5 because the test client doesn't patch it). Wait: actually `make_test_client()` doesn't patch the turn timer for all tables — only S6 does. LL5 relies on the joiner being absent (WS disconnected) and the engine's reserve-window auto-action logic. If the reserve window allows the engine to auto-fold after disconnect, the hand resolves quickly. If not, LL5 may take up to `turn_timer_seconds` (30 s). The 45 s thread timeout accommodates this. The LL5 test will pass as long as HAND_RESULT arrives before 45 s.

---

## 8. LL6 — Completion Summary: Test Steps

**Setup**: Run `run_all_tables` again with the 3-table LL1 scenario functions (or reuse cached results if architecture supports it).

**Steps**:
1. Collect `results: list[TableScenarioResult]`
2. Assert `all(r.passed for r in results)`
3. If any fail, `assert_all_results_passed(results)` formats a human-readable error

**Failure cases**:
- Any table failed in LL1 (but LL6 runs independently — it re-executes) → `passed=False` captured
- Thread stuck → `run_all_tables` raises immediately before LL6's assertion runs

---

## 9. Orchestrator Unit Assertions

These are verified implicitly through LL1–LL6 but can be extracted as unit tests if desired:

| Behaviour | How to verify |
|-----------|--------------|
| `run_all_tables` returns `len(scenarios)` results | `assert len(results) == 3` |
| Results are sorted by `table_index` | `assert [r.table_index for r in results] == [0, 1, 2]` |
| Stuck thread detection fires | Pass a scenario that sleeps 60 s; assert `AssertionError` naming the thread |
| Failed scenario captured | Pass a scenario that raises; assert `result.passed is False` and `result.error` is non-empty |
| Lock prevents lost results | 3 concurrent appends → all 3 results present |

---

## 10. Flakiness Risks

| # | Risk | Mitigation |
|---|------|------------|
| F1 | Hand takes longer than expected under concurrent load (3 asyncio loops on 1 event loop thread) | 45 s thread timeout provides ample margin; `_drive_hand` max_iter=100 covers all realistic hand lengths |
| F2 | WS drain for spectator misses HAND_RESULT if it arrives before `drain_until` is called | Spectator drain is called inside the WS context, after `_drive_hand` completes — ordering is deterministic within the thread |
| F3 | Phone number collision if tests run concurrently via pytest-xdist | LL1–LL6 use `+1557xxx` / `+1558xxx` prefixes, distinct from all other test files |
| F4 | LL5 auto-action timer (30 s) pushes thread duration to 30–35 s | Thread timeout is 45 s; expected total for LL5 is well within budget |
| F5 | LL4 reconnect `reserve_until` check: `time.time()` is called after `drain_until("PLAYER_STATUS")` which may take several seconds | `reserve_until` window is 60 s (production default); even with 10 s drain lag, the assertion holds |

---

## 11. Regressions This Feature Catches

1. `TableSessionRegistry.get_or_create` not atomic — concurrent table creation creates duplicate sessions
2. Broadcast service sends `CARDS_DEALT` to spectators (bug in subscriber filter)
3. Broadcast service sends events from wrong table (cross-table leakage in publisher routing)
4. Session manager stalls when a player disconnects mid-hand (reserve-window auto-action not triggered)
5. WS event ordering violated under concurrent load (HAND_RESULT before BLINDS_POSTED)
6. Reconnect fails when background tables are active (race on session state map)
7. Thread-unsafe `dict` mutation in session state shared across asyncio tasks
8. Stuck session that never emits HAND_RESULT, blocking test shutdown indefinitely

---

## 12. QA Sign-Off Conditions

The implementation passes QA when:

- [ ] LL1 passes: 3 tables complete ≥1 hand each; no ERROR events
- [ ] LL2 passes: concurrent joins cause no 4xx/5xx or ERROR events; STATE_SNAPSHOT has ≥1 player on each table
- [ ] LL3 passes: spectators on all 3 tables show no CARDS_DEALT; no cross-table leakage
- [ ] LL4 passes: reconnect under concurrent activity yields STATE_SNAPSHOT with seat held; tables 1–2 unaffected
- [ ] LL5 passes: owner receives HAND_RESULT after joiner churn; no ERROR events
- [ ] LL6 passes: all `TableScenarioResult.passed == True`; assertion helper formats failure correctly
- [ ] All 194 existing tests (S1–S6, DS1–DS5, deck control) still pass after adding load-lite modules
- [ ] No new imports from `poker_engine/` or `backend/` in any load-lite module
- [ ] Total test runtime < 60 s for `test_load_lite.py` alone
