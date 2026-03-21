# QA Test Plan — backend-app-bootstrap

> Owner: Senior QA Reviewer
> Input: feature-spec.md, technical-design.md
> Gate: QA Gate (Gate 5)
> Status: Pre-implementation review complete

---

## Test Scenarios

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|----------------|
| T01 | OTP request with valid phone | POST /auth/request-otp `{"phone_number": "+972501234567"}` | 200 `{}`, OTP printed to stdout |
| T02 | OTP verify with correct code | POST /auth/verify-otp with matching code | 200 `{"token": "...", "user_id": "...", "expires_at": ...}` |
| T03 | OTP verify with wrong code | POST /auth/verify-otp with incorrect code | 400 `{"error": "INVALID_OTP", "message": "..."}` |
| T04 | OTP consumed on first use | POST /auth/verify-otp twice with same correct code | First: 200. Second: 400 INVALID_OTP |
| T05 | WS connect with valid token | Open WS /ws/table/{id}?token=<valid> | WS accepted, STATE_SNAPSHOT received within 1s |
| T06 | WS connect with invalid token | Open WS /ws/table/{id}?token=bad | WS closed with code 4001 |
| T07 | WS connect with missing token | Open WS /ws/table/{id} (no token param) | WS closed with code 4001 |
| T08 | WS connect to nonexistent table | Open WS /ws/table/does_not_exist?token=<valid> | WS closed with code 4004 |
| T09 | Join as player | Send JOIN_TABLE `{"role": "player"}` after connect | PLAYER_JOINED broadcast to all; requester gets own PLAYER_JOINED |
| T10 | Join as spectator | Send JOIN_TABLE `{"role": "spectator"}` | PLAYER_JOINED broadcast with `seat_index: -1`; no hand participation |
| T11 | Two players join → hand starts | Two clients join as player on same table | After 3s: PHASE_CHANGED, CARDS_DEALT (private per player), BLINDS_POSTED, TURN_CHANGED |
| T12 | Player sends ACTION | Active player sends `{"action": "call", "amount": 0}` on their turn | PLAYER_ACTED broadcast, TURN_CHANGED broadcast |
| T13 | Player sends action out of turn | Non-active player sends ACTION | ERROR event `NOT_YOUR_TURN`, connection stays open |
| T14 | SYNC_REQUEST | Connected player sends SYNC_REQUEST | STATE_SNAPSHOT sent only to requesting player |
| T15 | SIT_OUT | Seated player sends SIT_OUT | PLAYER_STATUS "sit_out" broadcast, player skipped next hand |
| T16 | SIT_IN | Sitting-out player sends SIT_IN | PLAYER_STATUS "waiting" broadcast; joins next hand |
| T17 | LEAVE_TABLE | Player sends LEAVE_TABLE | PLAYER_LEFT broadcast; player removed from session |
| T18 | CHAT message | Player sends CHAT `{"message": "gg"}` | CHAT_MESSAGE broadcast to all in table |
| T19 | WS disconnect | Close WS without LEAVE_TABLE | PLAYER_STATUS "disconnected" broadcast with `reserve_until` timestamp |
| T20 | Reconnect within 60s | Player reconnects before timer fires | STATE_SNAPSHOT sent; PLAYER_STATUS broadcast with current status |
| T21 | No reconnect after 60s | Player disconnects; 60s passes | PLAYER_STATUS "sit_out" broadcast; seat preserved |
| T22 | Create club | POST /clubs `{"name": "Test Club"}` | 201 with club_id, table_id, invite_code |
| T23 | Join club by invite code | POST /clubs/{id}/join with valid code | 200 with club_id and table_id |
| T24 | Get club table info | GET /clubs/{id}/table | 200 with config and recent_hands array |
| T25 | Update table config as admin | PATCH /clubs/{id}/table/config by admin | 200 with updated config |
| T26 | Update table config as non-admin | PATCH /clubs/{id}/table/config by non-admin | 403 NOT_ADMIN |
| T27 | Health check | GET /health | 200 `{"status": "ok", ...}` with correct active_tables count |
| T28 | Idempotent action (duplicate request_id) | Send ACTION twice with same request_id | Second request silently dropped; no duplicate event |

---

## Edge Cases

| ID | Case | Expected Behavior |
|----|------|------------------|
| E01 | Same user_id connects twice | Second connect treated as reconnect; first WS gracefully replaced |
| E02 | Malformed JSON in WS message | ERROR event `{"code": "INVALID_MESSAGE", "message": "..."}`, connection stays open |
| E03 | Valid JSON but wrong Pydantic schema | ERROR event `{"code": "INVALID_PAYLOAD", "message": "..."}`, connection stays open |
| E04 | Table full (10 players) — 11th joins as player | ERROR event `TABLE_FULL`, player may resend JOIN_TABLE with role "spectator" |
| E05 | Player action on empty `hand` (no hand in progress) | Engine raises ValueError → ERROR event `INVALID_PHASE`, connection stays open |
| E06 | WS token valid on connect but user deleted mid-session | Session continues until next action requires user lookup; document limitation |
| E07 | registry.get_or_create called simultaneously for same table_id | Exactly one TableSessionManager created (asyncio.Lock guard) |
| E08 | Broadcaster.send fails (stale WS handle) | Exception caught, logged; remaining connections receive the message |
| E09 | CHAT message empty string or whitespace | ERROR event `INVALID_PAYLOAD`; not broadcast |
| E10 | CHAT message over 500 chars | ERROR event `INVALID_PAYLOAD`; not broadcast |
| E11 | Player with stack=0 tries SIT_IN | SIT_IN rejected silently; player stays SIT_OUT |
| E12 | Player joins table mid-hand | Seated with status WAITING; receives STATE_SNAPSHOT showing current hand in progress |

