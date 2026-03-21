"""
simulation/debug/snapshot.py

Per-client and multi-client capture structures for simulation debug output.
Formats are always-on for capture (EventLog already stores everything),
but formatted only on the failure path.

Hidden-card safety:
  `your_cards` and `hand` payload fields are masked to "<hidden>"
  when is_spectator=True. Player-scoped summaries show own cards unmasked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from simulation.event_log import EventLog

_HIDDEN = "<hidden>"
_SENSITIVE_KEYS = frozenset({"your_cards", "hand"})
_MAX_PAYLOAD_CHARS = 120
_MAX_TAIL_EVENTS = 5


def _mask_payload(payload: dict, is_spectator: bool) -> dict:
    """Return a copy of payload with sensitive keys masked for spectator contexts."""
    if not is_spectator:
        return payload
    return {k: (_HIDDEN if k in _SENSITIVE_KEYS else v) for k, v in payload.items()}


def _truncate(s: str, max_chars: int = _MAX_PAYLOAD_CHARS) -> str:
    return s if len(s) <= max_chars else s[:max_chars] + "\u2026"


@dataclass
class ClientSummary:
    """
    Compact per-client debug summary extracted from a SimulatedClient's EventLog.

    is_spectator=True masks your_cards and hand fields in payload excerpts.
    """
    display_name: str
    phone: str
    event_count: int
    type_sequence: list[str]
    tail_events: list[tuple[str, str]]  # [(event_type, truncated_payload_repr), ...]
    is_spectator: bool = False

    @classmethod
    def from_client(
        cls,
        client,
        is_spectator: bool = False,
        tail: int = _MAX_TAIL_EVENTS,
    ) -> "ClientSummary":
        log: EventLog = client.log
        all_events = log.all()
        tail_events = []
        for e in all_events[-tail:]:
            masked = _mask_payload(e.payload, is_spectator)
            raw = json.dumps(masked, default=str)
            tail_events.append((e.type, _truncate(raw)))
        return cls(
            display_name=getattr(client, "display_name", "?"),
            phone=getattr(client, "phone", "?"),
            event_count=len(all_events),
            type_sequence=log.types(),
            tail_events=tail_events,
            is_spectator=is_spectator,
        )

    def format(self) -> str:
        role_tag = " [spectator]" if self.is_spectator else ""
        lines = [
            f"  Client: {self.display_name}{role_tag} ({self.phone})",
            f"  Events: {self.event_count}  sequence: {self.type_sequence}",
        ]
        if self.tail_events:
            lines.append(f"  Last {len(self.tail_events)} event(s):")
            for etype, payload_str in self.tail_events:
                lines.append(f"    [{etype}] {payload_str}")
        else:
            lines.append("  (no events recorded)")
        return "\n".join(lines)


@dataclass
class ScenarioSnapshot:
    """
    Multi-client snapshot captured at a point in a scenario.
    Used to attach context to AssertionError messages.
    """
    scenario_name: str
    summaries: list[ClientSummary] = field(default_factory=list)

    @classmethod
    def capture(
        cls,
        scenario_name: str,
        clients: list,
        spectator_indices: list[int] | None = None,
    ) -> "ScenarioSnapshot":
        spectator_set = set(spectator_indices or [])
        summaries = [
            ClientSummary.from_client(c, is_spectator=(i in spectator_set))
            for i, c in enumerate(clients)
        ]
        return cls(scenario_name=scenario_name, summaries=summaries)

    def format(self) -> str:
        lines = [f"=== ScenarioSnapshot: {self.scenario_name} ==="]
        for s in self.summaries:
            lines.append(s.format())
        return "\n".join(lines)
