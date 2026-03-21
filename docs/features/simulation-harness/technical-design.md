# Technical Design — simulation-harness

> Agent: Senior Mobile Game Developer
> Gate: Technical Design (Gate 4)
> Status: APPROVED

---

## Design Philosophy

The harness drives the **real application** from the outside via its published transport contracts (HTTP + WebSocket JSON). It has no knowledge of, and no dependency on, internal module structure beyond what is needed for test bootstrapping:

1. `create_app()` — to obtain a live ASGI app
2. `_TestAuthService` pattern — to inject a deterministic auth service (reused from integration tests)
3. `ClientEnvelope` / `ServerEnvelope` schemas — for message construction and parsing

This keeps the harness decoupled from implementation details. If session_manager internals change, scenarios continue to work as long as the transport contract is unchanged.

---

## Module Layout

```
simulation/
├── __init__.py                # exports: SimulatedClient, ScenarioRunner
├── app_factory.py             # harness-flavoured create_app() wrapper
├── client.py                  # SimulatedClient
├── event_log.py               # EventLog (per-client captured messages)
├── helpers.py                 # auth_flow(), create_club(), join_club() helpers
├── runner.py                  # ScenarioRunner
└── scenarios/
    ├── __init__.py
    ├── s1_two_player_hand.py
    ├── s2_mid_hand_join.py
    ├── s3_spectator_filtering.py
    ├── s4_reconnect.py
    ├── s5_full_table_rejection.py
    └── s6_timeout_auto_action.py

tests/
└── test_simulation_scenarios.py   # pytest entry point; runs all 6 scenarios
```

All scenario modules are **pure functions** — no pytest fixtures inside them. The pytest file calls them.

---

## `simulation/app_factory.py`

```python
"""
Creates a test-mode FastAPI app with:
  - TestAuthService (deterministic OTP)
  - configurable BETWEEN_HANDS_DELAY
  - configurable turn_timer_seconds (via TableConfig override at club creation)
"""

from fastapi.testclient import TestClient
from backend.main import create_app
from tests.test_app_integration import _TestAuthService  # reuse

def make_test_client(between_hands_delay: float = 0.05) -> TestClient:
    """
    Returns (app, TestClient) with lifespan run and auth overridden.
    between_hands_delay patches session_manager.BETWEEN_HANDS_DELAY.
    """
    import backend.sessions.session_manager as sm
    sm.BETWEEN_HANDS_DELAY = between_hands_delay

    _app = create_app()
    client = TestClient(_app, raise_server_exceptions=True)
    client.__enter__()   # trigger lifespan
    _app.state.auth_service = _TestAuthService(_app.state.persistence)
    return client
```

> Note: `sm.BETWEEN_HANDS_DELAY = between_hands_delay` is module-attribute patching, not monkeypatching a live asyncio task. The constant is read each time the delay is awaited, so overriding it before any table is created is safe.

---

## `simulation/event_log.py`

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class CapturedEvent:
    type: str
    payload: dict[str, Any]
    seq: int
    ts: float

class EventLog:
    def __init__(self) -> None:
        self._events: list[CapturedEvent] = []

    def append(self, raw: dict) -> None:
        self._events.append(CapturedEvent(
            type=raw["type"],
            payload=raw.get("payload", {}),
            seq=raw.get("seq", 0),
            ts=raw.get("ts", 0.0),
        ))

    def all(self) -> list[CapturedEvent]:
        return list(self._events)

    def of_type(self, event_type: str) -> list[CapturedEvent]:
        return [e for e in self._events if e.type == event_type]

    def has_type(self, event_type: str) -> bool:
        return any(e.type == event_type for e in self._events)

    def clear(self) -> None:
        self._events.clear()
```

---

## `simulation/client.py`

```python
"""
SimulatedClient — one logical player or spectator.

Transport contract:
  HTTP:  standard requests via TestClient
  WS:    TestClient.websocket_connect() context manager
         Messages use ClientEnvelope JSON format (type, request_id, table_id, payload)
         Server sends ServerEnvelope JSON (v, seq, table_id, type, payload, ts)
"""
import json
import uuid
from contextlib import contextmanager
from typing import Optional
from fastapi.testclient import TestClient
from .event_log import EventLog

