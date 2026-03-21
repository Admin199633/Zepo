# Technical Design — backend-application-wiring

> Owner: Senior Mobile Game Developer
> Input: feature-spec.md, ux-spec.md
> Gate: Technical Gate (Gate 3)
> Status: APPROVED

---

## Architectural Review

### Review Criteria and Findings

This review audits the six boundary requirements before any implementation begins.

#### 1. Engine Isolation

**Finding: PASS**

`poker_engine/` contains zero imports from `backend/`. Verified by inspection:
- `poker_engine/engine/models.py` — imports only stdlib (`dataclasses`, `enum`, `uuid`, `time`)
- `poker_engine/engine/game_engine.py` — imports only from `poker_engine/`
- `poker_engine/rules/` — imports only from `poker_engine/`

The engine is a pure Python library. It can be packaged and published independently.

#### 2. No DB or Transport Logic in Engine

**Finding: PASS**

No DB connections, HTTP calls, WebSocket references, or asyncio patterns exist in
`poker_engine/`. The engine is synchronous and deterministic.

#### 3. Hidden Card Data Cannot Reach Spectators

**Finding: PASS with one observation**

`poker_engine/engine/view_builder.py:build_spectator_view()` masks all hole cards as
`{"rank":"?","suit":"?"}` during any phase prior to `HAND_END`. At `HAND_END`,
winners' cards are revealed (showdown). This is correct.

`session_manager._dispatch_events()` routes `EvtCardsDealt` to `send_to_player`
(private) only — never to `broadcast_to_table`. Confirmed.

**Observation (non-blocking):** `session_manager._dispatch_events` contains inline
imports of engine event types on lines 628–633. These should be at module top level.
This is a style issue, not a boundary violation. Fix as part of this feature's cleanup.

#### 4. Deck State Is Never Persisted

**Finding: PASS**

`PersistenceAdapter.save_game_state_snapshot` docstring explicitly states:
"The caller is responsible for stripping the deck before calling."
`session_manager._persist_phase_snapshot()` uses `build_spectator_view(state)` as
the snapshot source. `view_builder` never includes the deck key. Verified.

`InMemoryPersistenceAdapter.save_game_state_snapshot` also defensively strips `deck`.

#### 5. SessionManager Is Orchestration-Only

**Finding: PASS**

`TableSessionManager` has no game logic. It:
- Delegates all game decisions to `GameEngine`
- Delegates all persistence to `PersistenceAdapter`
- Delegates all messaging to `BroadcastService`
- Manages timers, lock, and sequence numbers

No poker rules are implemented in `session_manager.py`.

#### 6. API / Realtime / Persistence / Sessions Boundaries

**Finding: PASS with two observations**

Correct dependency direction:
```
poker_engine ← backend/persistence (models only)
poker_engine ← backend/sessions
poker_engine ← backend/realtime (CardDTO etc.)
backend/sessions → backend/persistence (interface)
backend/sessions → backend/realtime (schemas + broadcaster)
backend/sessions → backend/analytics (fire-and-forget)
backend/api → (to be created) → backend/dependencies → all singletons
```

`backend/api/__init__.py` is currently empty. `backend/api/` is a clean namespace
ready for routers.

**Observation 1 (non-blocking):** `backend/persistence/adapter.py` imports
`GameState` from `poker_engine.engine.models` but `GameState` is never used in
any method signature (snapshots are persisted as `dict`). This import is dead code.
Remove as part of this feature.

**Observation 2 (non-blocking):** `backend/sessions/session_manager.py` creates a
fire-and-forget task for `save_chat_message` without attaching a done-callback:
```python
asyncio.create_task(self._persistence.save_chat_message(chat_msg))
```
If this coroutine raises, the exception is silently swallowed. Add error logging via
`task.add_done_callback`. Fix as part of this feature's cleanup.

### Review Summary

| Check | Result |
|-------|--------|
| Engine isolation | ✅ Pass |
| No DB/transport in engine | ✅ Pass |
| Hidden card data blocked | ✅ Pass |
| Deck not persisted | ✅ Pass |
| SessionManager orchestration-only | ✅ Pass |
| Module boundaries clean | ✅ Pass (2 non-blocking observations, fix in this feature) |

