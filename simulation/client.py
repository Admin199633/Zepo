"""
SimulatedClient — one logical player or spectator.

Wraps HTTP + WebSocket interactions against a live TestClient backend.
Transport contract: uses ClientEnvelope JSON format for outbound messages,
parses ServerEnvelope JSON for inbound messages.

No imports from backend/sessions/, backend/realtime/ws_broadcaster.py, or
any other internal module. Only the published transport contracts are used.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Optional

from fastapi.testclient import TestClient

from .event_log import EventLog


class SimulatedClient:
    """
    One simulated player or spectator.

    Lifecycle:
        client = SimulatedClient(http, "+15550001001", "Alice")
        client.authenticate()
        data = client.create_club()
        with client.connect(data["table_id"]):
            client.send_join(data["table_id"])
            client.drain_until("STATE_SNAPSHOT")
    """

    def __init__(self, http: TestClient, phone: str, display_name: str) -> None:
        self._http = http
        self.phone = phone
        self.display_name = display_name
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.log = EventLog()
        self._ws = None  # active WS session when inside connect()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self) -> "SimulatedClient":
        """Full OTP flow. Idempotent — skips if already authenticated."""
        if self.token:
            return self
        r = self._http.post("/auth/request-otp", json={"phone_number": self.phone})
        assert r.status_code == 200, f"request-otp failed: {r.text}"
        r = self._http.post(
            "/auth/verify-otp",
            json={
                "phone_number": self.phone,
                "code": "123456",
                "display_name": self.display_name,
            },
        )
        assert r.status_code == 200, f"verify-otp failed: {r.text}"
        body = r.json()
        self.token = body["token"]
        self.user_id = body["user_id"]
        return self

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        assert self.token, "call authenticate() first"
        return {"Authorization": f"Bearer {self.token}"}

    def create_club(self, name: str = "Sim Club") -> dict:
        """Returns {club_id, table_id, invite_code}."""
        r = self._http.post("/clubs", json={"name": name}, headers=self._headers())
        assert r.status_code == 201, f"create_club failed: {r.text}"
        return r.json()

    def join_club(self, club_id: str, invite_code: str) -> None:
        r = self._http.post(
            f"/clubs/{club_id}/join",
            json={"invite_code": invite_code},
            headers=self._headers(),
        )
        assert r.status_code == 200, f"join_club failed: {r.text}"

    def get_club(self, club_id: str) -> dict:
        r = self._http.get(f"/clubs/{club_id}", headers=self._headers())
        assert r.status_code == 200, f"get_club failed: {r.text}"
        return r.json()

    def patch_table_config(self, club_id: str, **kwargs: Any) -> dict:
        """Partial update — any TableConfig field can be passed as kwargs."""
        r = self._http.patch(
            f"/clubs/{club_id}/table/config",
            json=kwargs,
            headers=self._headers(),
        )
        assert r.status_code == 200, f"patch_table_config failed: {r.text}"
        return r.json()

    def try_join_club(self, club_id: str, invite_code: str) -> int:
        """Returns HTTP status code (for negative testing)."""
        r = self._http.post(
            f"/clubs/{club_id}/join",
            json={"invite_code": invite_code},
            headers=self._headers(),
        )
        return r.status_code

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    @contextmanager
    def connect(self, table_id: str):
        """
        Context manager that opens a WS connection to the table.
        Clears the event log on entry so each connection starts fresh.

        Usage:
            with client.connect(table_id):
                client.send_join(table_id)
                client.drain_until("STATE_SNAPSHOT")
        """
        assert self.token, "call authenticate() first"
        self.log.clear()
        with self._http.websocket_connect(
            f"/ws/table/{table_id}?token={self.token}"
        ) as ws:
            self._ws = ws
            try:
                yield self
            finally:
                self._ws = None

    def send(self, msg_type: str, table_id: str, payload: Optional[dict] = None) -> str:
        """Send a client envelope. Returns the request_id used."""
        assert self._ws is not None, "must be inside connect() context"
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

    def send_chat(self, table_id: str, message: str) -> str:
        return self.send("CHAT", table_id, {"message": message})

    def recv_one(self) -> dict:
        """Receive one message and append it to the event log."""
        assert self._ws is not None, "must be inside connect() context"
        msg = self._ws.receive_json()
        self.log.append(msg)
        return msg

    def drain_until(self, event_type: str, max_msgs: int = 30) -> dict:
        """
        Consume messages until one of target type is received.
        All consumed messages are appended to self.log.
        Raises AssertionError with diagnostic info if not found.
        """
        for _ in range(max_msgs):
            msg = self.recv_one()
            if msg["type"] == event_type:
                return msg
        from simulation.debug.snapshot import ClientSummary
        raise AssertionError(
            f"{event_type!r} not received within {max_msgs} messages.\n"
            + ClientSummary.from_client(self).format()
        )

    def drain_n(self, n: int) -> list[dict]:
        """Receive exactly n messages, logging all."""
        return [self.recv_one() for _ in range(n)]
