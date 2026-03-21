"""
Unit tests for simulation/debug/ package.

Verifies:
  - ClientSummary capture, masking, truncation, format
  - ScenarioSnapshot capture and format
  - stuck_diagnostic output
  - format_ordering_failure annotated output
  - format_leakage_failure output
  - LoadLiteSummary format and assert_all_passed
  - drain_until enriched AssertionError
  - assert_spectator_isolation enriched AssertionError
  - assert_event_ordering enriched AssertionError
  - Hidden-card safety (spectator masked, player unmasked)
  - Absence of output on passing paths
"""
from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock

import pytest

from simulation.debug import (
    ClientSummary,
    ScenarioSnapshot,
    FailureReport,
    LoadLiteSummary,
    stuck_diagnostic,
    format_ordering_failure,
    format_leakage_failure,
)
from simulation.event_log import EventLog
from simulation.load_lite.orchestrator import TableScenarioResult


# ---------------------------------------------------------------------------
# Helpers to build mock clients and event logs
# ---------------------------------------------------------------------------

def _make_client(display_name: str = "Alice", phone: str = "+15550001001") -> MagicMock:
    client = MagicMock()
    client.display_name = display_name
    client.phone = phone
    client.log = EventLog()
    return client


def _push_event(log: EventLog, event_type: str, payload: dict | None = None) -> None:
    log.append({"type": event_type, "payload": payload or {}, "seq": 0, "ts": 0.0})


# ---------------------------------------------------------------------------
# 3. ClientSummary tests
# ---------------------------------------------------------------------------

def test_client_summary_basic_capture():
    client = _make_client()
    for t in ["STATE_SNAPSHOT", "BLINDS_POSTED", "HAND_RESULT"]:
        _push_event(client.log, t)
    summary = ClientSummary.from_client(client)
    assert summary.event_count == 3
    assert summary.type_sequence == ["STATE_SNAPSHOT", "BLINDS_POSTED", "HAND_RESULT"]
    assert len(summary.tail_events) == 3


def test_client_summary_tail_truncation():
    client = _make_client()
    for i in range(20):
        _push_event(client.log, f"EVT_{i}")
    summary = ClientSummary.from_client(client, tail=5)
    assert len(summary.tail_events) == 5
    # Last 5 events are EVT_15 through EVT_19
    assert summary.tail_events[0][0] == "EVT_15"
    assert summary.tail_events[-1][0] == "EVT_19"


def test_client_summary_payload_truncation():
    client = _make_client()
    long_payload = {"key": "x" * 200}
    _push_event(client.log, "SOME_EVENT", long_payload)
    summary = ClientSummary.from_client(client, tail=1)
    _, payload_str = summary.tail_events[0]
    assert len(payload_str) <= 121  # 120 chars + ellipsis


def test_client_summary_spectator_masks_your_cards():
    client = _make_client()
    _push_event(client.log, "CARDS_DEALT", {"your_cards": [{"rank": "A", "suit": "S"}]})
    summary = ClientSummary.from_client(client, is_spectator=True, tail=1)
    _, payload_str = summary.tail_events[0]
    assert "<hidden>" in payload_str
    assert "rank" not in payload_str or "A" not in payload_str


def test_client_summary_player_not_masked():
    client = _make_client()
    _push_event(client.log, "CARDS_DEALT", {"your_cards": [{"rank": "A", "suit": "S"}]})
    summary = ClientSummary.from_client(client, is_spectator=False, tail=1)
    _, payload_str = summary.tail_events[0]
    assert "<hidden>" not in payload_str
    assert "A" in payload_str


def test_client_summary_format_line_count():
    client = _make_client()
    for t in ["STATE_SNAPSHOT", "BLINDS_POSTED", "TURN_CHANGED", "HAND_RESULT"]:
        _push_event(client.log, t)
    formatted = ClientSummary.from_client(client).format()
    lines = formatted.split("\n")
    assert len(lines) <= 30


