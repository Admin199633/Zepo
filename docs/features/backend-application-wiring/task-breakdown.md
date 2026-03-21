# Task Breakdown — backend-application-wiring

> Owner: Senior Mobile Game Developer
> Input: technical-design.md, qa-test-plan.md
> Gate: Implementation Gate (Gate 4)
> Status: APPROVED — ready for implementation

---

## Milestones

| # | Milestone | Deliverable |
|---|-----------|------------|
| M0 | Cleanup + review | Dead import removed; inline imports moved; chat task error callback added |
| M1 | Infrastructure | `WebSocketBroadcaster`, `TableSessionRegistry`, `dependencies.py`, schema addition |
| M2 | HTTP layer | All HTTP routers + `main.py` + `.env.example`; `uvicorn backend.main:app` starts |
| M3 | WebSocket layer | WS gateway running; two clients can join, act, disconnect |
| M4 | Persistence scaffold | `SqlitePersistenceAdapter` skeleton with DB schema defined |
| M5 | Integration tests | All 14 integration tests pass; all existing tests pass |

---

## Tasks

| ID | Task | Milestone | Depends On | Size |
|----|------|-----------|-----------|------|
| A1 | **Cleanup: `backend/persistence/adapter.py`** — remove dead `GameState` import. Verify no callers use it. | M0 | — | XS |
| A2 | **Cleanup: `backend/sessions/session_manager.py`** — (a) move inline imports at line 628–633 to module top level; (b) add `.add_done_callback` for the fire-and-forget chat task to log exceptions. | M0 | — | XS |
| T1 | **`backend/realtime/schemas.py`** — add `reserve_until: Optional[float] = None` to `PlayerStatusPayload`. Verify no existing tests break. | M1 | M0 | XS |
| T2 | **`backend/realtime/ws_broadcaster.py`** — `WebSocketBroadcaster` implementing `BroadcastService`. Connection dict keyed `dict[table_id, dict[user_id, ConnectionRecord]]`. asyncio.Lock. `register`, `update_role`, `unregister`, `send_to_player`, `broadcast_to_table`, `broadcast_to_spectators`, `_safe_send`. Copy list before iteration in all broadcast methods. Catch all send exceptions in `_safe_send`. | M1 | — | M |
| T3 | **`backend/session_registry.py`** — `TableSessionRegistry`. asyncio.Lock wraps full check-and-insert in `get_or_create`. `get`, `remove`, `active_count` property. | M1 | — | S |
| T4 | **`backend/dependencies.py`** — singleton factories reading from `app.state`: `get_persistence`, `get_broadcaster`, `get_registry`, `get_auth_service`. `get_current_user` Depends: extracts `Authorization: Bearer <token>`, calls `auth_service.verify_token`, raises `HTTPException(401)` on failure. `http_error` helper: returns `{"error": CODE, "message": MSG}`. | M1 | T2, T3 | S |
| T5 | **`backend/api/health_router.py`** — `GET /health`. Reads `app.state.registry.active_count`. Returns `HealthResponse` with `state_persistence` = `"in_memory_volatile"` when `settings.app_env != "production"`. No auth required. | M2 | T4 | XS |
| T6 | **`backend/api/auth_router.py`** — `POST /auth/request-otp` (validate E.164 format, call `auth_service.request_otp`), `POST /auth/verify-otp` (call `auth_service.verify_otp`, return `TokenResponse`). Catch `ValueError` → 400. Use `http_error` helper for all errors. | M2 | T4 | S |
| T7 | **`backend/api/clubs_router.py`** — `POST /clubs`: create `Club` + `TableRecord` via persistence, return `CreateClubResponse`. `GET /clubs/{id}`: check membership → 403 if not member. `POST /clubs/{id}/join`: validate invite code via `get_club_by_invite`, add membership, return `{club_id, table_id}`. All endpoints require `get_current_user`. | M2 | T4 | M |
| T8 | **`backend/api/tables_router.py`** — `GET /clubs/{id}/table`: member check, return `TableRecord` + `get_hand_history(limit=20)`. `PATCH /clubs/{id}/table/config`: admin check via `club.is_admin(actor_id)`, apply partial config update, `save_table`. Return updated config. | M2 | T4 | S |
| T9 | **`backend/main.py`** — `create_app() -> FastAPI`. `@asynccontextmanager lifespan`: create `InMemoryPersistenceAdapter`, `WebSocketBroadcaster`, `TableSessionRegistry`, `ConsoleAuthService`; attach to `app.state`; yield. Mount routers: `/health`, `/auth`, `/clubs`, `/clubs` (tables), `/ws`. CORS middleware (all origins for dev). `app = create_app()` module-level. | M2 | T5–T8 | S |
| T10 | **`.env.example`** — document every variable in `backend/config.py` with safe dev default and a one-line production note. | M2 | T9 | XS |
| T11 | **`requirements-backend.txt`** — add: `fastapi[standard]>=0.110`, `uvicorn[standard]>=0.29`, `httpx>=0.27`, `aiosqlite>=0.20`, `sqlalchemy>=2.0`. | M2 | — | XS |
| T12 | **`backend/realtime/ws_router.py`** — `APIRouter` with `@router.websocket("/ws/table/{table_id}")`. Full flow per technical-design.md event flow section. `try/finally` guarantees `unregister + disconnect`. `_dispatch_message` with `match` on `ClientMessageType`. `_send_error` helper sends `ERROR` envelope with `request_id` echo. Handle all 7 client message types. | M3 | T9, T2, T3 | L |
| T13 | **`backend/persistence/sqlite_adapter.py`** — `SqlitePersistenceAdapter(PersistenceAdapter)`. `__init__(database_url)`. Define all 9 SQLAlchemy Core `Table` objects as module-level constants. All 18 abstract methods implemented with `raise NotImplementedError("TODO: production implementation — see inline comment")` and a one-line SQL pattern comment per method. | M4 | — | M |
| T14 | **`tests/test_app_integration.py`** — 14 integration tests per qa-test-plan.md. Use `TestClient(create_app())`. Dependency-override `get_auth_service` with `TestAuthService` (deterministic OTP). Pre-seed `InMemoryPersistenceAdapter` with a `TableRecord` for WS tests. Async WS tests via `client.websocket_connect(...)` context manager. | M5 | T9, T12 | L |

