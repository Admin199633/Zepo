# Feature Spec — backend-application-wiring

> Owner: Product Manager
> Gate: Product Gate (Gate 1)
> Status: APPROVED
> Predecessor: backend-app-bootstrap (design artifacts approved 2026-03-19)

---

## Context

The `backend-app-bootstrap` feature produced approved design artifacts for wiring the
backend. This feature executes that design. It also extends it with two requirements
that were out of scope for the design phase:
1. A formal architectural review before any code is written.
2. A production persistence adapter scaffold alongside the in-memory adapter.

No new gameplay or UI features are introduced.

---

## Feature Goal

Deliver a deployable, testable FastAPI backend application that runs the poker engine
and session manager behind a real HTTP and WebSocket transport layer — with a clear
path toward production persistence.

---

## User Story

As the development team, we need a running server that accepts real connections so that:
- Mobile client development can begin against a stable local API.
- Integration tests verify the full request path from HTTP/WS to engine and back.
- The production persistence upgrade path (SQLite → Postgres) is scaffolded and ready to
  fill in without disrupting the running application.

---

## In Scope

### Architectural Review
- Formal audit of boundary compliance across all existing backend modules.
- Findings documented in `technical-design.md` before any code change.
- Any violation found during the review must be fixed as part of this feature before
  other implementation tasks begin.

### Application Bootstrap
- `backend/main.py` — FastAPI app factory with `@asynccontextmanager lifespan`.
- `backend/dependencies.py` — Singleton factories via `app.state`; `get_current_user`
  extracts and validates the Bearer JWT.
- `backend/session_registry.py` — `TableSessionRegistry`: asyncio-safe map of
  `table_id → TableSessionManager`, created on demand.

### Transport Layer
- `backend/realtime/ws_broadcaster.py` — `WebSocketBroadcaster` implementing
  `BroadcastService`. Holds live WebSocket connections keyed by `(table_id, user_id)`.
  Send failures caught and logged — never raised.
- `backend/realtime/ws_router.py` — `WS /ws/table/{table_id}?token=<jwt>`. Token
  validated before upgrade accepted. Explicit `JOIN_TABLE` message required to seat or
  spectate. Full `try/finally` guarantees `disconnect()` on any exit path.
- `backend/api/auth_router.py` — `POST /auth/request-otp`, `POST /auth/verify-otp`.
- `backend/api/clubs_router.py` — `POST /clubs`, `GET /clubs/{id}`,
  `POST /clubs/{id}/join`.
- `backend/api/tables_router.py` — `GET /clubs/{id}/table`,
  `PATCH /clubs/{id}/table/config`.
- `backend/api/health_router.py` — `GET /health`.
- Schema addition: `reserve_until: Optional[float]` on `PlayerStatusPayload`.

### Persistence Scaffold
- `backend/persistence/sqlite_adapter.py` — `SqlitePersistenceAdapter` class that
  implements `PersistenceAdapter` ABC. Defines the SQLAlchemy Core table schema for all
  entities. All methods implemented as structural stubs (raise `NotImplementedError` with
  inline comments describing the production implementation pattern). Purpose: establishes
  the production DB schema and adapter interface, ready to be filled in.

### Configuration and Integration Tests
- `.env.example` — documents every variable in `backend/config.py`.
- `requirements-backend.txt` updated: add `fastapi[standard]`, `uvicorn[standard]`,
  `httpx`, `aiosqlite`, `sqlalchemy`.
- `tests/test_app_integration.py` — end-to-end tests covering HTTP routes and the
  WebSocket gate using FastAPI `TestClient`.

---

## Out of Scope

- Production SQLite or Postgres execution (adapter is scaffold only — methods stubbed).
- Redis broadcaster (in-process `WebSocketBroadcaster` only).
- Real SMS provider (Twilio) — `ConsoleAuthService` for MVP.
- Admin member management endpoints (ban, promote, remove).
- Push notifications, rate limiting, analytics persistence backend.
- Mobile client, mobile UI screens.
- New game rules or engine changes of any kind.
- Token refresh endpoint.
- Horizontal scaling (requires Redis broadcaster — deferred).