def test_client_summary_empty_log():
    client = _make_client()
    summary = ClientSummary.from_client(client)
    assert summary.event_count == 0
    assert summary.type_sequence == []
    assert summary.tail_events == []
    # format() must not raise
    formatted = summary.format()
    assert "no events" in formatted


# ---------------------------------------------------------------------------
# 4. stuck_diagnostic tests
# ---------------------------------------------------------------------------

def test_stuck_diagnostic_basic():
    c1 = _make_client("Alice")
    c2 = _make_client("Bob")
    _push_event(c1.log, "BLINDS_POSTED")
    _push_event(c2.log, "STATE_SNAPSHOT")
    out = stuck_diagnostic([c1, c2], drain_target="HAND_RESULT", elapsed_seconds=12.3)
    assert "HAND_RESULT" in out
    assert "12.3" in out
    assert "Alice" in out
    assert "Bob" in out
    assert "'BLINDS_POSTED'" in out
    assert "'STATE_SNAPSHOT'" in out


def test_stuck_diagnostic_empty_log():
    c = _make_client("Alice")
    out = stuck_diagnostic([c], drain_target="HAND_RESULT", elapsed_seconds=5.0)
    assert "(no events)" in out


def test_stuck_diagnostic_spectator_label():
    c1 = _make_client("Owner")
    c2 = _make_client("Spectator")
    _push_event(c1.log, "HAND_RESULT")
    out = stuck_diagnostic([c1, c2], drain_target="HAND_RESULT", elapsed_seconds=1.0,
                           spectator_indices=[1])
    assert "[spectator]" in out


# ---------------------------------------------------------------------------
# 5. format_ordering_failure tests
# ---------------------------------------------------------------------------

def test_format_ordering_failure_highlights_positions():
    client = _make_client()
    for t in ["STATE_SNAPSHOT", "HAND_RESULT", "BLINDS_POSTED"]:
        _push_event(client.log, t)
    out = format_ordering_failure(client, "BLINDS_POSTED", "HAND_RESULT")
    assert "ORDERING FAILURE" in out
    assert ">>>" in out
    # Both target events must be highlighted
    assert ">>>BLINDS_POSTED<<<" in out
    assert ">>>HAND_RESULT<<<" in out


def test_format_ordering_failure_includes_table_id():
    client = _make_client()
    _push_event(client.log, "HAND_RESULT")
    _push_event(client.log, "BLINDS_POSTED")
    out = format_ordering_failure(client, "BLINDS_POSTED", "HAND_RESULT", table_id="tbl-42")
    assert "tbl-42" in out


def test_format_ordering_failure_line_count():
    client = _make_client()
    for t in ["A", "B", "C"]:
        _push_event(client.log, t)
    out = format_ordering_failure(client, "A", "C")
    assert len(out.split("\n")) <= 3


# ---------------------------------------------------------------------------
# 6. format_leakage_failure tests
# ---------------------------------------------------------------------------

def test_format_leakage_failure_contains_required_fields():
    spectator = _make_client("Spectator")
    _push_event(spectator.log, "COMMUNITY_CARDS")
    out = format_leakage_failure(
        spectator,
        expected_table_id="table-A",
        offending_event_type="COMMUNITY_CARDS",
        offending_table_id="table-B",
        offending_payload={"table_id": "table-B"},
    )
    assert "table-A" in out
    assert "table-B" in out
    assert "COMMUNITY_CARDS" in out
    assert "CROSS-TABLE LEAKAGE" in out


def test_format_leakage_failure_payload_truncation():
    spectator = _make_client("Spectator")
    big_payload = {"cards": ["2S"] * 100}
    out = format_leakage_failure(
        spectator, "t1", "EVT", "t2", big_payload
    )
    # The payload representation in the output must be bounded
    lines = out.split("\n")
    payload_line = [l for l in lines if "payload" in l.lower()][0]
    assert len(payload_line) <= 200  # generous bound; real cap is 120 + overhead


