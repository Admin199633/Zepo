# QA Test Plan — backend-application-wiring

> Owner: Senior QA Reviewer
> Input: feature-spec.md, technical-design.md
> Gate: QA Gate (Gate 5)
> Status: Pre-implementation review complete

---

## Architecture Boundary Tests

| ID | Check | Method | Expected |
|----|-------|--------|---------|
| A01 | Engine imports nothing from backend | Static import inspection (`grep -r "from backend" poker_engine/`) | Zero matches |
| A02 | No game logic in session_manager | Code review — no poker rule evaluation outside engine | Confirmed |
| A03 | Deck absent from all snapshots | Test: call `build_spectator_view`, `build_player_view`; assert no `"deck"` key at any nesting level | Confirmed |
| A04 | `SqlitePersistenceAdapter` passes ABC check | `isinstance(SqlitePersistenceAdapter(...), PersistenceAdapter)` | True |
| A05 | Dead import removed | `adapter.py` no longer imports `GameState` | Confirmed |

---

## Test Scenarios

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|----------------|
| T01 | Health check | `GET /health` | `200 {"status":"ok", "state_persistence":"in_memory_volatile", ...}` |
| T02 | OTP request valid phone | `POST /auth/request-otp {"phone_number":"+972501234567"}` | `200 {}` |
| T03 | OTP request invalid phone | `POST /auth/request-otp {"phone_number":"not_a_phone"}` | `400 {"error":"INVALID_PHONE","message":"..."}` |
| T04 | OTP verify correct code | `POST /auth/verify-otp` with matching code | `200 {"token":"...","user_id":"...","expires_at":...}` |
| T05 | OTP verify wrong code | `POST /auth/verify-otp` with wrong code | `400 {"error":"INVALID_OTP","message":"..."}` |
| T06 | OTP consumed on use | Two verify attempts with same code | First: 200. Second: 400. |
| T07 | Create club (authenticated) | `POST /clubs {"name":"Test"}` with valid token | `201 {"club_id","table_id","invite_code"}` |
| T08 | Create club (unauthenticated) | `POST /clubs` without token | `401` |
| T09 | Get club (member) | `GET /clubs/{id}` as member | `200` with club fields |
| T10 | Get club (non-member) | `GET /clubs/{id}` as non-member | `403 NOT_MEMBER` |
| T11 | Join club valid code | `POST /clubs/{id}/join {"invite_code":"..."}` | `200 {"club_id","table_id"}` |
| T12 | Join club invalid code | `POST /clubs/{id}/join {"invite_code":"WRONG"}` | `400 INVALID_INVITE_CODE` |
| T13 | Join club already member | Join same club twice | `409 ALREADY_MEMBER` |
| T14 | Get table (member) | `GET /clubs/{id}/table` | `200` with `config` and `recent_hands` array |
| T15 | Update config as admin | `PATCH /clubs/{id}/table/config` by owner | `200` with updated config |
| T16 | Update config as non-admin | Same request by non-admin | `403 NOT_ADMIN` |
| T17 | WS connect valid token | Open WS with valid token | WS accepted (HTTP 101) |
| T18 | WS connect invalid token | Open WS `?token=garbage` | WS closed with code 4001 |
| T19 | WS connect missing token | Open WS with no token param | WS closed with code 4001 |
| T20 | WS connect nonexistent table | Open WS for unknown table_id | WS closed with code 4004 |
| T21 | JOIN_TABLE as player | Send JOIN_TABLE player | STATE_SNAPSHOT received; PLAYER_JOINED broadcast |
| T22 | JOIN_TABLE as spectator | Send JOIN_TABLE spectator | STATE_SNAPSHOT received; PLAYER_JOINED with seat_index=-1 |
| T23 | Two players → hand starts | Two clients join same table | After ≤4s: PHASE_CHANGED, CARDS_DEALT (per player), BLINDS_POSTED, TURN_CHANGED |
| T24 | ACTION routed correctly | Active player sends call | PLAYER_ACTED broadcast; TURN_CHANGED broadcast |
| T25 | SYNC_REQUEST | Seated player sends SYNC_REQUEST | STATE_SNAPSHOT sent privately to that player only |
| T26 | SIT_OUT | Player sends SIT_OUT | PLAYER_STATUS "sit_out" broadcast |
| T27 | SIT_IN | Sitting-out player sends SIT_IN | PLAYER_STATUS "waiting" broadcast |
| T28 | LEAVE_TABLE | Player sends LEAVE_TABLE | PLAYER_LEFT broadcast; removed from session |
| T29 | CHAT | Player sends CHAT "gg" | CHAT_MESSAGE broadcast to all |
| T30 | WS disconnect | Close WS unexpectedly | PLAYER_STATUS "disconnected" broadcast; `reserve_until` populated |

