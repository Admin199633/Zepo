# Feature Spec — simulation-harness

> Agent: Product Manager
> Gate: Feature Spec (Gate 1)
> Status: APPROVED

---

## Feature Goal

Build a backend-only simulation harness that drives the real FastAPI application through realistic multi-client poker scenarios without a mobile client. The harness exists purely as a test and validation tool; it adds no gameplay features and makes no changes to business logic.

---

## Background

The application layer (`backend/main.py`, `ws_router.py`, `session_manager.py`) is now fully wired and tested at the unit and integration level. What is missing is scenario-level validation: multi-player sequences where clients take turns, events arrive in defined order, and edge-case behaviors (reconnect, timeout, mid-hand join, spectator filtering) are exercised in a coherent story from start to finish.

---

## Scope

**In scope:**
- A `SimulatedClient` abstraction that wraps HTTP + WebSocket interactions against a live TestClient backend
- Auth helpers (OTP flow, token storage)
- HTTP helpers (create club, join club, get table config)
- WebSocket helpers (connect, send JOIN_TABLE, send ACTION, collect events)
- An event capture mechanism (per-client message log with type filtering)
- A `ScenarioRunner` that composes multiple `SimulatedClient` instances and drives scenario steps
- Six end-to-end simulation scenarios (see Minimum Scenarios below)
- Configurable delay overrides (between-hands, turn-timer) so scenarios run fast in CI

**Out of scope:**
- Load testing / sustained concurrency (this is not a load harness)
- Mobile client code
- New gameplay features
- Changes to poker rules
- Modifications to `poker_engine/`
- New HTTP API routes
- UI components of any kind
- Distributed or cross-process simulation

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC-01 | `SimulatedClient` can complete a full OTP auth flow and obtain a dev token |
| AC-02 | `SimulatedClient` can create a club and receive `club_id`, `table_id`, `invite_code` |
| AC-03 | A second `SimulatedClient` can join an existing club via invite code |
| AC-04 | `SimulatedClient` can open a WebSocket to `/ws/table/{table_id}?token=` and send `JOIN_TABLE` |
| AC-05 | `SimulatedClient` event log captures all received server envelopes for later assertion |
| AC-06 | `drain_until(type)` blocks until the target event type is received or fails with a clear error |
| AC-07 | Two-player scenario: both players join and complete at least one full hand (HAND_RESULT received by both) |
| AC-08 | Mid-hand join scenario: a third player who joins mid-hand receives a STATE_SNAPSHOT and waits until next hand before being dealt cards |
| AC-09 | Spectator scenario: a spectator receives all broadcast events and never receives `CARDS_DEALT` |
| AC-10 | Reconnect scenario: a player disconnects (WS context exits) and reconnects within 60 s; receives STATE_SNAPSHOT confirming seat held |
| AC-11 | Full-table scenario: an 11th player attempting to join receives a `TABLE_FULL` error |
| AC-12 | Timeout scenario: when a player does not act within the turn timer, the engine auto-acts and `PLAYER_ACTED` is broadcast |
| AC-13 | All six scenarios run in under 30 seconds total in CI (achieved via delay overrides) |
| AC-14 | Harness does not modify any file under `poker_engine/`, `backend/`, or existing `tests/` |
| AC-15 | Harness entry point is `simulation/` package; importable without circular dependencies |

---

## Minimum Scenarios Required

| # | Scenario |
|---|----------|
| S1 | **Two-player hand** — two players connect, join, complete at least one hand |
| S2 | **Mid-hand join** — third player joins while hand is in progress; waits; receives cards next hand |
| S3 | **Spectator filtering** — spectator connects; never receives `CARDS_DEALT`; receives all other broadcast events |
| S4 | **Reconnect** — disconnected player reconnects within 60 s; seat is held; receives STATE_SNAPSHOT |
| S5 | **Full-table rejection** — 11th player attempt returns `TABLE_FULL` error |
| S6 | **Timeout auto-action** — player does not act within turn timer; engine auto-acts; `PLAYER_ACTED` emitted |

---

## Dependencies

| Dependency | Status |
|-----------|--------|
| `backend/main.py` `create_app()` | ✅ Available |
| `backend/auth/service.py` `ConsoleAuthService` | ✅ Available |
| `backend/realtime/schemas.py` `ClientEnvelope`, `ServerEnvelope` | ✅ Available |
| `fastapi.testclient.TestClient` | ✅ Available |
| `tests/test_app_integration.py` `_TestAuthService` pattern | ✅ Available (reuse pattern) |

---

## Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Between-hands delay (default 3.0 s) makes CI slow | High | Must be overridable per test app instance |
| Turn timer (default 30 s) makes timeout scenario slow | High | Must be overridable to a short value (≤2 s) |
| Synchronous TestClient with nested WS contexts | Medium | Tested pattern in integration tests; viable for sequential event collection |
| Event ordering nondeterminism from asyncio scheduling | Medium | Mitigated by `drain_until` with tolerance window |
| Spectator hidden-card assertion relies on absence of CARDS_DEALT | Low | Must assert on collected log, not just first message |

---

## Open Questions

| # | Question | Resolution |
|---|----------|------------|
| Q1 | How to override `BETWEEN_HANDS_DELAY` per test? | Patch the constant in `session_manager.py` at test setup via monkeypatch; document in technical-design |
| Q2 | Should simulated clients use `anyio` async or sync TestClient? | Sync TestClient — consistent with existing integration test pattern; avoids event loop management overhead |
| Q3 | Where does the `simulation/` package live? | Top-level `simulation/` directory (sibling of `backend/`, `tests/`); not nested under `tests/` to keep scenario code reusable |
| Q4 | How many hands needed for multi-hand progression scenario? | Two hands minimum — sufficient to verify hand-counter increments and seat continuity |
