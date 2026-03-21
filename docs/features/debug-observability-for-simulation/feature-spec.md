# Feature Spec — debug-observability-for-simulation

> Agent: Product Manager
> Gate: Feature Spec (Gate 1)
> Status: APPROVED

---

## 1. Feature Goal

When a simulation scenario fails today, the diagnostic output is a raw Python `AssertionError` with a message like:

```
AssertionError: 'HAND_RESULT' not received within 30 messages.
Types received: ['STATE_SNAPSHOT', 'BLINDS_POSTED', 'PLAYER_ACTED', ...]
```

This tells you *that* it failed but not *why*, *where it got stuck*, *which client was waiting*, *what the other clients saw*, or *what state the table was in*. For load-lite concurrent runs with 3 tables and 6+ clients, it is completely opaque.

This feature adds **lightweight, bounded, CI-safe debug output** for simulation failures. The output must be:

- **Compact** — a few dozen lines maximum per scenario, not megabytes
- **Structured** — machine-readable enough to parse but human-readable enough to scan
- **Failure-focused** — full detail on failure; minimal noise on success
- **Safe** — hole cards are never exposed in spectator-scoped output; debug does not weaken hidden-card guarantees

The goal is to answer, from a single pytest output block on failure:
> *What happened, in which table, in which order, which client saw what, where it got stuck, and what the final state was before it failed.*

---

## 2. Debugging Pain Points This Feature Solves

| Pain point | Current state | After this feature |
|-----------|---------------|-------------------|
| `drain_until` timeout gives no context | Prints only the types list; no event payloads, no other client logs | Failure snapshot includes last N events with key payload fields per client |
| Load-lite failure doesn't show which table | Thread exception propagates as a `TableScenarioResult(error=str(exc))` with no context about other tables | `LoadLiteSummary` printed on failure lists all tables, their progress, and which one(s) failed |
| Stuck scenario gives no "last known state" | `AssertionError` with partial type list | Stuck diagnostic shows last event received per client, elapsed time, and which drain call was blocking |
| Event ordering violations are hard to inspect | `assert bp_idx < hr_idx` with just two indices | Ordering failure prints the full ordered type sequence with positions highlighted |
| Cross-table leakage is hard to reproduce | Assertion error names the event type but not the sequence that led to it | Leakage report shows spectator's full type sequence and the offending event's payload |
| Reconnect failures are context-free | No context about reserve_until, elapsed time, or PLAYER_STATUS events | Reconnect failure shows PLAYER_STATUS payload, reserve_until, and elapsed time at assertion |

---

## 3. Scope

### In scope (M0)

- `simulation/debug/` package with:
  - `snapshot.py` — captures per-client debug state at any point
  - `report.py` — formats failure reports, ordering reports, leakage reports, stuck diagnostics
  - `summary.py` — compact per-table and per-run summaries (for load-lite)
- Enriched `drain_until` failure messages (via a new `drain_until_or_report` helper or by enriching the existing `AssertionError`)
- `LoadLiteSummary` that aggregates all `TableScenarioResult` objects into a concise failure block
- Integration hooks into:
  - `simulation/load_lite/assertions.py` (richer failure messages)
  - `simulation/client.py` (optional: richer `drain_until` failure)
  - `tests/test_load_lite.py` and `tests/test_simulation_scenarios.py` (optional: pytest `--tb` friendliness)

### Out of scope

- Production logging, metrics, dashboards, or monitoring infrastructure
- Persisting debug output to files during normal CI runs (optional structured text dump is deferred)
- Distributed tracing or OpenTelemetry
- Log aggregation (ELK, Datadog, etc.)
- UI or mobile client diagnostic tools
- Performance profiling or flame graphs
- Any change to `poker_engine/` or `backend/`
- Any change to gameplay rules
- Integration with external error tracking services

---

