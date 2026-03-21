# QA Test Plan — debug-observability-for-simulation

> Agent: Senior QA Reviewer
> Gate: QA Review (Gate 3)
> Status: APPROVED

---

## 1. Scope

This plan covers the `simulation/debug/` package and its integration into `simulation/client.py` and `simulation/load_lite/assertions.py`. It verifies that:

- Debug output is correct and useful on failure
- Debug output is absent on success
- Hidden-card safety is preserved in all debug output
- Output is bounded to acceptable sizes
- All 200 existing tests continue to pass

---

## 2. Test File

`tests/test_debug_observability.py` — unit tests for the debug package.

---

## 3. `ClientSummary` Unit Tests

### 3.1 Basic capture

**Setup**: Create a `SimulatedClient` mock with a pre-populated `EventLog`.

**Test**: `ClientSummary.from_client(client)` returns a summary with:
- `event_count` == number of events in the log
- `type_sequence` == `log.types()`
- `tail_events` contains at most 5 entries

**Pass condition**: All fields match the EventLog contents.

### 3.2 Tail truncation

**Setup**: EventLog with 20 events.

**Test**: `ClientSummary.from_client(client, tail=5).tail_events` has exactly 5 entries, corresponding to the last 5 events.

**Pass condition**: `len(tail_events) == 5`.

### 3.3 Payload truncation

**Setup**: Event with a payload that serialises to > 120 characters.

**Test**: The corresponding entry in `tail_events` has its payload string truncated to ≤ 121 characters (120 + "…").

**Pass condition**: `len(payload_str) <= 121`.

### 3.4 Spectator masking — `your_cards`

**Setup**: EventLog with a `CARDS_DEALT` event whose payload contains `{"your_cards": [{"rank": "A", "suit": "S"}]}`.

**Test**: `ClientSummary.from_client(client, is_spectator=True)` — the `tail_events` entry for `CARDS_DEALT` must show `"<hidden>"` for the `your_cards` value.

**Failure mode**: `"A"` or `"S"` appears in the payload string → hidden-card leak.

### 3.5 Player NOT masked

**Setup**: Same as 3.4.

**Test**: `ClientSummary.from_client(client, is_spectator=False)` — `your_cards` appears unmasked.

**Pass condition**: `"<hidden>"` does NOT appear in the payload string.

### 3.6 `format()` line count

**Test**: `ClientSummary.from_client(client).format()` returns a string with ≤ 30 lines (newline count ≤ 29).

### 3.7 Empty log

**Setup**: EventLog with 0 events.

**Test**: `ClientSummary.from_client(client)` produces `event_count=0`, `type_sequence=[]`, `tail_events=[]`. `format()` does not raise.

---

## 4. `stuck_diagnostic` Unit Tests

### 4.1 Basic output

**Setup**: Two clients with event logs (3 events each). `drain_target="HAND_RESULT"`, `elapsed_seconds=12.3`.

**Test**: Output string contains `"HAND_RESULT"`, `"12.3"`, both client display names, and both last event types.

### 4.2 Empty log client

**Setup**: One client with 0 events.

**Test**: Output contains `"(no events)"` for the empty client.

### 4.3 Spectator label

**Setup**: Client at index 1 marked as spectator.

**Test**: Output contains `"[spectator]"` adjacent to that client's name.

---

## 5. `format_ordering_failure` Unit Tests

### 5.1 Highlighted positions

**Setup**: Type sequence `["STATE_SNAPSHOT", "HAND_RESULT", "BLINDS_POSTED"]`.

**Test**: Output contains `">>>"` around both `BLINDS_POSTED` and `HAND_RESULT` entries, with their respective indices shown.

### 5.2 Normal ordering (should not be called in practice)

**Setup**: Type sequence `["BLINDS_POSTED", "HAND_RESULT"]`.

**Test**: Output still produces a string without raising. (This function formats; it doesn't validate — the caller has already determined there's an ordering problem.)

### 5.3 Line count

**Test**: Output has ≤ 3 lines.

---

## 6. `format_leakage_failure` Unit Tests

### 6.1 Contains all required fields

**Setup**: `expected_table_id="table-A"`, `offending_table_id="table-B"`, `offending_event_type="COMMUNITY_CARDS"`.

**Test**: Output contains `"table-A"`, `"table-B"`, `"COMMUNITY_CARDS"`.

### 6.2 Payload truncation

**Setup**: `offending_payload={"cards": ["2S"] * 100}` (long payload).

**Test**: Output payload representation is ≤ 121 characters.

### 6.3 Spectator sequence present

**Setup**: Spectator with 5-event log.

**Test**: Output contains the spectator's type sequence.

---

## 7. `LoadLiteSummary` Unit Tests

### 7.1 All passed

**Setup**: 3 `TableScenarioResult` objects with `passed=True`.

**Test**: `summary.format()` contains "3 tables, 0 failed". `summary.assert_all_passed()` does not raise.

### 7.2 One failed

**Setup**: 3 results, one with `passed=False, error="something went wrong"`.

**Test**: `summary.assert_all_passed()` raises `AssertionError`. The error message contains "FAIL" and "1 failed". It also contains an excerpt of the error string.

