# Technical Design — debug-observability-for-simulation

> Agent: Senior Mobile Game Developer
> Gate: Technical Design (Gate 2)
> Status: APPROVED

---

## 1. Design Summary

Add `simulation/debug/` — a three-module package that captures, formats, and reports simulation failure context. The package has **zero imports from `poker_engine/` or `backend/`** and adds **zero runtime cost on passing tests**. All existing simulation code is left structurally unchanged; the debug package is additive and opt-in at the call site.

The core principle: `EventLog` already captures everything — the debug package only formats that data better on the failure path.

---

## 2. Module Layout

```
simulation/
  debug/
    __init__.py        # exports: ClientSummary, ScenarioSnapshot, FailureReport,
                       #          LoadLiteSummary, stuck_diagnostic, format_ordering_failure,
                       #          format_leakage_failure
    snapshot.py        # ClientSummary, ScenarioSnapshot — capture structures
    report.py          # FailureReport, stuck_diagnostic, format_* helpers
    summary.py         # LoadLiteSummary — load-lite multi-table summary
```

Existing files modified (minimally):
- `simulation/load_lite/assertions.py` — enrich 3 failure messages using `simulation.debug`
- `simulation/client.py` — enrich `drain_until` `AssertionError` message using `ClientSummary`

---

## 3. `snapshot.py` — Capture Structures

### 3.1 `ClientSummary`

```python
from __future__ import annotations
import textwrap
import json
from dataclasses import dataclass
from simulation.event_log import EventLog, CapturedEvent

_HIDDEN = "<hidden>"
_SENSITIVE_KEYS = {"your_cards", "hand"}
_MAX_PAYLOAD_CHARS = 120
_MAX_TAIL_EVENTS = 5
_MAX_LINES = 30


def _mask_payload(payload: dict, is_spectator: bool) -> dict:
    """
    Return a copy of payload with sensitive keys masked for spectator contexts.
    Only `your_cards` and `hand` are masked; all other fields are preserved.
    """
    if not is_spectator:
        return payload
    result = {}
    for k, v in payload.items():
        result[k] = _HIDDEN if k in _SENSITIVE_KEYS else v
    return result


def _truncate(s: str, max_chars: int = _MAX_PAYLOAD_CHARS) -> str:
    return s if len(s) <= max_chars else s[:max_chars] + "…"


@dataclass
class ClientSummary:
    """
    Compact per-client debug summary extracted from an EventLog.

    is_spectator=True masks your_cards and hand fields in payload excerpts.
    """
    display_name: str
    phone: str
    event_count: int
    type_sequence: list[str]
    tail_events: list[tuple[str, str]]   # [(type, truncated_payload_repr), ...]
    is_spectator: bool = False

    @classmethod
    def from_client(
        cls,
        client,                          # SimulatedClient
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
            display_name=client.display_name,
            phone=client.phone,
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
            f"  Last {len(self.tail_events)} events:",
        ]
        for etype, payload_str in self.tail_events:
            lines.append(f"    [{etype}] {payload_str}")
        return "\n".join(lines)
```

### 3.2 `ScenarioSnapshot`

```python
@dataclass
class ScenarioSnapshot:
    """
    Multi-client snapshot captured at a point in a scenario.
    Used to attach context to AssertionError messages.
    """
    scenario_name: str
    summaries: list[ClientSummary]

    @classmethod
    def capture(
        cls,
        scenario_name: str,
        clients: list,                   # list of SimulatedClient
        spectator_indices: list[int] = None,
    ) -> "ScenarioSnapshot":
        spectator_indices = set(spectator_indices or [])
        summaries = [
            ClientSummary.from_client(c, is_spectator=(i in spectator_indices))
            for i, c in enumerate(clients)
        ]
        return cls(scenario_name=scenario_name, summaries=summaries)

    def format(self) -> str:
        lines = [f"=== ScenarioSnapshot: {self.scenario_name} ==="]
        for s in self.summaries:
            lines.append(s.format())
        return "\n".join(lines)
```

---

## 4. `report.py` — Failure Formatters

### 4.1 `stuck_diagnostic`

Called when `drain_until` times out. Captures the "last known position" across all clients.

```python
def stuck_diagnostic(
    clients: list,                       # SimulatedClient list
    drain_target: str,
    elapsed_seconds: float,
    spectator_indices: list[int] = None,
) -> str:
    """
    Produce a stuck-scenario diagnostic string.
    Shows: target event type, elapsed time, last event per client.
    """
    spectator_indices = set(spectator_indices or [])
    lines = [
        f"STUCK DIAGNOSTIC — waiting for {drain_target!r} after {elapsed_seconds:.1f}s",
    ]
    for i, c in enumerate(clients):
        is_spec = i in spectator_indices
        types = c.log.types()
        last = types[-1] if types else "(no events)"
        count = len(types)
        masked_last = last
        lines.append(
            f"  {c.display_name}{'[spectator]' if is_spec else ''}: "
            f"{count} events, last={masked_last!r}"
        )
    return "\n".join(lines)
```

