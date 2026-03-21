"""
simulation/debug/summary.py

Load-lite multi-table run summary. Compact tabular format for failure reports.
"""
from __future__ import annotations

from dataclasses import dataclass

from simulation.load_lite.orchestrator import TableScenarioResult


@dataclass
class LoadLiteSummary:
    """
    Compact summary of a load-lite run's TableScenarioResult list.
    Formatted output is produced on failure; suppressed when all pass.
    """
    results: list[TableScenarioResult]

    def format(self) -> str:
        lines = [
            "LOAD-LITE RUN SUMMARY",
            f"  {'idx':<4} {'table_id':<38} {'pass':<6} {'events':<8} {'last_event':<22} error",
        ]
        for r in self.results:
            last = r.event_types[-1] if r.event_types else "\u2014"
            err = (r.error or "")[:60] if r.error else ""
            lines.append(
                f"  {r.table_index:<4} {(r.table_id or '\u2014'):<38} "
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
