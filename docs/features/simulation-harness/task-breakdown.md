# Task Breakdown — simulation-harness

> Status: APPROVED FOR IMPLEMENTATION

---

## Milestone Sequence

```
M0 → M1 → M2 → M3
```

| Milestone | Description |
|-----------|-------------|
| M0 | Package scaffolding — create `simulation/` directory, `__init__.py`, `scenarios/__init__.py` |
| M1 | Core infrastructure — `event_log.py`, `client.py`, `app_factory.py`, `helpers.py`, `runner.py` |
| M2 | Six scenario modules (`scenarios/s1_*.py` through `s6_*.py`) |
| M3 | Pytest entry point (`tests/test_simulation_scenarios.py`) + full pass |

---

## Tasks

### M0 — Package Scaffolding

**T0** — Create directory structure
- `simulation/__init__.py` — exports `SimulatedClient`, `ScenarioRunner`
- `simulation/scenarios/__init__.py` — empty

No logic. Just directory and empty init files.

---

### M1 — Core Infrastructure

**T1** — `simulation/event_log.py`
- `CapturedEvent` dataclass: `type`, `payload`, `seq`, `ts`
- `EventLog`: `append(raw)`, `all()`, `of_type(t)`, `has_type(t)`, `clear()`

**T2** — `simulation/app_factory.py`
- `make_test_client(between_hands_delay=0.05) -> TestClient`
- Patches `backend.sessions.session_manager.BETWEEN_HANDS_DELAY`
- Calls `create_app()`, enters `TestClient` lifespan context, injects `_TestAuthService`
- Returns the live `TestClient`

**T3** — `simulation/client.py`
- `SimulatedClient.__init__(http, phone, display_name)`
- `authenticate()` — OTP flow, stores `token`, `user_id`
- HTTP helpers: `create_club()`, `join_club()`, `get_club()`, `patch_table_config()`
- `auth_headers()` utility
- WS: `connect(table_id)` context manager, `send()`, `send_join()`, `send_action()`
- Event reception: `recv_one()`, `drain_until(type, max_msgs=30)`, `drain_n(n)`

**T4** — `simulation/helpers.py`
- `make_client(http, phone, name) -> SimulatedClient` — authenticates on creation
- `setup_two_players(http) -> (owner, joiner, club_id, table_id)`
- `both_join_as_players(owner, joiner, table_id)` — sends JOIN_TABLE + drains STATE_SNAPSHOT for both

**T5** — `simulation/runner.py`
- `ScenarioResult` dataclass: `name`, `passed`, `error`
- `ScenarioRunner(http)`: `run(name, fn)`, `assert_all_passed()`

---

### M2 — Scenario Modules

Each scenario is a module with a single public function `def run(http: TestClient) -> None`.

**T6** — `simulation/scenarios/s1_two_player_hand.py`
- Setup two players via `setup_two_players` + `both_join_as_players`
- Drain `BLINDS_POSTED` on both clients
- Drive hand to completion using `drain_until("TURN_CHANGED")` + action dispatch
- Assert both receive `HAND_RESULT`; `pot_total > 0`; no ERROR events in either log

**T7** — `simulation/scenarios/s2_mid_hand_join.py`
- Start S1 setup, wait for `BLINDS_POSTED` (hand in progress)
- Third client joins club and opens WS with `JOIN_TABLE role=player` mid-hand
- Assert third client gets `STATE_SNAPSHOT`
- Drive first hand to `HAND_RESULT`; assert third client is NOT in `CARDS_DEALT` for first hand
- Wait for second hand's `BLINDS_POSTED`; assert third client receives `CARDS_DEALT`

**T8** — `simulation/scenarios/s3_spectator_filtering.py`
- Start S1 setup with hand in progress
- Spectator joins with `JOIN_TABLE role=spectator`; drains to `STATE_SNAPSHOT`
- Drive hand to `HAND_RESULT`
- Assert: spectator log has no `CARDS_DEALT`
- Assert: spectator log has `BLINDS_POSTED`, `TURN_CHANGED`, `PLAYER_ACTED`, `HAND_RESULT`

**T9** — `simulation/scenarios/s4_reconnect.py`
- Start S1 setup with hand in progress
- Player A disconnects (exit inner WS connect context)
- Assert Player B received `PLAYER_STATUS{status=disconnected}` + `reserve_until` populated
- Within 1 s, Player A reconnects and sends `JOIN_TABLE role=player`
- Assert Player A receives `STATE_SNAPSHOT` and is not eliminated

**T10** — `simulation/scenarios/s5_full_table_rejection.py`
- Owner patches `max_players=2` via `patch_table_config`
- Two clients join as players
- Third client (club member) opens WS and sends `JOIN_TABLE role=player`
- Assert receives `ERROR{code=TABLE_FULL}`
- Assert WS connection is still open (send `JOIN_TABLE role=spectator`; assert `STATE_SNAPSHOT`)

**T11** — `simulation/scenarios/s6_timeout_auto_action.py`
- Owner patches `turn_timer_seconds=2` before hand starts
- Two players join and wait for `TURN_CHANGED`
- Acting player does NOT send any action
- Non-acting player's `drain_until("PLAYER_ACTED", max_msgs=50)` with 5 s timeout
- Assert `PLAYER_ACTED.action` is `check` or `fold`

---

### M3 — Pytest Entry Point

**T12** — `tests/test_simulation_scenarios.py`
- One `@pytest.fixture` creates `http` via `make_test_client()`
- Fixture teardown: exit TestClient `__exit__`, restore `BETWEEN_HANDS_DELAY` to `3.0`
- Six `test_*` functions, each calling the corresponding `run(http)`
- All tests must pass in < 30 s total

---

## Dependency Graph

```
T0 → T1 → T2 → T3 → T4 → T5
                T3 → T6, T7, T8, T9, T10, T11
                T6, T7, T8, T9, T10, T11 → T12
```

---

## What Must NOT Change During Implementation

- `poker_engine/` — zero changes
- `backend/` — no changes except module-level constant patching at test time
- `tests/test_app_integration.py` — no changes (only import `_TestAuthService` from it)
- `tests/test_persistence.py`, `tests/test_realtime_schemas.py`, `tests/test_session_manager.py` — no changes
- Any existing routes, schemas, or session_manager public methods

---

## Definition of Done

- [ ] All 6 scenario functions implemented
- [ ] `tests/test_simulation_scenarios.py` has 6 passing test functions
- [ ] Total run time < 30 s
- [ ] `py -3 -m pytest tests/ poker_engine/tests/ -q` shows 175+ tests passing, 0 failed
- [ ] No imports from `backend/sessions/`, `backend/realtime/ws_broadcaster.py`, or `backend/persistence/` internal modules except via the app_factory bootstrap
- [ ] `BETWEEN_HANDS_DELAY` restored to `3.0` in fixture teardown
