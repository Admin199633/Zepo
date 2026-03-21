# Technical Design — backend-app-bootstrap

> Owner: Senior Mobile Game Developer
> Input: feature-spec.md, ux-spec.md
> Gate: Technical Gate (Gate 3)
> Status: APPROVED

---

## Technical Overview

This feature adds the application layer that makes the backend deployable. It wires
the existing `TableSessionManager`, `PersistenceAdapter`, service interfaces, and
realtime schemas into a running FastAPI server. The only new logic introduced is
connection management (`WebSocketBroadcaster`, `TableSessionRegistry`) and HTTP/WS
routing. The game engine and session manager are not modified.

The server is structured around three layers:
1. **Transport** — FastAPI HTTP routes + WebSocket endpoint
2. **Session coordination** — `TableSessionRegistry` maps table_id → `TableSessionManager`
3. **Infrastructure** — `WebSocketBroadcaster` implements `BroadcastService`, `InMemoryPersistenceAdapter` implements `PersistenceAdapter`

---

## Module Breakdown

| Module | File | Responsibility | New / Modified |
|--------|------|---------------|----------------|
| App factory | `backend/main.py` | Create FastAPI app, mount routers, lifespan events | **New** |
| Dependency injection | `backend/dependencies.py` | FastAPI `Depends` factories for shared singletons | **New** |
| Session registry | `backend/session_registry.py` | `TableSessionRegistry`: owns all active `TableSessionManager` instances | **New** |
| WS broadcaster | `backend/realtime/ws_broadcaster.py` | Concrete `BroadcastService` over live WebSocket connections | **New** |
| WS router | `backend/realtime/ws_router.py` | WS endpoint, token validation, message dispatch loop | **New** |
| Auth router | `backend/api/auth_router.py` | POST /auth/request-otp, POST /auth/verify-otp | **New** |
| Clubs router | `backend/api/clubs_router.py` | POST /clubs, GET /clubs/{id}, POST /clubs/{id}/join | **New** |
| Tables router | `backend/api/tables_router.py` | GET /clubs/{id}/table, PATCH /clubs/{id}/table/config | **New** |
| Health router | `backend/api/health_router.py` | GET /health | **New** |
| Env example | `.env.example` | Documents all required env vars | **New** |
| Requirements | `requirements-backend.txt` | Add fastapi[standard], uvicorn[standard], pyjwt | **Modified** |

---

## Data Structures

```python
# backend/session_registry.py

class TableSessionRegistry:
    """
    Singleton created at app startup. Holds all active TableSessionManager
    instances. Creates a new manager when a table_id is first requested.
    Thread-safe via asyncio.Lock.
    """
    _sessions: dict[str, TableSessionManager]
    _lock: asyncio.Lock

    async def get_or_create(
        self,
        table_id: str,
        club_id: str,
        config: TableConfig,
        persistence: PersistenceAdapter,
        broadcaster: BroadcastService,
    ) -> TableSessionManager: ...

    def get(self, table_id: str) -> TableSessionManager | None: ...

    async def remove(self, table_id: str) -> None: ...


# backend/realtime/ws_broadcaster.py

@dataclass
class ConnectionRecord:
    websocket: WebSocket
    user_id: str
    table_id: str
    role: str  # "player" | "spectator"

class WebSocketBroadcaster:
    """
    Implements BroadcastService Protocol.
    Maintains: _connections: dict[str, dict[str, ConnectionRecord]]
               where outer key = table_id, inner key = user_id
    Send failures (stale WS) are caught, logged, and ignored — never raised.
    """
    _connections: dict[str, dict[str, ConnectionRecord]]
    _lock: asyncio.Lock

    async def register(self, table_id: str, user_id: str, ws: WebSocket, role: str) -> None: ...
    async def unregister(self, table_id: str, user_id: str) -> None: ...
    async def send_to_player(self, table_id: str, user_id: str, envelope: ServerEnvelope) -> None: ...
    async def broadcast_to_table(self, table_id: str, envelope: ServerEnvelope, exclude_user_id: str | None = None) -> None: ...
    async def broadcast_to_spectators(self, table_id: str, envelope: ServerEnvelope) -> None: ...
```

---

## API and Contracts

### HTTP: Client → Server