Size: XS < 20 min, S ≈ 45 min, M ≈ 90 min, L ≈ 3h

---

## Build Order

```
M0: A1, A2 (parallel)
M1: T1 (parallel with T2, T3) → T4
M2: T5, T6, T7, T8 (parallel after T4) → T9 → T10, T11 (parallel)
M3: T12 (after T9)
M4: T13 (independent, after M1)
M5: T14 (after T9, T12)
```

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| `fastapi[standard]` | Package | Add to requirements |
| `uvicorn[standard]` | Package | Add to requirements |
| `httpx` | Package | Test client — add to requirements |
| `aiosqlite` | Package | Required by sqlite_adapter scaffold |
| `sqlalchemy>=2.0` | Package | SQLAlchemy Core for schema definitions |
| `backend/sessions/session_manager.py` | Internal | Cleanup only (A2); public API unchanged |
| `backend/realtime/schemas.py` | Internal | Additive change only (T1) |

---

## What Must Not Change During Implementation

1. `poker_engine/` — zero changes permitted.
2. `backend/sessions/session_manager.py` public API — only internal cleanups (A2).
3. `backend/persistence/adapter.py` abstract interface — only dead import removal (A1).
4. `backend/persistence/memory.py` — no changes.
5. `backend/realtime/schemas.py` — additive only (T1); no existing field removed or renamed.
6. All existing test files — no modifications; only additions.

---

## Definition of Done

- [ ] Tasks A1, A2, T1–T14 all complete
- [ ] `uvicorn backend.main:app --reload` starts without errors
- [ ] All 14 integration tests in `test_app_integration.py` pass
- [ ] All existing tests in `poker_engine/tests/` and `tests/` pass
- [ ] Architecture boundary checks A01–A05 all confirmed
- [ ] `signoff.md` complete with all approvals

---

## Developer Notes

- `ConsoleAuthService` stub's `verify_token` method uses `"dev_<user_id>"` format,
  not a real JWT. Do not change this; rely on it for integration test tokens.
- For integration tests, a `TestAuthService` should store OTPs in a dict and
  accept them on verify — identical to `ConsoleAuthService` but injectable via
  `app.dependency_overrides[get_auth_service]`.
- `TableRecord` for WS tests must be pre-created in persistence at app startup or
  in test fixture setup. The WS endpoint calls `persistence.get_table(table_id)` — if
  the table doesn't exist, it closes 4004.
- The `_dispatch_message` function must not raise. All exceptions must be caught
  and converted to ERROR events.
