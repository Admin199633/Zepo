"""
simulation/debug/report.py

Failure report formatters for simulation diagnostics.
All formatters produce bounded, human-readable strings for use in AssertionError messages.
"""
from __future__ import annotations

from dataclasses import dataclass

from simulation.debug.snapshot import ClientSummary, ScenarioSnapshot, _truncate


def stuck_diagnostic(
    clients: list,
    drain_target: str,
    elapsed_seconds: float,
    spectator_indices: list[int] | None = None,
) -> str:
    """
    Produce a stuck-scenario diagnostic.
    Shows: target event type, elapsed time, last event per client.
    """
    spectator_set = set(spectator_indices or [])
    lines = [
        f"STUCK DIAGNOSTIC — waiting for {drain_target!r} "
        f"after {elapsed_seconds:.1f}s",
    ]
    for i, c in enumerate(clients):
        is_spec = i in spectator_set
        types = c.log.types()
        last = repr(types[-1]) if types else "(no events)"
        count = len(types)
        spec_tag = "[spectator]" if is_spec else ""
        lines.append(
            f"  {getattr(c, 'display_name', '?')}{spec_tag}: "
            f"{count} events, last={last}"
        )
    return "\n".join(lines)


def format_ordering_failure(
    player,
    before: str,
    after: str,
    table_id: str = "",
) -> str:
    """
    Produce an annotated ordering-failure message.
    Highlights positions of `before` and `after` in the full type sequence.
    """
    types = player.log.types()
    annotated = []
    for i, t in enumerate(types):
        if t in (before, after):
            annotated.append(f"[{i}]>>>{t}<<<")
        else:
            annotated.append(f"[{i}]{t}")
    label = f"[{table_id}] " if table_id else ""
    return (
        f"{label}ORDERING FAILURE: {before!r} must precede {after!r}\n"
        f"  Full sequence: {annotated}"
    )


def format_leakage_failure(
    spectator,
    expected_table_id: str,
    offending_event_type: str,
    offending_table_id: str,
    offending_payload: dict,
) -> str:
    """
    Produce a cross-table leakage failure message.
    Shows spectator's full type sequence and the offending event's details.
    """
    types = spectator.log.types()
    payload_str = _truncate(str(offending_payload))
    return (
        f"CROSS-TABLE LEAKAGE: spectator on {expected_table_id!r} "
        f"received {offending_event_type!r} from table {offending_table_id!r}\n"
        f"  Spectator sequence: {types}\n"
        f"  Offending payload: {payload_str}"
    )


@dataclass
class FailureReport:
    """
    Full failure report for a scenario. Built at the call site, attached to AssertionError.
    """
    scenario_name: str
    message: str
    snapshot: ScenarioSnapshot

    def format(self) -> str:
        sep = "=" * 60
        lines = [
            f"\n{sep}",
            f"FAILURE: {self.scenario_name}",
            f"  {self.message}",
            self.snapshot.format(),
            sep,
        ]
        return "\n".join(lines)

    def raise_as(self, msg: str = "") -> None:
        """Raise AssertionError with this report appended."""
        raise AssertionError((msg or self.message) + "\n" + self.format())