### 4.2 `format_ordering_failure`

```python
def format_ordering_failure(
    player,                              # SimulatedClient
    before: str,
    after: str,
    table_id: str = "",
) -> str:
    """
    Produce a detailed ordering-failure message.
    Highlights positions of `before` and `after` in the full type sequence.
    """
    types = player.log.types()
    annotated = []
    for i, t in enumerate(types):
        if t == before:
            annotated.append(f"[{i}]>>>{t}<<<")
        elif t == after:
            annotated.append(f"[{i}]>>>{t}<<<")
        else:
            annotated.append(f"[{i}]{t}")
    label = f"[{table_id}] " if table_id else ""
    return (
        f"{label}ORDERING FAILURE: {before!r} must precede {after!r}\n"
        f"  Full sequence: {annotated}"
    )
```

### 4.3 `format_leakage_failure`

```python
def format_leakage_failure(
    spectator,                           # SimulatedClient
    expected_table_id: str,
    offending_event_type: str,
    offending_table_id: str,
    offending_payload: dict,
) -> str:
    """
    Produce a cross-table leakage failure message.
    Shows full spectator type sequence and offending event details.
    """
    types = spectator.log.types()
    payload_str = _truncate(str(offending_payload))
    return (
        f"CROSS-TABLE LEAKAGE: spectator on {expected_table_id!r} "
        f"received {offending_event_type!r} from table {offending_table_id!r}\n"
        f"  Spectator sequence: {types}\n"
        f"  Offending payload: {payload_str}"
    )
```

### 4.4 `FailureReport`

```python
@dataclass
class FailureReport:
    """
    Full failure report for a scenario. Built at the call site, attached to AssertionError.
    """
    scenario_name: str
    message: str
    snapshot: ScenarioSnapshot

    def format(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"FAILURE: {self.scenario_name}",
            f"  {self.message}",
            self.snapshot.format(),
            f"{'='*60}",
        ]
        return "\n".join(lines)

    def raise_as(self, msg: str = "") -> None:
        """Raise AssertionError with this report appended."""
        raise AssertionError((msg or self.message) + "\n" + self.format())
```

---

## 5. `summary.py` — Load-Lite Multi-Table Summary

```python
from __future__ import annotations
from dataclasses import dataclass
from simulation.load_lite.orchestrator import TableScenarioResult


@dataclass
class LoadLiteSummary:
    """
    Compact summary of a load-lite run's TableScenarioResult list.
    Always prints on failure; suppressed on full pass.
    """
    results: list[TableScenarioResult]

    def format(self) -> str:
        lines = [
            "LOAD-LITE RUN SUMMARY",
            f"  {'idx':<4} {'table_id':<38} {'pass':<6} {'events':<8} {'last_event':<22} error",
        ]
        for r in self.results:
            last = r.event_types[-1] if r.event_types else "—"
            err = (r.error or "")[:60] if r.error else ""
            lines.append(
                f"  {r.table_index:<4} {(r.table_id or '—'):<38} "
                f"{'OK' if r.passed else 'FAIL':<6} "
                f"{len(r.event_types):<8} {last:<22} {err}"
            )
        failed = sum(1 for r in self.results if not r.passed)
        lines.append(f"  {len(self.results)} tables, {failed} failed")
        return "\n".join(lines)

    def assert_all_passed(self) -> None:
        failed = [r for r in self.results if not r.passed]
        if failed:
            raise AssertionError(self.format())
```

---

## 6. What Gets Recorded vs What Does Not

### Always recorded (via existing `EventLog`)
- Every server envelope received by every `SimulatedClient`
- Event type, payload, seq, ts

### Formatted on failure only
- `ClientSummary` — last N events with truncated payloads
- `stuck_diagnostic` — last event per client, elapsed time
- `format_ordering_failure` — annotated type sequence
- `format_leakage_failure` — spectator sequence + offending event
- `LoadLiteSummary` — per-table row table

### Never formatted (hidden-card safety)
- `your_cards` payload field in any spectator-scoped output
- `hand` payload field in any spectator-scoped output
- These are masked to `"<hidden>"` when `is_spectator=True`

