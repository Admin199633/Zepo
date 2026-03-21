# QA Test Plan — simulation-harness

> Agent: Senior QA Reviewer
> Gate: QA Test Plan (Gate 5)
> Status: APPROVED

---

## Scope of QA Review

This plan covers:
1. Correctness of the six required simulation scenarios
2. Event ordering and filtering assertions
3. Reconnect and timeout behavior
4. Failure modes and race condition risks in the harness itself
5. Nondeterminism risks and mitigation
6. Required assertions for confidence

---

## Scenarios

### S1 — Two-Player Hand (Happy Path)

**Steps:**
1. Create two clients (owner, joiner), authenticate both
2. Owner creates club, joiner joins via invite code
3. Both open WS and send `JOIN_TABLE role=player`
4. Both drain to `STATE_SNAPSHOT`
5. Wait for `BLINDS_POSTED` (hand has started)
6. Wait for `TURN_CHANGED` (someone's turn)
7. Acting player sends appropriate action (check or call)
8. Continue until `HAND_RESULT` received by both clients

**Required assertions:**
- Both clients receive `HAND_RESULT`
- `HAND_RESULT.pot_total > 0`
- `STATE_SNAPSHOT.hand_number` increments after hand ends (drain second STATE_SNAPSHOT at top of next hand)
- No `ERROR` events in either client log
- Neither client receives `CARDS_DEALT` for the other player's cards (private delivery verified by absence in log)

**Failure case to test:**
- If only one player joins, no hand should start — verify by waiting 1 s and confirming no `BLINDS_POSTED`

---

### S2 — Mid-Hand Join (Wait for Next Hand)

**Steps:**
1. Setup: two players connected and hand in progress (S1 setup up to `BLINDS_POSTED`)
2. Third client (member) authenticates and joins club
3. Third client opens WS and sends `JOIN_TABLE role=player` mid-hand
4. Third client drains to `STATE_SNAPSHOT`
5. Assert: third client's `STATE_SNAPSHOT` shows `phase != "waiting"` (hand in progress) and their own status is `sitting_out` or `waiting`
6. Wait for `HAND_RESULT` in client 3's log (they observe the hand ending)
7. Wait for `BLINDS_POSTED` for the next hand in client 3's log
8. Client 3 should receive `CARDS_DEALT` in the second hand

**Required assertions:**
- Third client receives `STATE_SNAPSHOT` immediately on join
- Third client is NOT listed as active player in the first hand (`hole_cards` not present for their `user_id`)
- Third client receives `CARDS_DEALT` after the second hand starts
- Third client receives `HAND_RESULT` for the first hand (as observer)

**Failure case:**
- If client 3 sends action during first hand, must receive `ERROR` with `INVALID_ACTION`

---

### S3 — Spectator Event Filtering

**Steps:**
1. Setup: two players, one hand in progress
2. Spectator client joins with `JOIN_TABLE role=spectator`
3. Spectator drains to `STATE_SNAPSHOT`
4. Wait for `HAND_RESULT` in spectator's log
5. Inspect spectator's full event log

**Required assertions:**
- Spectator receives `STATE_SNAPSHOT`
- Spectator receives `BLINDS_POSTED` (broadcast)
- Spectator receives `TURN_CHANGED` (broadcast)
- Spectator receives `PLAYER_ACTED` (broadcast)
- Spectator receives `HAND_RESULT` (broadcast)
- Spectator receives `COMMUNITY_CARDS` (broadcast) — if hand reaches flop
- **Spectator NEVER receives `CARDS_DEALT`** ← critical assertion
- `STATE_SNAPSHOT.hand.hole_cards` — all values must be masked (`rank="?"`, `suit="?"`) for non-self players; spectator sees no one's cards

**QA Risk Note 1:**
`CARDS_DEALT` is a private unicast. The test must drain the spectator's full event log through an entire hand (not just until STATE_SNAPSHOT) to be meaningful. Drain until `HAND_RESULT`.

---

### S4 — Reconnect Within 60 Seconds

**Steps:**
1. Setup: two players, hand in progress
2. Player A disconnects (exit inner WS context manager)
3. Verify: remaining player B receives `PLAYER_STATUS` with `status="disconnected"` and `reserve_until` populated
4. Within 1 s (well within 60 s reserve window), Player A reconnects (new WS context)
5. Player A sends `JOIN_TABLE role=player`
6. Player A drains to `STATE_SNAPSHOT`

**Required assertions:**
- After reconnect, `STATE_SNAPSHOT` is received
- `STATE_SNAPSHOT.players[player_a.user_id].status` is NOT `folded_out` or `eliminated`
- Player B received `PLAYER_STATUS{status=disconnected}` during the gap
- Player B eventually receives `PLAYER_STATUS{status=active}` or `PLAYER_JOINED` after reconnect
- `reserve_until` in the disconnect event is > current time

**QA Risk Note 2:**
The between-hands delay must be overridden to 0.05 s or the hand may end before the reconnect window is demonstrated. Ensure the delay override is applied before any hand starts.

---

### S5 — Full-Table Rejection

**Steps:**
1. Owner creates club and sets `max_players=2` via `PATCH /clubs/{id}/table/config`
2. Two clients join as players (filling the table)
3. A third client (member of club) opens WS and sends `JOIN_TABLE role=player`
4. Third client drains until `ERROR`

**Required assertions:**
- Third client receives `ERROR` event (not HTTP error, WS message)
- `ERROR.payload.code == "TABLE_FULL"`
- WS connection remains open after the error (not closed)
- Third client can still send `JOIN_TABLE role=spectator` successfully afterward

**Alternative (10-player table):**
If patching max_players is preferred: create 10 players all joining, then attempt 11th. Either approach is acceptable; the 2-player version is faster.

---

### S6 — Timeout Auto-Action

**Steps:**
1. Owner patches `turn_timer_seconds=2` via `PATCH /clubs/{id}/table/config` before hand starts
2. Two players join
3. Wait for `TURN_CHANGED` event
4. Active player does NOT send any action
5. Wait up to 5 s (>2 s timer + 1 s grace)
6. Observe `PLAYER_ACTED` event in the non-acting player's log

**Required assertions:**
- `PLAYER_ACTED` is received within 5 s of `TURN_CHANGED`
- `PLAYER_ACTED.payload.action` is `"check"` or `"fold"` (engine auto-action)
- The acting player's WS connection is still open (they are not kicked)
- The game continues (next `TURN_CHANGED` or `HAND_RESULT` follows)

**QA Risk Note 3:**
Turn timer accuracy depends on asyncio task scheduling inside TestClient's background thread. A 2-second timer with a 3-second wait window provides adequate tolerance for CI environments. Do not test with a timer shorter than 2 s.

---

## Edge Cases

| # | Edge Case | Expected Behavior | Assertion |
|---|-----------|------------------|-----------|
| E01 | WS connect with invalid token | Server closes WS (exception on connect) | `pytest.raises(Exception)` |
| E02 | WS connect with valid token but nonexistent table | Server closes WS | `pytest.raises(Exception)` |
| E03 | Send malformed JSON over WS | `ERROR{code=INVALID_MESSAGE}` received; connection stays open | `drain_until("ERROR")` |
| E04 | Duplicate `request_id` on ACTION | Second message silently dropped; only one `PLAYER_ACTED` event | Count `PLAYER_ACTED` events |
| E05 | Unauthenticated HTTP request | HTTP 401 | `assert resp.status_code == 401` |
| E06 | `JOIN_TABLE` sent twice by same player | Second attempt returns `ERROR{code=ALREADY_SEATED}` or is idempotent | Verify no double-join |
| E07 | Spectator sends ACTION | `ERROR{code=INVALID_ACTION}` | `drain_until("ERROR")` |
| E08 | Player joins club with wrong invite code | HTTP 400 `INVALID_INVITE_CODE` | `assert resp.status_code == 400` |
| E09 | Non-club-member tries to join table | `ERROR{code=NOT_MEMBER}` on WS or HTTP 403 | Verify rejection |
| E10 | Two hands run back-to-back | `hand_number` increments each hand | Assert `snapshot2.hand_number == snapshot1.hand_number + 1` |

---

## Nondeterminism Risks

| Risk | Source | Mitigation |
|------|--------|-----------|
| Asyncio scheduling delays between hands | `asyncio.sleep(BETWEEN_HANDS_DELAY)` | Override to 0.05 s |
| Turn timer fires at variable wall-clock time | asyncio task in background thread | Use 2 s timer + 5 s wait window |
| PLAYER_JOINED arrives before or after STATE_SNAPSHOT | Session manager dispatch order | `drain_until` with 30-msg window |
| Non-acting player's log receives broadcast events in variable order | Multiple asyncio tasks dispatching | Assert presence (not position) of events in log |
| Hand may end before a mid-hand join attempt | Race between hand progress and test code | Use `BETWEEN_HANDS_DELAY=0.05` and send JOIN immediately after BLINDS_POSTED to maximize probability of mid-hand window |

---

## Race Condition Risks in Harness

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `drain_until` blocks indefinitely if server error silently drops event | Test hangs | Default `max_msgs=30` terminates drain; fail clearly |
| TestClient background thread exception swallowed | Test passes incorrectly | `raise_server_exceptions=True` in TestClient constructor |
| Module constant patch (`BETWEEN_HANDS_DELAY`) not reset between tests | Test pollution | Reset in pytest fixture teardown; use a dedicated `app_factory.py` that always sets it |
| Nested WS context manager outer exits before inner | Ghost session in registry | Not a harness risk — session_manager `try/finally` handles it |

---

## Assertion Summary (what must be true for QA gate to pass)

| Scenario | Minimum Assertions |
|----------|-------------------|
| S1 | `HAND_RESULT` received by both players; `pot_total > 0`; no ERROR events |
| S2 | Third player gets STATE_SNAPSHOT; not dealt cards in first hand; dealt cards in second hand |
| S3 | Spectator never receives `CARDS_DEALT`; receives all broadcast events |
| S4 | Reconnecting player gets STATE_SNAPSHOT; `reserve_until` populated in disconnect event |
| S5 | 11th player (or over-max player) receives `ERROR{TABLE_FULL}`; WS stays open |
| S6 | `PLAYER_ACTED` received within 5 s of `TURN_CHANGED` without player sending action |

---

## QA Sign-Off Conditions

All six scenarios must pass in CI with:
- `BETWEEN_HANDS_DELAY = 0.05`
- `turn_timer_seconds = 2` (S6 only)
- Total run time under 30 s

Pre-implementation risk flags:
1. **S2 mid-hand window** — test must explicitly wait for `BLINDS_POSTED` before having the third player join; joining before blinds may result in them being seated for the first hand
2. **S3 spectator CARDS_DEALT** — must drain full hand to `HAND_RESULT` before asserting absence; asserting too early gives a false negative
3. **S6 timer granularity** — 2 s timer in asyncio background thread has ~100 ms jitter; 5 s total wait is the minimum safe window
4. **Module constant patching** — `sm.BETWEEN_HANDS_DELAY` must be set before `create_app()` is called in each test; verify ordering in `app_factory.py`
