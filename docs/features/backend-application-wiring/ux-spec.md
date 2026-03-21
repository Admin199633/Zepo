# UX Spec — backend-application-wiring

> Owner: Senior UI/UX Designer
> Input: feature-spec.md, player-feedback.md
> Gate: UX Gate (Gate 2)
> Status: APPROVED
> Reference: backend-app-bootstrap ux-spec.md (approved 2026-03-19)

---

## Scope Note

This is a backend-only feature. The UX deliverable is the API contract: error surfaces,
connection flow, event sequence, and state visibility for the mobile client developer.
This spec refines and finalises the contract from `backend-app-bootstrap/ux-spec.md`
with decisions made during this feature's design phase.

---

## Connection and Join Flow

```
1. Client opens WS /ws/table/{table_id}?token=<jwt>
   Server: validates token → accepts or closes 4001
   Server: looks up table → if missing, closes 4004
   [Nothing sent to client yet]

2. Client sends JOIN_TABLE { role: "player" | "spectator" }
   Server: routes to session_manager.join_as_player / join_as_spectator
   Server → Client (private): STATE_SNAPSHOT
   Server → All:              PLAYER_JOINED

3. [If 2+ players ACTIVE] → hand starts after 3s delay
   Server → All:  PHASE_CHANGED
   Server → Each player (private): CARDS_DEALT (hole cards)
   Server → All:  BLINDS_POSTED, TURN_CHANGED

4. Client sends ACTION
   Server → All:  PLAYER_ACTED, TURN_CHANGED

5. WS closes (any cause)
   Server → All:  PLAYER_STATUS { status: "disconnected", reserve_until: <ts> }

6. Client reconnects (within 60s)
   [Repeat from step 1; JOIN_TABLE not required — session_manager.reconnect() called]
   Server → Client (private): STATE_SNAPSHOT
   Server → All:  PLAYER_STATUS { status: current_status }
```

**Reconnect note:** If the same `user_id` connects while already present in the session
manager (step 1 → step 6), the session manager treats it as a reconnect automatically
(see `join_as_player` source). The WS router must detect this case via the
`JoinResult.error_code == ALREADY_SEATED` path and not double-join.

---

## HTTP API Contract

All 4xx/5xx responses use this exact JSON shape — no exceptions:
```json
{ "error": "ERROR_CODE", "message": "Human readable string." }
```

### Endpoint Contracts

| Endpoint | Success | Key Errors |
|---------|---------|-----------|
| `POST /auth/request-otp` | `200 {}` | `400 INVALID_PHONE` |
| `POST /auth/verify-otp` | `200 { token, user_id, expires_at }` | `400 INVALID_OTP` |
| `POST /clubs` | `201 { club_id, table_id, invite_code }` | `401 UNAUTHORIZED` |
| `GET /clubs/{id}` | `200 { club_id, name, owner_id, invite_code, member_count }` | `403 NOT_MEMBER`, `404 NOT_FOUND` |
| `POST /clubs/{id}/join` | `200 { club_id, table_id }` | `400 INVALID_INVITE_CODE`, `409 ALREADY_MEMBER` |
| `GET /clubs/{id}/table` | `200 { table_id, config, recent_hands[] }` | `403 NOT_MEMBER`, `404 NOT_FOUND` |
| `PATCH /clubs/{id}/table/config` | `200 { config }` | `403 NOT_ADMIN`, `400 INVALID_CONFIG` |
| `GET /health` | `200 { status, app_env, active_tables, version, state_persistence }` | none |

### Health Response Shape (incorporating player-feedback.md)
```json
{
  "status": "ok",
  "app_env": "development",
  "active_tables": 2,
  "version": "0.1.0",
  "state_persistence": "in_memory_volatile"
}
```
`state_persistence` is `"in_memory_volatile"` when `app_env != "production"`, and
`"sqlite"` or `"postgres"` in production. This surfaces data durability at a glance.

---

## WebSocket Event Contract

### WS Close Codes
| Code | Cause |
|------|-------|
| `4001` | Token missing, unparseable, or expired at connect time |
| `4004` | `table_id` not found in persistence |
| `1000` | Normal closure (client sends LEAVE_TABLE or voluntarily disconnects) |