---

## Acceptance Criteria

1. `uvicorn backend.main:app --reload` starts without errors on a clean environment.
2. Architectural review produces no unfixed boundary violations.
3. `GET /health` returns `200 {"status": "ok"}`.
4. `POST /auth/request-otp` → `200`. `POST /auth/verify-otp` with correct OTP → `200` token. Wrong OTP → `400`.
5. Authenticated user creates a club via `POST /clubs` and receives `club_id` and `table_id`.
6. `WS /ws/table/{table_id}?token=<valid>` connects, client receives `STATE_SNAPSHOT` after `JOIN_TABLE`.
7. `WS /ws/table/{table_id}?token=<invalid>` is rejected with close code `4001`.
8. Two authenticated WS clients join the same table; both receive `PLAYER_JOINED` for each other.
9. Two seated players trigger automatic hand start; both receive `PHASE_CHANGED`, private `CARDS_DEALT`, `BLINDS_POSTED`, `TURN_CHANGED`.
10. Player sends `ACTION`; all table clients receive `PLAYER_ACTED`.
11. WS close triggers `session_manager.disconnect()`; `PLAYER_STATUS "disconnected"` broadcast includes `reserve_until`.
12. Player reconnects within 60 s; receives fresh `STATE_SNAPSHOT` and hand continues.
13. `SqlitePersistenceAdapter` class exists, passes `isinstance(adapter, PersistenceAdapter)` check, and raises `NotImplementedError` on every method call.
14. All existing `poker_engine/tests/` and `tests/` tests continue to pass without modification.
15. `tests/test_app_integration.py` contains at least 10 passing tests.

---

## Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Architectural violation found during review | High | Must fix before implementation proceeds |
| WS `try/finally` missing → ghost sessions | High | Non-negotiable; verified by integration test |
| Registry race condition on concurrent first-connect | Medium | asyncio.Lock wraps full check-and-create |
| Stale WS handle during broadcast iteration | Medium | Copy connections list before iterating |
| In-memory state lost on server restart | Low | Documented limitation; SqliteAdapter is the path forward |

---

## Dependencies

| Dependency | Status |
|-----------|--------|
| `poker_engine` | Complete — must not change |
| `backend/sessions/session_manager.py` | Complete — must not change |
| `backend/persistence/memory.py` | Complete |
| `backend/persistence/adapter.py` | Complete |
| `backend/realtime/schemas.py` | Requires additive change: `reserve_until` field |
| `backend-app-bootstrap` design artifacts | Approved 2026-03-19 — inputs for this feature |
| `fastapi[standard]`, `uvicorn[standard]`, `httpx`, `aiosqlite`, `sqlalchemy` | Add to requirements |

---

## Open Questions

| # | Question | Resolution |
|---|----------|------------|
| Q1 | Should `club_name` and `admin_id` be included in `STATE_SNAPSHOT` without modifying `session_manager`? | **Resolved: deferred.** Session_manager cannot be modified per architectural constraints. These fields will be added when session_manager is extended in a future feature (`session-manager-extension`). Client should fetch `/clubs/{id}` for this context if needed. |
| Q2 | Should `SqlitePersistenceAdapter` use SQLAlchemy ORM or Core? | **Resolved: SQLAlchemy Core with `aiosqlite`.** ORM adds complexity without benefit for a well-defined schema. Core + raw tables is simpler and maps directly to the existing dataclass models. |
| Q3 | Should the WS endpoint send STATE_SNAPSHOT immediately on connect (before JOIN_TABLE) or only after JOIN_TABLE? | **Resolved: after JOIN_TABLE.** Session_manager already sends STATE_SNAPSHOT on join. A pre-join snapshot would require bypassing session_manager, violating the orchestration boundary. Client should send JOIN_TABLE immediately after connecting. |