def test_format_leakage_failure_spectator_sequence_present():
    spectator = _make_client("Spectator")
    for t in ["STATE_SNAPSHOT", "BLINDS_POSTED", "COMMUNITY_CARDS"]:
        _push_event(spectator.log, t)
    out = format_leakage_failure(spectator, "t1", "EVT", "t2", {})
    assert "STATE_SNAPSHOT" in out
    assert "BLINDS_POSTED" in out


# ---------------------------------------------------------------------------
# 7. LoadLiteSummary tests
# ---------------------------------------------------------------------------

def _make_result(idx: int, passed: bool, events=None, error=None) -> TableScenarioResult:
    return TableScenarioResult(
        table_index=idx,
        table_id=f"table-{idx}",
        passed=passed,
        error=error,
        event_types=events or ["STATE_SNAPSHOT", "BLINDS_POSTED", "HAND_RESULT"],
    )


def test_load_lite_summary_all_passed():
    results = [_make_result(i, True) for i in range(3)]
    summary = LoadLiteSummary(results)
    formatted = summary.format()
    assert "3 tables, 0 failed" in formatted
    summary.assert_all_passed()  # must not raise


def test_load_lite_summary_one_failed():
    results = [
        _make_result(0, True),
        _make_result(1, False, error="something went wrong"),
        _make_result(2, True),
    ]
    summary = LoadLiteSummary(results)
    with pytest.raises(AssertionError) as exc_info:
        summary.assert_all_passed()
    msg = str(exc_info.value)
    assert "FAIL" in msg
    assert "1 failed" in msg
    assert "something" in msg


def test_load_lite_summary_line_count():
    results = [_make_result(i, True) for i in range(3)]
    formatted = LoadLiteSummary(results).format()
    assert len(formatted.split("\n")) <= 10


def test_load_lite_summary_empty_event_types():
    result = TableScenarioResult(
        table_index=0, table_id="t0", passed=True, error=None, event_types=[]
    )
    formatted = LoadLiteSummary([result]).format()
    assert "\u2014" in formatted or "—" in formatted  # dash for empty last_event


# ---------------------------------------------------------------------------
# 8. drain_until enrichment tests
# ---------------------------------------------------------------------------

def test_drain_until_failure_includes_client_summary():
    """
    drain_until raises AssertionError containing ClientSummary output.
    Uses a mock _ws that returns one non-matching event then causes the
    loop to exhaust, triggering the enriched failure path.
    """
    from simulation.client import SimulatedClient

    # Build a real SimulatedClient but mock its _ws to return a controlled event
    client = SimulatedClient.__new__(SimulatedClient)
    client.phone = "+15599991001"
    client.display_name = "DebugTestUser"
    client.token = "fake-token"
    client.user_id = "user-1"
    client.log = EventLog()

    # Seed the log with one event so ClientSummary has something to show
    _push_event(client.log, "STATE_SNAPSHOT")

    # Mock _ws to return one PLAYER_STATUS message (not HAND_RESULT)
    ws_mock = MagicMock()
    ws_mock.receive_json.return_value = {
        "type": "PLAYER_STATUS", "payload": {}, "seq": 1, "ts": 0.0
    }
    client._ws = ws_mock

    with pytest.raises(AssertionError) as exc_info:
        client.drain_until("HAND_RESULT", max_msgs=1)

    msg = str(exc_info.value)
    assert "HAND_RESULT" in msg
    assert "DebugTestUser" in msg  # ClientSummary includes display_name
    assert "STATE_SNAPSHOT" in msg  # type sequence visible


def test_drain_until_success_produces_no_output(capsys):
    """drain_until success writes nothing to stdout/stderr."""
    from simulation.client import SimulatedClient

    client = SimulatedClient.__new__(SimulatedClient)
    client.phone = "+15599992001"
    client.display_name = "DebugTestUser2"
    client.token = "fake-token"
    client.user_id = "user-2"
    client.log = EventLog()

    ws_mock = MagicMock()
    ws_mock.receive_json.return_value = {
        "type": "STATE_SNAPSHOT", "payload": {}, "seq": 1, "ts": 0.0
    }
    client._ws = ws_mock

    result = client.drain_until("STATE_SNAPSHOT", max_msgs=5)
    assert result["type"] == "STATE_SNAPSHOT"

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---------------------------------------------------------------------------
# 9. assert_spectator_isolation enrichment tests
# ---------------------------------------------------------------------------

