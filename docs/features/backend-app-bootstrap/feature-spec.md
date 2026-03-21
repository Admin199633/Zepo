# Feature Spec — backend-app-bootstrap

> Owner: Product Manager
> Gate: Product Gate (Gate 1)
> Status: APPROVED

---

## Feature Goal

Wire all existing backend service modules into a single deployable FastAPI application.
The application must accept real HTTP connections (auth, clubs, tables) and real WebSocket
connections (table realtime channel). No new game logic is introduced — this feature is
purely the integration layer between the transport and the already-implemented engine and
session manager.

---

## User Story

As a mobile client developer, I need a running backend server with documented HTTP endpoints
for user auth and club management, and a WebSocket endpoint for real-time table events,
so that I can build and test the mobile app against a real server.

---

## In Scope

### HTTP Routes
| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/request-otp | Send OTP to phone number |
| POST | /auth/verify-otp | Verify OTP, return JWT token |
| POST | /clubs | Create a new club (authenticated) |
| GET | /clubs/{club_id} | Get club details |
| POST | /clubs/{club_id}/join | Join club by invite code |
| GET | /clubs/{club_id}/table | Get active table config and recent hand history |
| PATCH | /clubs/{club_id}/table/config | Update table config (club admin only) |
| GET | /health | Health check (unauthenticated) |

### WebSocket
- `WS /ws/table/{table_id}?token=<jwt>` — realtime table channel
- Token validated on connect; connection rejected if invalid
- All incoming messages are `ClientEnvelope` JSON
- All outgoing messages are `ServerEnvelope` JSON
- Supported message types: JOIN_TABLE, ACTION, CHAT, SIT_OUT, SIT_IN, LEAVE_TABLE, SYNC_REQUEST

### Application Infrastructure
- FastAPI app factory (`backend/main.py`)
- Dependency injection via FastAPI `Depends` (`backend/dependencies.py`)
- `TableSessionRegistry` — singleton map of `table_id → TableSessionManager`, created on demand
- `WebSocketBroadcaster` — concrete `BroadcastService` implementation backed by live WebSocket connections
- Lifespan context manager for startup/shutdown
- `.env.example` with all required variables documented

---

## Out of Scope

- Production database (SQLAlchemy / SQLite / Postgres) — `InMemoryPersistenceAdapter` used for MVP
- Redis broadcaster — in-process `WebSocketBroadcaster` only for MVP
- Real SMS provider (Twilio) — `ConsoleAuthService` (prints OTP to stdout) for MVP
- Admin management endpoints (ban, kick, transfer admin)
- Push notification delivery
- Rate limiting and abuse protection
- Analytics persistence backend
- Pagination on hand history
- Token refresh endpoint

---

## Acceptance Criteria

1. `uvicorn backend.main:app --reload` starts with no import errors on a clean environment.
2. `POST /auth/request-otp` with a valid E.164 phone number returns HTTP 200.
3. `POST /auth/verify-otp` with the correct OTP returns a JWT token and user_id.
4. `POST /auth/verify-otp` with an incorrect OTP returns HTTP 400 with an error message.
5. An authenticated user can create a club via `POST /clubs` and receive a `club_id`.
6. `WS /ws/table/{table_id}?token=<valid_jwt>` connects and the client receives a `STATE_SNAPSHOT` within 1 second.
7. `WS /ws/table/{table_id}?token=<invalid_jwt>` is rejected with close code 4001.
8. Two authenticated WebSocket clients who join the same table both receive `PLAYER_JOINED` for each other.
9. When two players are seated, a hand starts automatically and both receive `PHASE_CHANGED`, `CARDS_DEALT` (private), `BLINDS_POSTED`, and `TURN_CHANGED`.
10. A player action (ACTION message) routes correctly to `TableSessionManager` and all clients receive `PLAYER_ACTED`.
11. Closing a WebSocket triggers `session_manager.disconnect()` and a 60-second sit-out timer.
12. A player who reconnects within 60 seconds receives a fresh `STATE_SNAPSHOT` and the hand continues.
13. `GET /health` returns HTTP 200 with `{"status": "ok"}`.
14. All existing `poker_engine` and `backend` unit tests pass without modification.

---

## Risks

| Risk | Severity | Notes |
|------|----------|-------|
| WebSocketBroadcaster must handle stale connections without crashing | High | Catch OSError/WebSocketDisconnect on send; log and continue |
| TableSessionRegistry race condition on concurrent first-connect | Medium | Use asyncio.Lock on registry mutation |
| In-memory state lost on server restart | Low | Expected for MVP; must be documented |
| Token validation on WS upgrade is non-standard in FastAPI | Low | Use query param `?token=` pattern |

---

## Dependencies

- `poker_engine` — complete, no changes required
- `backend/sessions/session_manager.py` — complete, no changes required
- `backend/persistence/memory.py` — complete
- `backend/realtime/schemas.py` — complete
- `fastapi[standard]`, `uvicorn[standard]` — must be in requirements
- `python-jose` or `pyjwt` — for JWT encode/decode in production auth path

---

## Open Questions

| # | Question | Resolution |
|---|----------|------------|
| Q1 | WS join flow: should the client send an explicit JOIN_TABLE message, or does connecting to /ws/table/{table_id} auto-join? | **Resolved: explicit JOIN_TABLE message required.** Connection alone does not join. Client must send JOIN_TABLE with role ("player" or "spectator") after connecting. This allows spectators and players to share the same WS endpoint. |
| Q2 | Should a club table be created automatically when the club is created, or separately? | **Resolved: automatic.** One table per club. Table created with default config at club creation time. Club admin can update config via PATCH. |
| Q3 | Should the server keep a WS connection alive if the player leaves the table voluntarily (for chat or spectator purposes)? | **Deferred to `spectator-mode` feature.** For MVP: LEAVE_TABLE closes the server-side session but not the WS. Client can reconnect or send JOIN_TABLE again as spectator. |
