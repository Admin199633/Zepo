# Task Breakdown — backend-app-bootstrap

> Owner: Senior Mobile Game Developer
> Input: technical-design.md, qa-test-plan.md
> Gate: Implementation Gate (Gate 4)
> Status: APPROVED — ready for implementation

---

## Milestones

| # | Milestone | Deliverable |
|---|-----------|------------|
| M1 | Infrastructure | `WebSocketBroadcaster`, `TableSessionRegistry`, and dependency injection wired; no HTTP/WS yet |
| M2 | HTTP layer | All HTTP routes running; `uvicorn backend.main:app` starts; auth and clubs work over HTTP |
| M3 | WebSocket layer | WS endpoint running; two clients can join, exchange events, disconnect/reconnect |
| M4 | Validated | All QA scenarios T01–T28 pass; regression clean |

---

## Tasks

| ID | Task | Milestone | Depends On | Estimate | Status |
|----|------|-----------|-----------|----------|--------|
| T1 | Create `backend/realtime/ws_broadcaster.py` — `WebSocketBroadcaster` implementing `BroadcastService` Protocol. Holds `dict[table_id, dict[user_id, ConnectionRecord]]` with `asyncio.Lock`. Send failures caught and logged. Copy connection list before iterating. | M1 | — | S | Todo |
| T2 | Create `backend/session_registry.py` — `TableSessionRegistry` with `asyncio.Lock`. `get_or_create()` checks inside lock; creates `TableSessionManager` only if not present. `get()` and `remove()` methods. | M1 | — | S | Todo |
| T3 | Create `backend/dependencies.py` — FastAPI `Depends` factories. Singletons: `get_persistence()` → `InMemoryPersistenceAdapter`, `get_broadcaster()` → `WebSocketBroadcaster`, `get_registry()` → `TableSessionRegistry`, `get_auth_service()` → `ConsoleAuthService`. `get_current_user()` extracts Bearer token from header and calls `auth_service.verify_token()`. | M1 | T1, T2 | S | Todo |
| T4 | Create `backend/api/health_router.py` — `GET /health`. Returns `{"status": "ok", "app_env": settings.app_env, "active_tables": registry.active_count(), "version": "0.1.0"}`. No auth required. | M2 | T2 | XS | Todo |
| T5 | Create `backend/api/auth_router.py` — `POST /auth/request-otp` and `POST /auth/verify-otp`. Use `get_auth_service()` depend. Consistent error format `{"error": "...", "message": "..."}` on all 4xx. | M2 | T3 | S | Todo |
| T6 | Create `backend/api/clubs_router.py` — `POST /clubs`, `GET /clubs/{id}`, `POST /clubs/{id}/join`. `POST /clubs` creates club + table record via persistence, returns `club_id`, `table_id`, `invite_code`. Membership check on GET. | M2 | T3 | M | Todo |
| T7 | Create `backend/api/tables_router.py` — `GET /clubs/{id}/table` (member only) and `PATCH /clubs/{id}/table/config` (admin only). Config PATCH validates actor_id == admin_id. Returns updated TableRecord. | M2 | T3 | S | Todo |
| T8 | Create `backend/main.py` — FastAPI app factory with `@asynccontextmanager lifespan`. Mount all routers with prefixes. Create singletons in lifespan startup and attach to `app.state`. Include CORS middleware for dev. | M2 | T4, T5, T6, T7 | S | Todo |
| T9 | Create `backend/realtime/ws_router.py` — `WS /ws/table/{table_id}`. Validate token from query param (reject 4001 on failure). Look up table in registry (reject 4004 if missing). `broadcaster.register()`. Send STATE_SNAPSHOT. Async `iter_text()` dispatch loop with `try/finally` guaranteeing `broadcaster.unregister()` and `session_manager.disconnect()`. Dispatch: JOIN_TABLE, ACTION, CHAT, SIT_OUT, SIT_IN, LEAVE_TABLE, SYNC_REQUEST. Catch JSON errors → ERROR event. Catch Pydantic errors → ERROR event. Catch ValueError from engine → ERROR event. | M3 | T1, T2, T3, T8 | L | Todo |
| T10 | Update `PlayerStatusPayload` schema in `backend/realtime/schemas.py` — add optional `reserve_until: float | None`. Update `STATE_SNAPSHOT` structure to include `club_name` and `admin_id`. Ensure `build_player_view` and `build_spectator_view` wrappers in WS router include these fields. | M3 | T9 | S | Todo |
| T11 | Create `.env.example` — document every variable in `backend/config.py` with safe dev defaults and a comment for each production requirement. | M2 | T8 | XS | Todo |
| T12 | Write integration tests in `tests/test_ws_integration.py` using `httpx.AsyncClient` + `websockets` or FastAPI `TestClient`. Cover: WS connect → STATE_SNAPSHOT, JOIN_TABLE → PLAYER_JOINED, two players → hand starts, ACTION → PLAYER_ACTED, disconnect → PLAYER_STATUS disconnected, reconnect → STATE_SNAPSHOT. | M4 | T9, T10 | L | Todo |

Size key: XS < 30 min, S = ~1h, M = ~2h, L = ~3–4h

---

## Dependencies

| Dependency | Type | Owner | Status |
|-----------|------|-------|--------|
| `fastapi[standard]` in requirements-backend.txt | Package | Dev | Add |
| `uvicorn[standard]` in requirements-backend.txt | Package | Dev | Add |
| `pyjwt` in requirements-backend.txt | Package | Dev | Add (for future real JWT; ConsoleAuthService doesn't need it for MVP) |
| `httpx` in requirements-backend.txt (test only) | Package | Dev | Add |
| `poker_engine` | Internal | Engine (complete) | No changes |
| `backend/sessions/session_manager.py` | Internal | Dev (complete) | No changes |
| `backend/persistence/memory.py` | Internal | Dev (complete) | No changes |
| `backend/realtime/schemas.py` | Internal | Dev (complete) | T10 adds two optional fields only |

---

## Definition of Done

This feature is done when:

- [ ] All tasks T1–T12 are complete
- [ ] `uvicorn backend.main:app --reload` starts with no errors
- [ ] All test scenarios T01–T28 in `qa-test-plan.md` pass
- [ ] All existing tests in `poker_engine/tests/` and `tests/` pass with no modifications
- [ ] Deck data is confirmed absent from all HTTP and WS responses
- [ ] `signoff.md` is complete with all approvals

---

## Developer Notes

- **Task ordering:** T1 and T2 are independent and can be built in parallel. T3 depends
  on both. T4–T7 depend on T3 and can be parallelized. T8 depends on T4–T7. T9 depends
  on T8. T10 is a small modification alongside T9. T12 must be last.

- **Do not modify `session_manager.py`.** All integration happens through its existing
  public API. If something appears missing, raise it as a separate feature request.

- **The WS handler `try/finally` is the most critical correctness requirement.** See
  QA Risk Note #1. Test this explicitly in T12 by killing the WS mid-hand and verifying
  `disconnect()` was called.

- **T10 adds two optional fields to existing schemas.** These are backwards-compatible
  additions. No existing tests should break.