```
POST /auth/request-otp
Body:     { "phone_number": "+972501234567" }
Response: 200 {}

POST /auth/verify-otp
Body:     { "phone_number": "+972501234567", "code": "123456", "display_name": "Lior" }
Response: 200 { "token": "...", "user_id": "u_abc", "expires_at": 1700086400.0 }
Errors:   400 { "error": "INVALID_OTP", "message": "..." }

POST /clubs                                          [auth required]
Body:     { "name": "Friday Night Poker" }
Response: 201 { "club_id": "c_abc", "table_id": "t_xyz", "invite_code": "ABC123" }

GET /clubs/{club_id}                                 [auth required]
Response: 200 { "club_id", "name", "admin_id", "invite_code", "member_count" }
Errors:   404

POST /clubs/{club_id}/join                           [auth required]
Body:     { "invite_code": "ABC123" }
Response: 200 { "club_id": "c_abc", "table_id": "t_xyz" }
Errors:   400 INVALID_INVITE_CODE, 409 ALREADY_MEMBER

GET /clubs/{club_id}/table                           [auth required, member only]
Response: 200 { "table_id", "config": { TableConfig fields }, "recent_hands": [ HandSummary ] }

PATCH /clubs/{club_id}/table/config                  [auth required, admin only]
Body:     { partial TableConfig fields }
Response: 200 { "config": { updated TableConfig } }
Errors:   403 NOT_ADMIN, 400 INVALID_CONFIG

GET /health                                          [no auth]
Response: 200 { "status": "ok", "app_env": "...", "active_tables": 2, "version": "0.1.0" }
```

### WebSocket: Client → Server (ClientEnvelope)

```json
{ "type": "JOIN_TABLE",  "request_id": "<uuid4>", "table_id": "t_xyz", "payload": { "role": "player" } }
{ "type": "ACTION",      "request_id": "<uuid4>", "table_id": "t_xyz", "payload": { "action": "call", "amount": 0 } }
{ "type": "CHAT",        "request_id": "<uuid4>", "table_id": "t_xyz", "payload": { "message": "gg" } }
{ "type": "SIT_OUT",     "request_id": "<uuid4>", "table_id": "t_xyz", "payload": {} }
{ "type": "SIT_IN",      "request_id": "<uuid4>", "table_id": "t_xyz", "payload": {} }
{ "type": "LEAVE_TABLE", "request_id": "<uuid4>", "table_id": "t_xyz", "payload": {} }
{ "type": "SYNC_REQUEST","request_id": "<uuid4>", "table_id": "t_xyz", "payload": {} }
```

### WebSocket: Server → Client (ServerEnvelope — additions to existing schema)

The `PLAYER_STATUS` payload is extended with `reserve_until`:
```json
{
  "type": "PLAYER_STATUS",
  "payload": {
    "user_id": "u_abc",
    "status": "disconnected",
    "stack": 950,
    "reserve_until": 1700000060.0
  }
}
```

The `STATE_SNAPSHOT` payload is extended with `club_name` and `admin_id`:
```json
{
  "type": "STATE_SNAPSHOT",
  "payload": {
    "table_id": "t_xyz",
    "club_id": "c_abc",
    "club_name": "Friday Night Poker",
    "admin_id": "u_host",
    "phase": "PRE_FLOP",
    "players": [...],
    "community_cards": [...],
    "pot": { "total": 150, "pots": [...] },
    "your_cards": [{"rank": "A", "suit": "S"}, {"rank": "K", "suit": "H"}],
    "current_turn_seat": 2,
    "turn_deadline": 1700000030.0,
    "hand_number": 5
  }
}
```

---

## Event Flow

### Happy Path: WS Connect → Join → Hand → Action

```
1. Client opens WS /ws/table/t_xyz?token=<jwt>
2. Server: verify_token(token) → User  [reject with 4001 if invalid]
3. Server: registry.get_or_create(table_id, ...) → TableSessionManager
4. Server: broadcaster.register(table_id, user_id, ws, role=None)  [before JOIN_TABLE]
5. Server: send STATE_SNAPSHOT privately to user  [before JOIN_TABLE, on connect]
6. Client sends: { type: JOIN_TABLE, payload: { role: "player" } }
7. Server: session_manager.join_as_player(user_id, display_name, connection_id)
8. session_manager emits PLAYER_JOINED → broadcaster.broadcast_to_table
9. [If 2+ players active] → session_manager schedules _start_hand_after_delay (3s)
10. After 3s: PHASE_CHANGED(START_HAND), EvtCardsDealt → send_to_player each, BLINDS_POSTED, TURN_CHANGED → broadcast
11. Client sends: { type: ACTION, payload: { action: "call", amount: 0 } }
12. Server: session_manager.handle_action(user_id, "call", 0, request_id)
13. Engine applies action → PLAYER_ACTED, TURN_CHANGED → broadcast_to_table
14. ... hand continues to HAND_RESULT → broadcast_to_table
15. Client closes WS (network drop or explicit)
16. Server: _dispatch_loop exits → broadcaster.unregister → session_manager.disconnect(user_id)
17. 60s timer starts on session_manager
```

