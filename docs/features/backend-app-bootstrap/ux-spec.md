# UX Spec — backend-app-bootstrap

> Owner: Senior UI/UX Designer
> Input: feature-spec.md, player-feedback.md
> Gate: UX Gate (Gate 2)
> Status: APPROVED

---

## Scope Note

This feature has no mobile UI screens. The "UX" is the developer and operator experience:
API contract clarity, error surface, connection flow, and system visibility. All decisions
here define what the mobile client layer will need to implement when it consumes this API.

---

## User Flow

### Auth Flow
```
App launch
  → POST /auth/request-otp  { phone_number }
  ← 200 {}                  (OTP sent to console in dev, SMS in prod)
  → POST /auth/verify-otp   { phone_number, code, display_name? }
  ← 200 { token, user_id, expires_at }
  → Store token in secure storage
```

### Club + Table Entry Flow
```
After auth
  → POST /clubs             { name }          (creates club + table automatically)
  ← 201 { club_id, table_id, invite_code }
  OR
  → POST /clubs/{id}/join   { invite_code }
  ← 200 { club_id, table_id }
  → GET  /clubs/{id}/table
  ← 200 { table_id, config, recent_hands[] }
```

### WebSocket Table Flow
```
  → WS connect /ws/table/{table_id}?token=<jwt>
  ← STATE_SNAPSHOT          (sent automatically on connect, before any message)
  → { type: JOIN_TABLE, payload: { role: "player" } }
  ← PLAYER_JOINED           (broadcast to all)
  ← [PLAYER_JOINED for each already-seated player] (sent privately to new joiner)
  → { type: ACTION, payload: { action: "call", amount: 0 } }
  ← PLAYER_ACTED            (broadcast)
  ← TURN_CHANGED            (broadcast)
  → WS close / network drop
  ← PLAYER_STATUS "disconnected" (broadcast, includes reserve_until timestamp)
  → WS reconnect /ws/table/{table_id}?token=<jwt>
  ← STATE_SNAPSHOT          (private, full current state)
```

---

## API Contract Requirements

### HTTP Error Format (all 4xx / 5xx)
Every error response must use this exact shape:
```json
{
  "error": "INVALID_OTP",
  "message": "The code you entered is incorrect or has expired."
}
```
- `error`: machine-readable code in SCREAMING_SNAKE_CASE
- `message`: human-readable English string suitable for display

### WebSocket Error Format
Errors during an active WS session must be sent as a `ServerEnvelope` with type `ERROR`:
```json
{
  "v": 1,
  "seq": 12,
  "table_id": "t_abc",
  "type": "ERROR",
  "payload": {
    "code": "NOT_YOUR_TURN",
    "message": "It is not your turn to act."
  },
  "ts": 1700000000.0
}
```
The connection must **stay open** after non-fatal errors (invalid action, malformed message).
The connection must **close** only for fatal errors (auth failure, table not found).

### WebSocket Close Codes
| Code | Meaning | Trigger |
|------|---------|---------|
| 4001 | Unauthorized | Token missing, invalid, or expired at connect time |
| 4003 | Table full | Table is full and client did not request spectator role |
| 4004 | Not found | table_id does not exist or table has been closed |
| 1000 | Normal closure | Client sent LEAVE_TABLE or voluntary disconnect |

---

## Screens / Surfaces (Developer-Facing)

### GET /health
```json
{
  "status": "ok",
  "app_env": "development",
  "active_tables": 2,
  "version": "0.1.0"
}
```

### STATE_SNAPSHOT Content Requirements
The snapshot sent on WS connect and on reconnect must include:
- `table_id`
- `club_id`
- `club_name` *(added per player-feedback.md — avoids extra HTTP call)*
- `admin_id` *(added per player-feedback.md — allows UI to show/hide config button)*
- `phase` — current hand phase
- `players[]` — each player: user_id, display_name, seat_index, stack, status, is_connected
- `community_cards[]` — visible cards (masked as `?` if not yet dealt)
- `pot` — total pot and pot breakdown
- `your_cards[]` — hole cards for the requesting player (masked for spectators and others)
- `current_turn_seat` — whose turn it is (-1 if none)
- `turn_deadline` — Unix timestamp of when the turn timer fires (null if no timer)
- `hand_number` — integer, current hand count