---

## Edge Cases

| ID | Case | Expected Behavior |
|----|------|------------------|
| E01 | WS handler exits with exception | `finally` block executes: broadcaster.unregister + session_manager.disconnect called |
| E02 | Malformed JSON message | ERROR event `INVALID_MESSAGE` sent; connection stays open |
| E03 | Valid JSON, wrong schema | ERROR event `INVALID_PAYLOAD` sent; connection stays open |
| E04 | ACTION out of turn | ERROR event `INVALID_ACTION` with message; stays open |
| E05 | ACTION with no hand in progress | ERROR event `INVALID_ACTION`; stays open |
| E06 | Duplicate request_id within TTL | Second request silently dropped; no duplicate event emitted |
| E07 | Two WS connects for same user_id | Second connect hits `join_as_player` which detects already-seated → reconnect path |
| E08 | registry.get_or_create concurrent calls | asyncio.Lock ensures exactly one TableSessionManager created |
| E09 | Broadcaster send on stale WS | Exception caught in `_safe_send`; logged; other connections still receive message |
| E10 | Table full — 11th client joins as player | ERROR event `TABLE_FULL`; client can resend JOIN_TABLE as spectator |
| E11 | Player with stack=0 sends SIT_IN | Ignored; player stays SIT_OUT |
| E12 | SIT_OUT/ACTION sent before JOIN_TABLE | ERROR event `NOT_JOINED` (or silently ignored by session_manager) |
| E13 | CHAT empty string | Pydantic validator rejects; ERROR `INVALID_PAYLOAD` |
| E14 | CHAT > 500 chars | Pydantic validator rejects; ERROR `INVALID_PAYLOAD` |
| E15 | Server starts with no .env | Config defaults used; no crash |

---

## Failure Cases

| ID | Failure | Expected Response |
|----|---------|-----------------|
| F01 | OTP requested for unknown phone | 200 (do not reveal whether phone exists) |
| F02 | Token with wrong secret | 401 INVALID_TOKEN |
| F03 | `GET /clubs/{id}` club does not exist | 404 NOT_FOUND |
| F04 | `PATCH /clubs/{id}/table/config` invalid field values | 400 INVALID_CONFIG |
| F05 | Persistence raises unexpected exception in route | 500 `{"error":"INTERNAL_ERROR","message":"..."}` |
| F06 | session_manager raises unexpected exception in WS dispatch | ERROR event sent; connection stays open |
| F07 | `SqlitePersistenceAdapter` method called in dev | `NotImplementedError` raised — must not be wired in dev |

---

## Regression Checklist

- [ ] All `poker_engine/tests/` tests pass — zero changes to engine
- [ ] `tests/test_session_manager.py` passes — session_manager changes are cleanups only
- [ ] `tests/test_persistence.py` passes — no adapter changes except dead import removal
- [ ] `tests/test_realtime_schemas.py` passes — `reserve_until` is Optional; no breaking change
- [ ] Deck key absent from all `STATE_SNAPSHOT` responses (existing test coverage)
- [ ] CARDS_DEALT sent only to owning player (existing test coverage)
- [ ] Spectator STATE_SNAPSHOT has all hole cards masked (existing test coverage)

---

## Security Checks