def test_assert_spectator_isolation_leakage_has_full_context():
    from simulation.load_lite.assertions import assert_spectator_isolation
    spectator = _make_client("Spectator")
    _push_event(spectator.log, "COMMUNITY_CARDS", {"table_id": "other-table"})
    with pytest.raises(AssertionError) as exc_info:
        assert_spectator_isolation(spectator, "expected-table")
    msg = str(exc_info.value)
    assert "CROSS-TABLE LEAKAGE" in msg
    assert "other-table" in msg
    assert "expected-table" in msg


def test_assert_spectator_isolation_cards_dealt_clear_message():
    from simulation.load_lite.assertions import assert_spectator_isolation
    spectator = _make_client("Spectator")
    _push_event(spectator.log, "CARDS_DEALT", {"your_cards": []})
    with pytest.raises(AssertionError) as exc_info:
        assert_spectator_isolation(spectator, "table-X")
    msg = str(exc_info.value)
    assert "CARDS_DEALT" in msg


# ---------------------------------------------------------------------------
# 10. assert_event_ordering enrichment tests
# ---------------------------------------------------------------------------

def test_assert_event_ordering_out_of_order_annotated():
    from simulation.load_lite.assertions import assert_event_ordering
    player = _make_client("Player")
    # HAND_RESULT before BLINDS_POSTED — wrong order
    _push_event(player.log, "HAND_RESULT")
    _push_event(player.log, "BLINDS_POSTED")
    with pytest.raises(AssertionError) as exc_info:
        assert_event_ordering(player, "table-Z")
    msg = str(exc_info.value)
    assert "ORDERING FAILURE" in msg
    assert ">>>" in msg


# ---------------------------------------------------------------------------
# 11. Hidden-card safety tests
# ---------------------------------------------------------------------------

def test_spectator_debug_output_never_exposes_raw_hole_cards():
    spectator = _make_client("Spectator")
    # Simulate a hypothetical server bug where CARDS_DEALT is sent to spectator
    _push_event(spectator.log, "CARDS_DEALT", {
        "your_cards": [{"rank": "A", "suit": "S"}, {"rank": "K", "suit": "H"}]
    })
    summary = ClientSummary.from_client(spectator, is_spectator=True, tail=5)
    formatted = summary.format()
    assert "<hidden>" in formatted
    # Raw rank/suit values must not appear in spectator output
    # (they are nested under "your_cards" which is masked entirely)
    assert '"rank": "A"' not in formatted
    assert '"suit": "S"' not in formatted


def test_hand_field_masked_for_spectators():
    spectator = _make_client("Spectator")
    _push_event(spectator.log, "STATE_SNAPSHOT", {
        "hand": {"community_cards": [{"rank": "2", "suit": "S"}]}
    })
    summary = ClientSummary.from_client(spectator, is_spectator=True, tail=1)
    _, payload_str = summary.tail_events[0]
    assert "<hidden>" in payload_str


def test_player_summary_shows_own_cards():
    player = _make_client("Player")
    _push_event(player.log, "CARDS_DEALT", {
        "your_cards": [{"rank": "A", "suit": "S"}]
    })
    summary = ClientSummary.from_client(player, is_spectator=False, tail=1)
    _, payload_str = summary.tail_events[0]
    assert "<hidden>" not in payload_str
    assert "A" in payload_str


# ---------------------------------------------------------------------------
# 12. Output absence on green runs
# ---------------------------------------------------------------------------

def test_load_lite_summary_no_output_on_success(capsys):
    results = [_make_result(i, True) for i in range(3)]
    summary = LoadLiteSummary(results)
    summary.assert_all_passed()  # no exception
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