## 4. Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC-01 | When `drain_until` times out, the `AssertionError` includes: (a) the target event type, (b) the full types sequence seen so far, (c) the last 5 events with their key payload fields (truncated), (d) which client (`phone`/`display_name`) was waiting |
| AC-02 | When a load-lite scenario fails, `assert_all_results_passed` prints a `LoadLiteSummary` block that lists every table with its `passed` flag, event count, last event type, and error message (if any) |
| AC-03 | When an ordering assertion fails (`assert_event_ordering`), the error includes the full ordered type sequence with the positions of the out-of-order events highlighted |
| AC-04 | When a spectator isolation assertion fails (`assert_spectator_isolation`), the error includes the spectator's full event type sequence and the offending event's type, table_id, and key payload fields |
| AC-05 | A `ScenarioSnapshot` can be captured at any point in a scenario and printed in ≤ 30 lines (compact format) |
| AC-06 | A `ClientSummary` for any `SimulatedClient` lists: display_name, phone, event count, event type sequence, last 3 events with payload excerpts |
| AC-07 | Debug output never exposes hole cards (`your_cards` payload) outside the owning player's `ClientSummary`; spectator summaries mask any `your_cards` field |
| AC-08 | Debug output is always-on for failures and silent on passing tests (no extra stdout on green runs) |
| AC-09 | Adding debug output does not increase the runtime of any existing test by more than 50 ms |
| AC-10 | All 200 existing tests continue to pass after this feature is implemented |
| AC-11 | The `simulation/debug/` package has zero imports from `poker_engine/` or `backend/` |
| AC-12 | A `stuck_diagnostic` helper produces a "last known position" report: last event type per client, which `drain_until` call was blocking, and elapsed seconds at the point of failure |

---

## 5. Design Questions (Resolved)

| # | Question | Resolution |
|---|----------|------------|
| Q1 | What exact debug artifacts should be produced for a failed scenario? | A `FailureReport` printed to stderr: (a) scenario name, (b) `ClientSummary` per involved client, (c) highlighted ordering or leakage details if applicable, (d) stuck diagnostic if drain timed out |
| Q2 | What exact per-table and per-client summaries are needed? | `TableSummary`: table_id, players list, event count, last event, passed/failed. `ClientSummary`: display_name, phone, event count, type sequence, last 3 events with truncated payloads |
| Q3 | Should debug capture be always-on, failure-only, or configurable? | Always-on capture (EventLog already captures everything); formatted output only on failure. No runtime cost for capture; formatting cost only on failure path |
| Q4 | How will hidden-card safety be preserved in debug output? | `your_cards` and `hand` fields in payloads are masked to `"<hidden>"` in any output associated with spectators or other-player contexts. Player-scoped summaries show own `your_cards` unmasked |
| Q5 | How will stuck scenarios produce actionable diagnostics? | `stuck_diagnostic(clients, drain_target, elapsed)` captures: last event per client, whether each client's log is empty, the expected next event type, elapsed seconds |
| Q6 | How will concurrent load-lite runs be summarized? | `LoadLiteSummary(results)` prints a table: index, table_id, passed, event_count, last_event, error_excerpt. ≤ 10 lines total for a 3-table run |
| Q7 | What runtime and output-size budget is acceptable for CI? | ≤ 50 ms overhead per test; ≤ 30 lines per `ClientSummary`; ≤ 10 lines for `LoadLiteSummary`; zero output on green runs |

---

## 6. Dependencies

| Dependency | Kind | Status |
|-----------|------|--------|
| `simulation.event_log.EventLog` | Existing — read `_events`, `types()`, `all()` | Available |
| `simulation.client.SimulatedClient` | Existing — `log`, `phone`, `display_name` | Available |
| `simulation.load_lite.orchestrator.TableScenarioResult` | Existing | Available |
| `simulation.load_lite.assertions` | Existing — enhance failure messages | Available |
| `dataclasses`, `textwrap`, `time` (stdlib) | No new dependencies | Available |

---

## 7. Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | Debug output in passing tests adds noise to CI logs | Medium | All formatting is failure-path only; `EventLog` capture is zero-cost on the happy path |
| R2 | `your_cards` leak to spectator debug output | High | Explicit masking in `ClientSummary` for spectator role; always mask `your_cards` in cross-client summaries |
| R3 | Failure reports become too long, making CI output unreadable | Medium | Hard caps: ≤ 30 lines per `ClientSummary`, ≤ 5 events with payloads, payload truncation at 120 chars |
| R4 | Debug helpers import from `backend/` or `poker_engine/`, breaking isolation | Medium | `simulation/debug/` has an explicit import boundary; no `backend.*` or `poker_engine.*` imports |
| R5 | Nondeterministic content in failure reports causes flaky test output | Low | Payload truncation is deterministic; type sequences are ordered by receipt time (already deterministic within a client's log) |