---

## Failure Cases

| ID | Failure | Expected Response |
|----|---------|-----------------|
| F01 | Server starts with no .env | Defaults from `backend/config.py` used; no crash |
| F02 | POST /auth/request-otp with malformed phone | 400 `{"error": "INVALID_PHONE", "message": "..."}` |
| F03 | POST /clubs/{id}/join with wrong invite_code | 400 `{"error": "INVALID_INVITE_CODE", "message": "..."}` |
| F04 | GET /clubs/{id} where user is not a member | 403 `{"error": "NOT_MEMBER", "message": "..."}` |
| F05 | Server restart | In-memory state lost; expected. Players see error on reconnect attempt to WS (session gone). Document this clearly. |
| F06 | WS message larger than server limit | FastAPI/Starlette 1MB default; payload rejected before parsing |
| F07 | Two players fold simultaneously (concurrent actions) | asyncio.Lock in session_manager serializes; second action processed after first; second may get INVALID_PHASE |

---

## Regression Checklist

- [ ] `pytest poker_engine/tests/` — all engine tests pass (zero changes to engine)
- [ ] `pytest tests/` — all existing backend tests pass (zero changes to session_manager)
- [ ] `InMemoryPersistenceAdapter` tests pass
- [ ] Deck never appears in any HTTP response body
- [ ] Deck never appears in any WS ServerEnvelope payload
- [ ] Spectator's STATE_SNAPSHOT has all hole cards masked as `?`
- [ ] Player's STATE_SNAPSHOT shows own cards, masks opponents' cards
- [ ] CARDS_DEALT event is sent only to the named player (not broadcast)

---

## Security Checks

- [ ] JWT token validated before WS upgrade is accepted (not after)
- [ ] Token in query param is not logged at INFO level (potential token leak in logs)
- [ ] PATCH /table/config checks `actor_id == club.admin_id` — cannot be bypassed
- [ ] Hidden cards never included in broadcast events (only in private CARDS_DEALT)
- [ ] Spectator STATE_SNAPSHOT uses `build_spectator_view` — confirmed by test
- [ ] Admin_id in STATE_SNAPSHOT is read-only — client cannot change it via any message type
- [ ] No user can send an ACTION on behalf of a different user_id (user_id taken from token, not payload)

---

## Realtime and Reconnect Checks

- [ ] Player disconnects → `PLAYER_STATUS {"status": "disconnected", "reserve_until": <ts>}` broadcast within 1s
- [ ] `reserve_until` = `time.time() + 60` at the moment disconnect is processed
- [ ] Player reconnects before `reserve_until` → `STATE_SNAPSHOT` sent privately, hand continues
- [ ] Player reconnects after `reserve_until` → player is SIT_OUT; `STATE_SNAPSHOT` still sent (shows SIT_OUT state)
- [ ] Sequence numbers on `ServerEnvelope` increment from 1 with no gaps in happy path
- [ ] SYNC_REQUEST sends snapshot only to requesting player (not broadcast)
- [ ] No events are broadcast to a user after they send LEAVE_TABLE
- [ ] After disconnect + reconnect, turn timer deadline is still accurate (deadline is absolute timestamp)

---

## Pass/Fail Criteria

| Criterion | Pass Condition |
|-----------|---------------|
| All T01–T28 scenarios | Pass with no blockers |
| Security checks | All items checked and confirmed |
| Regression | Zero regressions in existing test suite |
| Deck exposure | Zero occurrences of deck data in any response |
| Card privacy | CARDS_DEALT only sent to owning player — confirmed by test |

---

## QA Sign-off

- [ ] All scenarios passed
- [ ] No blocker defects open
- [ ] Regression clean
- Date: (to be filled after implementation)
- Defects logged: (to be filled after implementation)

---

## QA Risk Notes to Developer

1. **The `try/finally` in the WS handler is critical.** If an unhandled exception occurs
   inside the dispatch loop, `disconnect()` must still be called. Missing this creates
   ghost sessions that hold seats forever.

2. **The `asyncio.Lock` in `TableSessionRegistry` must wrap the entire check-and-create
   sequence**, not just the dict assignment. A task switch between the `get()` check and
   the `__setitem__` can create two managers for the same table.

3. **`WebSocketBroadcaster.broadcast_to_table` must copy the connection list before
   iterating.** If a WS closes mid-broadcast, the unregister call modifies the dict
   while iteration is in progress — this causes `RuntimeError: dictionary changed size`.

4. **Token in query param `?token=` is visible in server access logs.** For production,
   consider an initial auth message instead. For MVP with ConsoleAuthService this is
   acceptable, but must be flagged for hardening before real deployment.