Table-full is handled as an ERROR event (not a close): the client can resend
JOIN_TABLE with `"role": "spectator"`.

### WS Error Events (non-fatal, connection stays open)
```json
{
  "v": 1, "seq": N, "table_id": "t_xyz", "type": "ERROR", "ts": 0.0,
  "payload": {
    "code": "NOT_YOUR_TURN",
    "message": "It is not your turn to act.",
    "request_id": "<echoed from client message>"
  }
}
```
`request_id` in ERROR payload must always be populated when the error is triggered by
a client message (per player-feedback.md). This allows the mobile client to correlate
errors to specific tapped actions.

### Error Code Registry
| Code | Trigger |
|------|---------|
| `INVALID_MESSAGE` | JSON parse failure |
| `INVALID_PAYLOAD` | Pydantic schema validation failure |
| `NOT_YOUR_TURN` | Action sent when it's not this player's turn |
| `INVALID_ACTION` | Engine rejects action for any other reason |
| `TABLE_FULL` | JOIN_TABLE as player when table has no available seats |
| `INVALID_PHASE` | Action sent when no hand is in progress |
| `NOT_JOINED` | SIT_OUT/SIT_IN/ACTION before JOIN_TABLE |

### PLAYER_STATUS Payload (with reserve_until)
```json
{
  "user_id": "u_abc",
  "status": "disconnected",
  "stack": 950,
  "reserve_until": 1700000060.0
}
```
`reserve_until` is populated only when `status == "disconnected"`. It is `null`
for all other status values.

### STATE_SNAPSHOT Content
Produced by `build_player_view(state, user_id)` or `build_spectator_view(state)`.
Contains: `table_id`, `club_id`, `phase`, `hand_number`, `players[]`, `seat_map`,
`config`, `hand` (with hole cards masked for non-owners / spectators), no deck.
`club_name` and `admin_id` are deferred (require session_manager extension — see Q1
in feature-spec.md).

---

## Client Message Routing

| Client Message Type | Session Manager Method | Notes |
|--------------------|----------------------|-------|
| `JOIN_TABLE` | `join_as_player` or `join_as_spectator` | Role in payload |
| `ACTION` | `handle_action` | `request_id` passed for idempotency |
| `CHAT` | `handle_chat` | |
| `SIT_OUT` | `sit_out` | Ignored if not a player |
| `SIT_IN` | `sit_in` | Ignored if not SIT_OUT |
| `LEAVE_TABLE` | `leave` | Removes from session |
| `SYNC_REQUEST` | `send_sync` | Private STATE_SNAPSHOT to requester |

---

## Operator / Developer Visibility

- **Running the server**: `uvicorn backend.main:app --reload`
- **Checking state**: `GET /health` — shows active tables, env, persistence mode
- **Checking OTP in dev**: OTP printed to stdout by `ConsoleAuthService`
- **Sequence gaps**: `seq` on ServerEnvelope is monotonic per table; client detects
  gaps and triggers `SYNC_REQUEST`

---

## UX Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Client doesn't send JOIN_TABLE → no STATE_SNAPSHOT, UI blank | Developer confusion | Document clearly in integration guide |
| `reserve_until` not populated → client can't show countdown | Confusing disconnect UX | Required field; populated in WS router disconnect path |
| State lost on server restart → player rejoins empty table | Frustrating | Surfaced via `state_persistence` in `/health` |
| ERROR event without `request_id` → client can't correlate | Silent failure | Required; WS router always echoes `request_id` |

---

## UX Gate Sign-off

- [x] All HTTP endpoints specified with exact response shapes and error codes
- [x] WS close codes defined for all fatal failure modes
- [x] ERROR event contract defined with `request_id` echo requirement
- [x] `reserve_until` field required in PLAYER_STATUS disconnect event
- [x] `state_persistence` field required in health response
- [x] Connection and join flow fully sequenced
- [x] Player-feedback items incorporated
- Date: 2026-03-19
- Notes: UX Gate passed. Technical design may proceed.