### Never recorded (not needed)
- Raw WS frames or HTTP request/response bodies
- Internal backend state (session manager, asyncio task state)
- Engine-internal hand object (cards, deck)
- Timing microsecond-level traces

---

## 7. Integration Points

### 7.1 `simulation/client.py` — enriched `drain_until`

The existing `drain_until` raises:
```python
raise AssertionError(
    f"{event_type!r} not received within {max_msgs} messages. "
    f"Types received: {self.log.types()}"
)
```

Enhanced version adds a `ClientSummary` snippet:

```python
from simulation.debug.snapshot import ClientSummary

raise AssertionError(
    f"{event_type!r} not received within {max_msgs} messages.\n"
    + ClientSummary.from_client(self).format()
)
```

This is a **drop-in enrichment** — same `AssertionError`, richer message. No signature change.

### 7.2 `simulation/load_lite/assertions.py` — enriched failure messages

`assert_spectator_isolation` currently raises a plain message. Enhanced:

```python
from simulation.debug.report import format_leakage_failure

# inside the table_id mismatch check:
raise AssertionError(
    format_leakage_failure(spectator, expected_table_id, event.type, tid, event.payload)
)
```

`assert_event_ordering` enhanced:

```python
from simulation.debug.report import format_ordering_failure

raise AssertionError(
    format_ordering_failure(player, "BLINDS_POSTED", "HAND_RESULT", table_id)
)
```

`assert_all_results_passed` enhanced:

```python
from simulation.debug.summary import LoadLiteSummary

summary = LoadLiteSummary(results)
summary.assert_all_passed()   # raises with formatted summary if any fail
```

---

## 8. Hidden-Card Safety

Two layers of protection:

**Layer 1 — Role-aware masking in `_mask_payload`:**
`is_spectator=True` masks `your_cards` and `hand` to `"<hidden>"`. The `is_spectator` flag is set at the call site when a `SimulatedClient` is known to be a spectator.

**Layer 2 — Per-client scope:**
`ClientSummary.from_client(client, is_spectator=False)` called on an actual player does NOT mask `your_cards`. This is correct — a player's own debug summary should show their own cards (useful for diagnosing DS1/DS2 failures). It does not show other players' cards because each player only receives their own `CARDS_DEALT`.

**What this means in practice:**
- `ScenarioSnapshot.capture(clients=[owner, joiner, spectator], spectator_indices=[2])` correctly masks spectator output while showing player cards.
- The engine's broadcast isolation ensures spectators never receive `CARDS_DEALT` with another player's `your_cards` — the debug layer inherits this guarantee.

---

## 9. Output Size Budget

| Output | Hard cap |
|--------|----------|
| `ClientSummary.format()` | ≤ `_MAX_TAIL_EVENTS` (5) events + header = ~10 lines |
| `ScenarioSnapshot.format()` | ≤ 3 clients × 10 lines = ~30 lines |
| `LoadLiteSummary.format()` | 1 header + 3 rows + 1 footer = 5 lines |
| `stuck_diagnostic` | 1 header + 1 line per client = ~5 lines |
| `format_ordering_failure` | 2 lines |
| `format_leakage_failure` | 3 lines |
| `FailureReport.format()` | ~35 lines max (separator + snapshot) |

Total maximum output for a 3-table load-lite failure: ~50 lines. Fits on one terminal screen.

---

## 10. Runtime Budget

| Operation | Cost |
|-----------|------|
| `EventLog.all()` | O(n) list copy — negligible (<1 ms for typical logs of <200 events) |
| `ClientSummary.from_client()` | O(n) for last-5 tail, O(1) for display fields |
| `format_*` helpers | O(n) string operations, called only on failure |
| `LoadLiteSummary.format()` | O(k) for k tables — negligible |
| **On passing tests** | **Zero** — format helpers are never called |

---

## 11. Import Boundary

`simulation/debug/` imports only from:
- `simulation.event_log` (EventLog, CapturedEvent)
- `simulation.load_lite.orchestrator` (TableScenarioResult) — only in `summary.py`
- stdlib: `dataclasses`, `json`, `textwrap`, `time`

`simulation/debug/` does NOT import from:
- `backend.*`
- `poker_engine.*`
- `fastapi.*`
- Any other simulation package beyond event_log and load_lite.orchestrator

---

## 12. No Production Code Changes

Zero files under `poker_engine/` or `backend/` are modified. Changes are:
- **New**: `simulation/debug/__init__.py`, `snapshot.py`, `report.py`, `summary.py`
- **Enhanced**: `simulation/client.py` (drain_until message only)
- **Enhanced**: `simulation/load_lite/assertions.py` (failure messages only)
