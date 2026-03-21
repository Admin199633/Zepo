"""
Assertion helpers for load-lite scenarios.
"""
from __future__ import annotations

from .orchestrator import TableScenarioResult


def assert_hand_completed(owner, joiner, table_id: str) -> None:
    assert owner.log.has_type("HAND_RESULT"), (
        f"[{table_id}] owner missing HAND_RESULT. Events: {owner.log.types()}"
    )
    assert joiner.log.has_type("HAND_RESULT"), (
        f"[{table_id}] joiner missing HAND_RESULT. Events: {joiner.log.types()}"
    )


def assert_event_ordering(player, table_id: str) -> None:
    types = player.log.types()
    assert "BLINDS_POSTED" in types, f"[{table_id}] no BLINDS_POSTED in log"
    assert "HAND_RESULT" in types, f"[{table_id}] no HAND_RESULT in log"
    bp_idx = types.index("BLINDS_POSTED")
    hr_idx = types.index("HAND_RESULT")
    if bp_idx >= hr_idx:
        from simulation.debug.report import format_ordering_failure
        raise AssertionError(
            format_ordering_failure(player, "BLINDS_POSTED", "HAND_RESULT", table_id)
        )


def assert_no_errors(*players, table_id: str) -> None:
    for player in players:
        errors = player.log.of_type("ERROR")
        assert not errors, (
            f"[{table_id}] unexpected ERROR events: {[e.payload for e in errors]}"
        )


def assert_spectator_isolation(spectator, expected_table_id: str) -> None:
    assert not spectator.log.has_type("CARDS_DEALT"), (
        f"Spectator on table {expected_table_id} received CARDS_DEALT — "
        f"hole cards leaked to spectator. Sequence: {spectator.log.types()}"
    )
    for event in spectator.log.all():
        tid = event.payload.get("table_id")
        if tid is not None and tid != expected_table_id:
            from simulation.debug.report import format_leakage_failure
            raise AssertionError(
                format_leakage_failure(
                    spectator, expected_table_id, event.type, tid, event.payload
                )
            )


def assert_all_results_passed(results: list[TableScenarioResult]) -> None:
    from simulation.debug.summary import LoadLiteSummary
    LoadLiteSummary(results).assert_all_passed()