class SimulatedClient:
    def __init__(self, http: TestClient, phone: str, display_name: str) -> None:
        self._http = http
        self.phone = phone
        self.display_name = display_name
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.log = EventLog()
        self._ws = None          # active WS context when connected

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self) -> "SimulatedClient":
        """Full OTP flow. Idempotent — skips if already authenticated."""
        if self.token:
            return self
        self._http.post("/auth/request-otp", json={"phone_number": self.phone})
        resp = self._http.post(
            "/auth/verify-otp",
            json={"phone_number": self.phone, "code": "123456", "display_name": self.display_name},
        )
        assert resp.status_code == 200, f"auth failed: {resp.text}"
        body = resp.json()
        self.token = body["token"]
        self.user_id = body["user_id"]
        return self

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def auth_headers(self) -> dict:
        assert self.token, "must authenticate first"
        return {"Authorization": f"Bearer {self.token}"}

    def create_club(self, name: str = "Sim Club") -> dict:
        """Returns {club_id, table_id, invite_code}."""
        resp = self._http.post("/clubs", json={"name": name}, headers=self.auth_headers())
        assert resp.status_code == 201, f"create_club failed: {resp.text}"
        return resp.json()

    def join_club(self, club_id: str, invite_code: str) -> None:
        resp = self._http.post(
            f"/clubs/{club_id}/join",
            json={"invite_code": invite_code},
            headers=self.auth_headers(),
        )
        assert resp.status_code == 200, f"join_club failed: {resp.text}"

    def get_club(self, club_id: str) -> dict:
        resp = self._http.get(f"/clubs/{club_id}", headers=self.auth_headers())
        assert resp.status_code == 200
        return resp.json()

    def patch_table_config(self, club_id: str, **kwargs) -> None:
        resp = self._http.patch(
            f"/clubs/{club_id}/table/config",
            json=kwargs,
            headers=self.auth_headers(),
        )
        assert resp.status_code == 200, f"patch_table_config failed: {resp.text}"

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    @contextmanager
    def connect(self, table_id: str):
        """
        Context manager for WS connection. Clears log on entry.
        Usage:
            with client.connect(table_id):
                client.send_join("player")
                client.drain_until("STATE_SNAPSHOT")
        """
        assert self.token
        self.log.clear()
        with self._http.websocket_connect(f"/ws/table/{table_id}?token={self.token}") as ws:
            self._ws = ws
            try:
                yield self
            finally:
                self._ws = None

    def send(self, msg_type: str, table_id: str, payload: dict = None) -> str:
        """Send a client envelope; returns the request_id used."""
        assert self._ws, "not connected"
        req_id = str(uuid.uuid4())
        self._ws.send_json({
            "type": msg_type,
            "request_id": req_id,
            "table_id": table_id,
            "payload": payload or {},
        })
        return req_id

    def send_join(self, table_id: str, role: str = "player") -> str:
        return self.send("JOIN_TABLE", table_id, {"role": role})

    def send_action(self, table_id: str, action: str, amount: int = 0) -> str:
        return self.send("ACTION", table_id, {"action": action, "amount": amount})

    def recv_one(self) -> dict:
        """Receive and log one message."""
        assert self._ws
        msg = self._ws.receive_json()
        self.log.append(msg)
        return msg

    def drain_until(self, event_type: str, max_msgs: int = 30) -> dict:
        """
        Consume messages until one of the target type is found.
        All consumed messages are appended to self.log.
        Raises AssertionError if not found within max_msgs.
        """
        for _ in range(max_msgs):
            msg = self.recv_one()
            if msg["type"] == event_type:
                return msg
        raise AssertionError(
            f"{event_type!r} not received within {max_msgs} messages. "
            f"Got types: {[e.type for e in self.log.all()]}"
        )

    def drain_n(self, n: int) -> list[dict]:
        """Receive exactly n messages, logging all."""
        return [self.recv_one() for _ in range(n)]
```

---

## `simulation/helpers.py`

```python
"""
High-level scenario helpers — composite operations used across multiple scenarios.
"""

from fastapi.testclient import TestClient
from .client import SimulatedClient

def make_client(http: TestClient, phone: str, name: str) -> SimulatedClient:
    return SimulatedClient(http, phone, name).authenticate()

def setup_two_players(http: TestClient) -> tuple[SimulatedClient, SimulatedClient, str, str]:
    """
    Create two authenticated clients, a club, and return:
    (owner, joiner, club_id, table_id)
    """
    owner = make_client(http, "+15550001001", "Owner")
    joiner = make_client(http, "+15550001002", "Joiner")

    data = owner.create_club("Sim Club")
    club_id = data["club_id"]
    table_id = data["table_id"]
    invite_code = data["invite_code"]

    joiner.join_club(club_id, invite_code)
    return owner, joiner, club_id, table_id

def both_join_as_players(owner, joiner, table_id: str):
    """
    Must be called inside nested WS context managers.
    Both clients send JOIN_TABLE and drain to STATE_SNAPSHOT.
    """
    owner.send_join(table_id, "player")
    owner.drain_until("STATE_SNAPSHOT")

    joiner.send_join(table_id, "player")
    joiner.drain_until("STATE_SNAPSHOT")
```

---

## `simulation/runner.py`

```python
"""
ScenarioRunner — optional orchestration helper for multi-step scenarios.

Scenarios can also be implemented as free functions without using Runner.
Runner is provided for scenarios that need coordinated setup/teardown.
"""
from dataclasses import dataclass, field
from fastapi.testclient import TestClient

@dataclass
class ScenarioResult:
    name: str
    passed: bool
    error: str = ""

class ScenarioRunner:
    def __init__(self, http: TestClient) -> None:
        self.http = http
        self.results: list[ScenarioResult] = []

    def run(self, name: str, fn) -> ScenarioResult:
        try:
            fn(self.http)
            r = ScenarioResult(name=name, passed=True)
        except Exception as exc:
            r = ScenarioResult(name=name, passed=False, error=str(exc))
        self.results.append(r)
        return r

    def assert_all_passed(self) -> None:
        failures = [r for r in self.results if not r.passed]
        if failures:
            lines = [f"  {r.name}: {r.error}" for r in failures]
            raise AssertionError("Scenario failures:\n" + "\n".join(lines))