### PLAYER_STATUS "disconnected" Event
Must include `reserve_until` field per player-feedback.md:
```json
{
  "user_id": "u_abc",
  "status": "disconnected",
  "stack": 950,
  "reserve_until": 1700000060.0
}
```

---

## Key Components (API Layer)

| Component | Purpose |
|-----------|---------|
| `POST /auth/request-otp` | Rate-limited in prod; returns 200 even if phone invalid (prevent enumeration) |
| `POST /auth/verify-otp` | OTP consumed on first use; second attempt with same code → 400 |
| `GET /health` | No auth required; safe to poll |
| `WS endpoint` | Token in query param; validated before upgrade accepted |
| `ServerEnvelope` | `seq` field must be monotonically increasing per table (client detects gaps) |

---

## Interaction Behavior

### On Malformed WS Message
1. Server catches JSON parse error
2. Server sends ERROR envelope: `{"code": "INVALID_MESSAGE", "message": "..."}`
3. Connection stays open

### On Valid JSON but Invalid Pydantic Schema
1. Pydantic raises `ValidationError`
2. Server sends ERROR envelope: `{"code": "INVALID_PAYLOAD", "message": "..."}`
3. Connection stays open

### On Engine ValueError (invalid action)
1. `session_manager.handle_action` raises `ValueError`
2. Server catches it, sends ERROR envelope with message from exception
3. Connection stays open

### On WS Client Disconnect (any cause)
1. Server's `iter_text()` loop exits
2. Server calls `session_manager.disconnect(user_id)`
3. 60-second timer starts on session_manager side

---

## Error, Loading, and Empty States

| State | Server Behavior | Client Expectation |
|-------|-----------------|--------------------|
| No players at table | Phase is WAITING_FOR_PLAYERS | STATE_SNAPSHOT shows empty seats |
| Hand in progress, new player joins | Player seated as WAITING | PLAYER_JOINED broadcast; player waits for next hand |
| All players fold | HAND_RESULT → HAND_END → 3s delay → next hand | Client shows result screen for 3 seconds |
| Only 1 player left | Hand cannot start | Phase stays WAITING_FOR_PLAYERS |
| Server restart | In-memory state lost | Client must reconnect and rejoin; expected for MVP |

---

## Notes for Mobile Constraints

- No HTTP polling permitted. State is pushed via WebSocket only.
- The mobile client must handle background/foreground transitions by reconnecting the WS.
- `turn_deadline` must be used by the client to render a countdown timer. Do not rely on
  client-side timing alone — use server `ts` timestamps to sync.
- `seq` gaps indicate a missed event; client should send SYNC_REQUEST to re-sync.
- Token lifetime is 24 hours (MVP). Token is validated only on WS connect, not mid-session.

---

## UX Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| STATE_SNAPSHOT payload size grows with player count | Minor render delay on mobile | Capped at 10 players; payload is small |
| Missed sequence numbers not detected by client | Player sees wrong game state | Document SYNC_REQUEST in client integration guide |
| `reserve_until` not included in PLAYER_STATUS → client can't show countdown | Confusing UX | Required field in WS spec (per player-feedback.md) |
| Admin_id not in snapshot → client can't show config button | Wrong UI state | Required field in STATE_SNAPSHOT (per player-feedback.md) |

---

## UX Sign-off

- [x] All API surfaces defined with explicit error codes and messages
- [x] WS close codes defined for all failure modes
- [x] STATE_SNAPSHOT content defined completely
- [x] Player-feedback items incorporated (reserve_until, admin_id, plain-language errors)
- [x] No mobile UI screens required for this feature
- Date: 2026-03-19
- Notes: UX Gate passed. Technical design may proceed.