- [ ] JWT/token validated before WS upgrade completes (close 4001 if invalid)
- [ ] `table_id` existence verified server-side before WS accepted
- [ ] Club membership verified on all club/table HTTP endpoints
- [ ] Admin check on PATCH /table/config uses `club.is_admin(actor_id)` from club model
- [ ] `user_id` taken from token, never from client payload (actions, chat, etc.)
- [ ] Token not logged at INFO level (checked: server access log typically logs URL;
      `?token=` will appear — flag for production hardening)
- [ ] Hole cards not in any broadcast payload (only in private CARDS_DEALT)
- [ ] Spectator broadcaster routes go through `build_spectator_view` path

---

## Realtime and Reconnect Checks

- [ ] `PLAYER_STATUS "disconnected"` broadcast within 1s of WS close
- [ ] `reserve_until` = `time.time() + 60` at disconnect processing time; populated in payload
- [ ] Player reconnects (new WS + JOIN_TABLE before 60s) → STATE_SNAPSHOT received privately
- [ ] Player reconnects after 60s → finds self in SIT_OUT; STATE_SNAPSHOT still delivered
- [ ] Sequence numbers monotonically increase; no gaps in happy path
- [ ] SYNC_REQUEST delivers STATE_SNAPSHOT to requester only (not broadcast)
- [ ] After LEAVE_TABLE, no further events delivered to that user_id over WS
- [ ] Turn timer deadline is an absolute timestamp; correct after reconnect

---

## Integration Test Coverage Requirements

`tests/test_app_integration.py` must contain at minimum:

1. `test_health` — GET /health returns 200 with all fields
2. `test_auth_flow` — request-otp → verify-otp → receive token
3. `test_auth_bad_otp` — verify with wrong code → 400
4. `test_create_club` — POST /clubs → 201 with club_id and table_id
5. `test_join_club` — create then join by invite code
6. `test_ws_invalid_token_rejected` — WS connect with bad token closes 4001
7. `test_ws_missing_token_rejected` — WS connect with no token closes 4001
8. `test_ws_nonexistent_table` — WS connect for unknown table closes 4004
9. `test_ws_join_and_snapshot` — WS connect + JOIN_TABLE → STATE_SNAPSHOT received
10. `test_ws_two_players_hand_start` — two players join → hand events received
11. `test_ws_action_routed` — player sends call → PLAYER_ACTED broadcast
12. `test_ws_disconnect_reserve_until` — WS close → PLAYER_STATUS has reserve_until
13. `test_ws_malformed_json_stays_open` — bad JSON → ERROR event, connection open
14. `test_ws_duplicate_request_id_dropped` — same request_id twice → one event emitted

---

## Pass/Fail Criteria

| Criterion | Pass Condition |
|-----------|---------------|
| Architecture boundary audit | All 5 checks pass |
| All T01–T30 scenarios | Pass with no blockers |
| All E01–E15 edge cases | Confirmed behavior |
| Security checks | All items confirmed |
| Integration tests | All 14 tests pass |
| Regression | Zero failures in existing test suite |
| Deck exposure | Confirmed absent from all responses |

---

## QA Risk Notes to Developer

1. **The `try/finally` in the WS handler is the single most critical correctness item.**
   Test `E01` must explicitly verify this: open a connection, trigger an unhandled
   exception inside the dispatch, verify `disconnect()` was called.

2. **The broadcaster's connection dict must be copied before iterating during broadcast.**
   If a WS closes during broadcast, `unregister` modifies the dict while iteration is
   in progress, causing `RuntimeError: dictionary changed size during iteration`.
   Pattern: `async with self._lock: records = list(...)` then iterate `records` outside lock.

3. **The registry `get_or_create` lock must cover the full check-and-insert.**
   Pattern:
   ```python
   async with self._lock:
       if table_id not in self._sessions:
           self._sessions[table_id] = TableSessionManager(...)
       return self._sessions[table_id]
   ```
   Not:
   ```python
   if table_id not in self._sessions:        # ← task switch can happen here
       async with self._lock:
           self._sessions[table_id] = ...    # ← too late; race already happened
   ```

4. **`reserve_until` must be set at disconnect processing time, not scheduled time.**
   `time.time() + 60` must be computed when `session_manager.disconnect()` is called,
   not when the 60-second asyncio timer fires.