**No blocking violations. Implementation may proceed.**

---

## Technical Overview

This feature wires the existing backend modules into a running FastAPI server.
New code is transport and wiring only. No game logic moves. No engine changes.

The implementation divides into four layers:
1. **Infrastructure** — `WebSocketBroadcaster`, `TableSessionRegistry`, DI container
2. **Transport** — HTTP routers + WebSocket gateway
3. **Persistence scaffold** — `SqlitePersistenceAdapter` structural skeleton
4. **Test harness** — end-to-end integration tests

---

## Module Breakdown

| Module | File | Responsibility | Status |
|--------|------|---------------|--------|
| App factory | `backend/main.py` | FastAPI app, lifespan, router mounting, CORS | New |
| DI container | `backend/dependencies.py` | `app.state` singletons, `get_current_user` | New |
| Session registry | `backend/session_registry.py` | `TableSessionRegistry` | New |
| WS broadcaster | `backend/realtime/ws_broadcaster.py` | `WebSocketBroadcaster` | New |
| WS gateway | `backend/realtime/ws_router.py` | WS endpoint, dispatch loop | New |
| Auth router | `backend/api/auth_router.py` | OTP request/verify | New |
| Clubs router | `backend/api/clubs_router.py` | Create, get, join club | New |
| Tables router | `backend/api/tables_router.py` | Get, update table config | New |
| Health router | `backend/api/health_router.py` | Health check | New |
| SQLite adapter | `backend/persistence/sqlite_adapter.py` | Scaffold + DB schema | New |
| Schema update | `backend/realtime/schemas.py` | Add `reserve_until` to `PlayerStatusPayload` | Modified |
| Cleanup | `backend/persistence/adapter.py` | Remove dead `GameState` import | Modified |
| Cleanup | `backend/sessions/session_manager.py` | Move inline imports to top; add error callback on chat task | Modified |
| Config | `.env.example`, `requirements-backend.txt` | Env vars, dependencies | New/Modified |
| Tests | `tests/test_app_integration.py` | End-to-end integration tests | New |

---

## Data Structures

```python
# backend/session_registry.py

class TableSessionRegistry:
    _sessions: dict[str, TableSessionManager]
    _lock: asyncio.Lock

    async def get_or_create(
        table_id: str,
        club_id: str,
        config: TableConfig,
        persistence: PersistenceAdapter,
        broadcaster: BroadcastService,
    ) -> TableSessionManager

    def get(table_id: str) -> TableSessionManager | None

    async def remove(table_id: str) -> None

    @property
    def active_count(self) -> int


# backend/realtime/ws_broadcaster.py

@dataclass
class ConnectionRecord:
    websocket: WebSocket
    user_id: str
    table_id: str
    role: str  # "player" | "spectator" | "unknown" (pre-JOIN_TABLE)

class WebSocketBroadcaster:
    _connections: dict[str, dict[str, ConnectionRecord]]  # table_id → {user_id → record}
    _lock: asyncio.Lock

    async def register(table_id, user_id, ws, role) -> None
    async def update_role(table_id, user_id, role) -> None
    async def unregister(table_id, user_id) -> None
    async def send_to_player(table_id, user_id, envelope) -> None
    async def broadcast_to_table(table_id, envelope, exclude_user_id=None) -> None
    async def broadcast_to_spectators(table_id, envelope) -> None
    async def _safe_send(ws, envelope) -> None  # catches all exceptions, logs


# backend/persistence/sqlite_adapter.py (scaffold)

# SQLAlchemy Core table definitions:
users_table         = Table("users", ...)
clubs_table         = Table("clubs", ...)
club_memberships    = Table("club_memberships", ...)
tables_table        = Table("tables", ...)
hand_summaries      = Table("hand_summaries", ...)
game_snapshots      = Table("game_snapshots", ...)
player_sessions     = Table("player_sessions", ...)
player_stats        = Table("player_stats", ...)
chat_messages       = Table("chat_messages", ...)

class SqlitePersistenceAdapter(PersistenceAdapter):
    def __init__(self, database_url: str) -> None: ...
    # All abstract methods: raise NotImplementedError("TODO: implement for production")
```