---

## State Transitions

```
WS_CONNECTING  →  token valid    →  WS_OPEN (pre-join)
WS_CONNECTING  →  token invalid  →  WS_CLOSED(4001)
WS_OPEN        →  JOIN_TABLE     →  SEATED (or SPECTATING)
WS_OPEN        →  table full     →  ERROR sent, WS stays open (client can rejoin as spectator)
WS_OPEN        →  table missing  →  WS_CLOSED(4004)
SEATED         →  ACTION         →  engine processes, events broadcast
SEATED         →  SIT_OUT        →  PlayerStatus.SIT_OUT
SIT_OUT        →  SIT_IN         →  PlayerStatus.WAITING
SEATED         →  WS drop        →  DISCONNECTED (60s timer)
DISCONNECTED   →  reconnect <60s →  SEATED + STATE_SNAPSHOT
DISCONNECTED   →  timeout 60s    →  SIT_OUT
```

---

## Validation Rules

All server-side. Client input is never trusted.

- Token: must be decodable, non-expired, user_id must exist in persistence
- `table_id` in WS URL: must match an existing TableRecord
- `club_id` membership: user must be a member of the club that owns the table
- Club admin check: PATCH /table/config requires `actor_id == club.admin_id`
- JOIN_TABLE `role`: must be `"player"` or `"spectator"` (validated by Pydantic)
- ACTION `action` field: validated by existing `ActionPayload` schema
- CHAT `message`: stripped, non-empty, max 500 chars (validated by existing `ChatPayload`)
- All incoming WS messages: parsed as `ClientEnvelope` by Pydantic; any parse failure → ERROR event, connection stays open

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `WebSocketBroadcaster` stale connection during broadcast | Silent message loss | Catch `WebSocketDisconnect` / `RuntimeError` per send; log and continue |
| `TableSessionRegistry.get_or_create` called concurrently for same table_id | Duplicate `TableSessionManager` created | Use `asyncio.Lock`; check-then-create inside lock |
| `session_manager.disconnect` not called if WS message loop crashes | Seat reserved forever | Use `try/finally` in WS handler to guarantee `disconnect` is called |
| STATE_SNAPSHOT sent before JOIN_TABLE — player gets snapshot but hasn't joined | Possible UI confusion | Snapshot on connect shows current table state; joining is separate. This is correct — spectators also need snapshots. |
| In-memory broadcaster won't work across multiple server processes | Only works single-process | Acceptable for MVP. Document: must use Redis broadcaster for horizontal scaling. |

---

## Implementation Notes

- Use `@asynccontextmanager` with `lifespan=` parameter in FastAPI app factory (not
  deprecated `@app.on_event`).
- WS handler pattern:
  ```python
  try:
      async for text in websocket.iter_text():
          await dispatch(text, user, session_manager)
  except WebSocketDisconnect:
      pass
  finally:
      await broadcaster.unregister(table_id, user_id)
      await session_manager.disconnect(user_id)
  ```
- `WebSocketBroadcaster` must not hold the lock during the actual `ws.send_text()` call
  to avoid blocking. Copy the list of connections under the lock, then send outside.
- `ConsoleAuthService` is used for dev. For prod, swap via dependency injection — no
  change to routes required.
- `InMemoryPersistenceAdapter` is used for dev. Same swap pattern.
- `.env.example` must document every variable in `backend/config.py` with a safe default
  and a comment for production requirements.
- Version string (`0.1.0`) is hardcoded in `health_router.py` for MVP.

---

## Technical Sign-off

- [x] QA has reviewed for risks and edge cases
- [x] PM approved — scope matches feature-spec.md
- [x] UX contract requirements incorporated (reserve_until, admin_id, club_name, error formats)
- Date: 2026-03-19
- Notes: Technical Gate passed. Task breakdown and implementation may proceed.