```

---

## Delay Override Strategy

Two delays must be shortened in scenarios:

| Constant | Module | Default | Override value |
|----------|--------|---------|---------------|
| `BETWEEN_HANDS_DELAY` | `backend.sessions.session_manager` | `3.0` | `0.05` |
| `turn_timer_seconds` | `TableConfig` (per table) | `30` | `2` (set via `PATCH /clubs/{id}/table/config`) |

**Between-hands delay** is a module-level constant read inside `asyncio.sleep()`. It is safe to replace it with a float before the `TableSessionManager` is instantiated. The `make_test_client()` factory does this.

**Turn timer** is a per-table config value. For the timeout scenario (S6), the club owner uses `patch_table_config(club_id, turn_timer_seconds=2)` before any hand starts.

No monkey-patching of asyncio or internal timers is required.

---

## Event Ordering Guarantee

The harness relies on the session_manager's documented dispatch order (from `session_manager.py`):
1. `PLAYER_JOINED` broadcast
2. `STATE_SNAPSHOT` private to joining player

Because TestClient processes messages synchronously, and the server sends `PLAYER_JOINED` then `STATE_SNAPSHOT` in that order within the same coroutine, `drain_until("STATE_SNAPSHOT")` will find the snapshot after zero or more `PLAYER_JOINED` messages. The 30-message window provides sufficient tolerance.

---

## Concurrency Strategy

The harness uses **nested synchronous WS context managers**, the same pattern proven in `test_ws_duplicate_request_id_dropped`. This works because:

- TestClient runs the ASGI app in a background thread
- Each `websocket_connect()` context communicates synchronously with that thread
- The background thread handles async dispatch normally
- Nested contexts are opened sequentially but run concurrently in the background

```
with client_a.connect(table_id):
    with client_b.connect(table_id):
        client_a.send_join(table_id)
        client_a.drain_until("STATE_SNAPSHOT")
        client_b.send_join(table_id)
        client_b.drain_until("STATE_SNAPSHOT")
        # both connected; hand will start when engine has ≥2 players
```

For the reconnect scenario (S4), the inner WS context is exited and re-entered while the outer structure remains. This produces the disconnect and reconnect sequence.

---

## Spectator Filtering Verification

`CARDS_DEALT` is sent only to the specific player whose cards they are (private unicast). Spectators are never in the send list. The assertion is:

```python
assert not spectator.log.has_type("CARDS_DEALT"), \
    "spectator must never receive CARDS_DEALT"
```

The spectator must remain connected through at least one full hand for this assertion to be meaningful.

---

## Full-Table Rejection

The session_manager enforces `MAX_PLAYERS = 10`. When an 11th player sends `JOIN_TABLE` with `role="player"`, the server returns an `ERROR` event with `code="TABLE_FULL"`. No WS close is issued — the connection stays open.

```python
client_11.send_join(table_id, "player")
err = client_11.drain_until("ERROR")
assert err["payload"]["code"] == "TABLE_FULL"
```

---

## Module Boundary Rules

| Rule | Rationale |
|------|-----------|
| `simulation/` must not import from `backend/sessions/` | Avoids coupling to internal implementation |
| `simulation/` must not import from `backend/realtime/ws_broadcaster.py` | Broadcaster is internal; harness uses only transport |
| `simulation/` MAY import `ClientEnvelope`, `ServerEnvelope` from `backend.realtime.schemas` | These are the published transport contracts |
| `simulation/` MAY import `create_app` from `backend.main` | Required to start the app |
| `simulation/` MAY import `_TestAuthService` from `tests.test_app_integration` | Established test utility — acceptable coupling |
| `simulation/` must not modify any file under `poker_engine/` | Engine isolation |
| `simulation/` must not modify any file under `backend/` except patching module constants at test setup | Cleanly reverted after test |
| `simulation/scenarios/` must not import from each other | Scenarios are independent |

---

## File Boundaries Summary

| File | Responsibility |
|------|---------------|
| `simulation/app_factory.py` | App + TestClient construction with delay override |
| `simulation/event_log.py` | Captured event storage and filtering |
| `simulation/client.py` | `SimulatedClient` — HTTP + WS interactions |
| `simulation/helpers.py` | Reusable multi-client setup functions |
| `simulation/runner.py` | Optional `ScenarioRunner` for coordinated test runs |
| `simulation/scenarios/s*.py` | One scenario per file; each is a plain function `def run(http): ...` |
| `tests/test_simulation_scenarios.py` | pytest test functions; one per scenario; calls `run(http)` |

---

## Non-Goals

- No `asyncio.run()` / `anyio` — all sync via TestClient
- No Redis, no external process, no Docker
- No new API routes or session_manager methods
- No engine modifications
- No load generation (>10 concurrent connections intentionally out of scope)