---

## API and Contracts

### HTTP Request / Response Models (Pydantic)

```python
# Auth
class OtpRequestBody(BaseModel):
    phone_number: str           # validated: must start with "+"

class OtpVerifyBody(BaseModel):
    phone_number: str
    code: str
    display_name: Optional[str] = None

class TokenResponse(BaseModel):
    token: str
    user_id: str
    expires_at: float

# Clubs
class CreateClubBody(BaseModel):
    name: str                   # 1–64 chars, stripped

class JoinClubBody(BaseModel):
    invite_code: str

class ClubResponse(BaseModel):
    club_id: str
    name: str
    owner_id: str
    invite_code: str
    member_count: int

class CreateClubResponse(BaseModel):
    club_id: str
    table_id: str
    invite_code: str

# Tables
class TableConfigPatchBody(BaseModel):
    small_blind: Optional[int] = None
    big_blind: Optional[int] = None
    turn_timer_seconds: Optional[int] = None
    max_players: Optional[int] = None
    house_rules: Optional[list[str]] = None

# Health
class HealthResponse(BaseModel):
    status: str
    app_env: str
    active_tables: int
    version: str
    state_persistence: str      # "in_memory_volatile" | "sqlite" | "postgres"
```

---

## Event Flow

### WS Handler Dispatch Loop

```python
@ws_router.websocket("/ws/table/{table_id}")
async def ws_table_endpoint(websocket, table_id, token=""):
    await websocket.accept()

    # 1. Token validation
    try:
        user = await auth_service.verify_token(token)
    except ValueError:
        await websocket.close(code=4001, reason="unauthorized")
        return

    # 2. Table lookup
    table_record = await persistence.get_table(table_id)
    if table_record is None:
        await websocket.close(code=4004, reason="table_not_found")
        return

    # 3. Get/create session manager
    session_manager = await registry.get_or_create(
        table_id, table_record.club_id, table_record.config,
        persistence, broadcaster
    )

    # 4. Register connection
    connection_id = str(uuid.uuid4())
    await broadcaster.register(table_id, user.id, websocket, role="unknown")

    # 5. Dispatch loop
    try:
        async for text in websocket.iter_text():
            await _dispatch_message(text, user, table_id, session_manager, broadcaster, websocket)
    except WebSocketDisconnect:
        pass
    finally:                                    # ← CRITICAL: always runs
        await broadcaster.unregister(table_id, user.id)
        await session_manager.disconnect(user.id)


async def _dispatch_message(text, user, table_id, session_manager, broadcaster, ws):
    # Parse envelope
    try:
        envelope = ClientEnvelope.model_validate_json(text)
    except (ValueError, ValidationError) as e:
        await _send_error(ws, table_id, "INVALID_MESSAGE", str(e), request_id=None)
        return

    req_id = envelope.request_id

    try:
        match envelope.type:
            case ClientMessageType.JOIN_TABLE:
                payload = JoinTablePayload.model_validate(envelope.payload)
                if payload.role == "player":
                    result = await session_manager.join_as_player(
                        user.id, user.display_name, connection_id
                    )
                    if not result.success:
                        await _send_error(ws, table_id, result.error_code.value,
                                         result.error_message or "", req_id)
                    else:
                        await broadcaster.update_role(table_id, user.id, "player")
                else:
                    await session_manager.join_as_spectator(
                        user.id, user.display_name, connection_id
                    )
                    await broadcaster.update_role(table_id, user.id, "spectator")

            case ClientMessageType.ACTION:
                payload = ActionPayload.model_validate(envelope.payload)
                await session_manager.handle_action(
                    user.id, payload.action, payload.amount, req_id
                )

            case ClientMessageType.CHAT:
                payload = ChatPayload.model_validate(envelope.payload)
                await session_manager.handle_chat(user.id, user.display_name, payload.message)

            case ClientMessageType.SIT_OUT:
                await session_manager.sit_out(user.id)

            case ClientMessageType.SIT_IN:
                await session_manager.sit_in(user.id)

            case ClientMessageType.LEAVE_TABLE:
                await session_manager.leave(user.id)

            case ClientMessageType.SYNC_REQUEST:
                await session_manager.send_sync(user.id)

    except ValidationError as e:
        await _send_error(ws, table_id, "INVALID_PAYLOAD", str(e), req_id)
    except ValueError as e:
        await _send_error(ws, table_id, "INVALID_ACTION", str(e), req_id)
```