### 7.3 Line count

**Test**: `summary.format()` has ≤ 10 lines for a 3-table run.

### 7.4 Empty event_types

**Setup**: Result with `event_types=[]`.

**Test**: `summary.format()` shows "—" for last_event, does not raise.

---

## 8. `drain_until` Enrichment Tests

### 8.1 Failure message includes `ClientSummary`

**Setup**: Mock a `SimulatedClient` whose `drain_until` times out (use `max_msgs=1` on a log that won't produce the target type).

**Test**: The raised `AssertionError` message contains:
- The target event type string
- The client's `display_name`
- The client's type sequence

**Approach**: `pytest.raises(AssertionError)` captures the error; assert on `str(exc_info.value)`.

### 8.2 Failure message does not appear on success

**Test**: A successful `drain_until` call returns normally with no debug output written to stdout/stderr.

---

## 9. `assert_spectator_isolation` Enrichment Tests

### 9.1 Leakage failure has full context

**Setup**: Build a `SimulatedClient` acting as spectator whose `EventLog` contains an event with `table_id="other-table"`. Call `assert_spectator_isolation(spectator, "expected-table")`.

**Test**: `AssertionError` message contains `"CROSS-TABLE LEAKAGE"`, `"other-table"`, `"expected-table"`, and the spectator's type sequence.

### 9.2 CARDS_DEALT failure has clear message

**Setup**: Spectator log contains a `CARDS_DEALT` event.

**Test**: `AssertionError` message contains `"CARDS_DEALT"` and the spectator's table_id.

---

## 10. `assert_event_ordering` Enrichment Tests

### 10.1 Out-of-order message has annotated sequence

**Setup**: Player log has `["HAND_RESULT", "BLINDS_POSTED"]` — HAND_RESULT before BLINDS_POSTED.

**Test**: `AssertionError` message contains `"ORDERING FAILURE"`, `">>>"` markers, and both positions.

---

## 11. Hidden-Card Safety Tests

### 11.1 Spectator debug output never contains raw hole card data

**Setup**: A `SimulatedClient` (spectator) whose log contains a synthetic `CARDS_DEALT` event with `your_cards` field populated (simulating a hypothetical bug where the server sent it).

**Test**: `ClientSummary.from_client(spectator, is_spectator=True).format()` — assert `"<hidden>"` appears and no rank/suit values from the `your_cards` payload appear literally.

### 11.2 `hand` field masked for spectators

**Setup**: Event with payload `{"hand": {"community_cards": [...]}}`.

**Test**: Spectator-scoped summary shows `"<hidden>"` for the `hand` key.

### 11.3 Player summary shows own cards

**Setup**: Player client whose log contains their own `CARDS_DEALT` with `your_cards=[{"rank":"A","suit":"S"}]`.

**Test**: `ClientSummary.from_client(player, is_spectator=False).format()` — `"A"` and `"S"` appear in the output (player can see their own cards).

---

## 12. Output Absence on Green Runs

### 12.1 Passing `drain_until` produces no extra output

**Test**: Capture `sys.stdout` and `sys.stderr` during a successful `drain_until` call (mocked). Assert both are empty.

### 12.2 `LoadLiteSummary.assert_all_passed` produces no output on success

**Test**: Call with all-passing results. Assert no output is written and no exception is raised.

---

## 13. Regression Gate

After all new tests pass:

```bash
py -m pytest
```

Must report **200 passed** (131 existing + 69 poker_engine + new tests from `test_debug_observability.py`).

The total will increase by the number of new debug observability tests.

---

## 14. Flakiness Risks

| # | Risk | Mitigation |
|---|------|------------|
| F1 | `ClientSummary` format changes break existing assertion error messages | No existing test asserts on the exact text of `drain_until` error messages — they assert on exception type only |
| F2 | Masking logic misses a new payload key added by the engine | `_SENSITIVE_KEYS` is a whitelist (`your_cards`, `hand`) — new keys are not masked unless explicitly added; this is conservative by design |
| F3 | `json.dumps` fails on non-serialisable payload values | `default=str` in `json.dumps` converts anything to its string repr — never raises |
| F4 | Line count varies by event sequence length | Tail is capped at `_MAX_TAIL_EVENTS=5`; line count is deterministic regardless of log size |

---

## 15. QA Sign-Off Conditions

- [ ] `ClientSummary` masking: spectator `your_cards` → `"<hidden>"`; player unmasked
- [ ] `stuck_diagnostic` output contains all required fields
- [ ] `format_ordering_failure` output contains annotated sequence with `>>>` markers
- [ ] `format_leakage_failure` output contains both table IDs and spectator sequence
- [ ] `LoadLiteSummary` failure triggers `AssertionError` with formatted table
- [ ] `drain_until` failure includes `ClientSummary` in error message
- [ ] All output-size budgets verified by unit tests (line count assertions)
- [ ] Zero output on passing tests (stdout/stderr capture tests pass)
- [ ] All 200 existing tests still pass after integration
- [ ] `simulation/debug/` has zero imports from `backend.*` or `poker_engine.*`