---

## State Transitions

```
WS_CONNECTING  → token valid + table exists  → WS_OPEN (pre-join, role=unknown)
WS_CONNECTING  → invalid token               → CLOSED(4001)
WS_CONNECTING  → table not found             → CLOSED(4004)

WS_OPEN        → JOIN_TABLE "player"  → session_manager.join_as_player → SEATED
WS_OPEN        → JOIN_TABLE "spectator" → session_manager.join_as_spectator → SPECTATING
WS_OPEN        → table full           → ERROR(TABLE_FULL), stays open (can rejoin as spectator)

SEATED         → ACTION               → engine processes, events broadcast
SEATED         → SIT_OUT              → PlayerStatus.SIT_OUT
SEATED         → LEAVE_TABLE          → removed from session
SEATED         → WS drop              → session_manager.disconnect → 60s timer

DISCONNECTED   → WS reconnect <60s   → session_manager.join_as_player → reconnect path
DISCONNECTED   → timeout 60s         → SIT_OUT (session_manager internal timer)
```

---

## Validation Rules

Server-side only; client data is never trusted.

- Token: valid JWT or "dev_" prefix (ConsoleAuthService); user must exist in persistence.
- `table_id` in URL: must exist in persistence before WS is accepted.
- Club membership: checked on all HTTP routes (GET/PATCH club endpoints).
- Admin check: `PATCH /clubs/{id}/table/config` checks `club.is_admin(actor_id)`.
- `JOIN_TABLE role`: validated by `JoinTablePayload` — must be `"player"` or `"spectator"`.
- All client WS payloads: Pydantic validation before any session_manager call.
- `request_id`: UUID4 format not strictly enforced (any non-empty string accepted for
  idempotency) — avoids rejecting valid messages on UUID format.

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `try/finally` missing in WS handler | Permanent ghost session | Non-negotiable; covered by QA test E01 |
| Registry double-create race | Duplicate manager; chip state divergence | asyncio.Lock wraps check+insert atomically |
| Broadcaster iterates while dict mutated | RuntimeError crash | `async with self._lock:` + copy list, then iterate outside lock |
| `WebSocketState.CONNECTED` check before send | Avoids send-after-close errors | Check `ws.client_state` in `_safe_send` |
| SQLite adapter instantiated in production before implemented | Runtime crash | `SqlitePersistenceAdapter` must pass `isinstance` check; method stubs raise `NotImplementedError` with clear message |

---

## Implementation Notes

- `backend/main.py` uses `@asynccontextmanager lifespan=` (not deprecated `@app.on_event`).
- Singletons are attached to `app.state` in lifespan startup:
  `persistence`, `broadcaster`, `registry`, `auth_service`.
- HTTP routers read singletons via `request.app.state` (no FastAPI `Depends` needed for
  state-based injection; use `Depends` only for per-request concerns like `get_current_user`).
- WS router reads singletons from `websocket.app.state` directly (same pattern).
- `ClubService` and `TableService` Protocols are not instantiated as separate objects
  for this feature. Router handlers call `persistence` directly. If the logic grows
  complex, extracting to service objects is a future refactor.
- For integration tests, use `from fastapi.testclient import TestClient` with
  `app.dependency_overrides` to inject a `TestAuthService` that accepts a fixed OTP.

---

## Technical Sign-off

- [x] Architectural review complete — no blocking violations
- [x] Two non-blocking observations scheduled for cleanup in this feature
- [x] UX contract requirements implemented (reserve_until, health state_persistence, error request_id echo)
- [x] PM approved — scope matches feature-spec.md
- Date: 2026-03-19
- Notes: Technical Gate passed. QA review and task breakdown may proceed.
