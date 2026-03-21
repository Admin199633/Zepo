# Feature Spec: Deterministic Simulation Scenarios

**Feature ID:** deterministic-simulation-scenarios
**Status:** Proposed
**Author:** Product / Engineering
**Last Updated:** 2026-03-19

---

## 1. Feature Goal

The existing simulation harness (`simulation/scenarios/s1–s6`) drives a live FastAPI backend via `TestClient` and verifies that the server behaves correctly end-to-end. However, because the poker engine shuffles the deck with `secrets.SystemRandom()`, the cards dealt are different on every run. As a result, tests can only assert structural properties—"a `HAND_RESULT` event was received with `pot_total > 0`"—rather than asserting on specific card combinations, winners, or board runouts. This makes it impossible to test outcome-sensitive logic such as split pots, straight-flush beats full-house, or correct winner selection at showdown.

This feature introduces a deterministic deck-injection mechanism and a new sub-package of five scenario variants (`DS1–DS5`) that use pre-ordered decks to assert exact, repeatable outcomes. The mechanism requires no changes to production engine code: it monkey-patches the module-level name `poker_engine.engine.game_engine.fresh_shuffled_deck` inside a Python context manager that is only ever imported from test code. All existing nondeterministic scenarios (`s1–s6`) are unaffected and continue to run as before.

---

## 2. Scope

- A new `simulation/deck_control.py` module containing:
  - A `seeded_deck(cards: list[Card]) -> ContextManager` context manager that monkey-patches `poker_engine.engine.game_engine.fresh_shuffled_deck` to return the caller-supplied card list and restores the original function on exit.
  - A `build_cards(spec: list[str]) -> list[Card]` helper that parses short card strings like `"As"`, `"Kh"`, `"2c"` into `Card` objects.
- A new `simulation/scenarios/deterministic/` sub-package (with `__init__.py`) containing five deterministic scenario modules: `ds1_known_winner.py`, `ds2_known_board.py`, `ds3_reconnect_snapshot.py`, `ds4_spectator_deterministic.py`, `ds5_duplicate_request.py`.
- Each deterministic scenario is a standalone `run(http: TestClient) -> None` function consistent with the existing scenario contract, so it can be invoked by `ScenarioRunner` or directly in pytest.
- Integration of all five scenarios into whatever test runner or pytest conftest invokes s1–s6 today.
- Card dealing order is documented in each scenario's module docstring: for a 2-player hand, seats are sorted ascending; each player receives 2 cards from the top of the deck in seat order; community cards occupy deck positions `[4]`, `[5]`, `[6]` (flop), `[7]` (turn), `[8]` (river).

---

## 3. Out of Scope

- Changes to any file under `poker_engine/` or `backend/`. No production code is modified.
- Seeding via `random.seed()` or `secrets` replacement. The injection mechanism is pure monkey-patching of the module-level binding, not RNG state manipulation.
- Parameterized property-based testing (e.g., Hypothesis). Deterministic scenarios use hand-crafted card orders only.
- Multi-table or tournament-bracket scenarios.
- Modification of existing `s1–s6` scenarios. They remain nondeterministic.
- Persistence of deterministic decks to disk or any external configuration file.
- Performance or load testing.
- Deck injection in production or staging environments.

---

## 4. Acceptance Criteria

1. `simulation/deck_control.py` exists and is never imported from any file under `poker_engine/` or `backend/`.
2. `seeded_deck(cards)` is a context manager: on entry it replaces `poker_engine.engine.game_engine.fresh_shuffled_deck` with a callable that returns a shallow copy of `cards`; on exit (including exception paths) it restores the original function.
3. After `seeded_deck` exits, `poker_engine.engine.game_engine.fresh_shuffled_deck` is identical to the function object it held before the context manager was entered.
4. `build_cards` correctly parses all 52 possible short card strings (rank characters `2 3 4 5 6 7 8 9 T J Q K A`, suit characters `s h d c` case-insensitively) and raises `ValueError` on any unrecognized token.
5. **DS1** runs to completion without error, and the `HAND_RESULT` payload field `winner_id` matches the user ID of the player who was dealt the known-stronger hole cards, confirmed by the pre-ordered deck specification in the scenario.
6. **DS2** runs to completion without error; the community cards visible in `COMMUNITY_CARDS` events received by both players match exactly the ranks and suits specified in the deck order (flop at deck positions 4–6, turn at 7, river at 8).
7. **DS2** asserts the `HAND_RESULT` `winner_id` and `hand_description` (or equivalent payload field) against the expected showdown result derived from the pre-ordered deck.
8. **DS3** runs to completion without error; after a mid-hand disconnect and reconnect, the `STATE_SNAPSHOT` payload received by the reconnecting player contains the player's own entry in the `players` map and the `community_cards` list matches the cards dealt from the injected deck up to the point of reconnection.
9. **DS4** runs to completion without error; a spectator connected during an in-progress deterministic hand never receives a `CARDS_DEALT` event, and the `HAND_RESULT` event received by the spectator identifies the same winner as the one asserted by the two active players.
10. **DS5** runs to completion without error; when the same `request_id` is submitted twice by the same client, the server emits exactly one `PLAYER_ACTED` event for that action (no duplicate application of the action to the game state).
11. All five deterministic scenarios (`DS1–DS5`) are registered in the test suite so that `pytest` discovers and executes them; CI must report all five as passed.
12. All six existing nondeterministic scenarios (`s1–s6`) continue to pass without modification after this feature is merged.
13. Each deterministic scenario module contains a docstring specifying: (a) the exact deck order used, expressed as a list of short card strings, (b) the expected outcome being asserted, and (c) the seat-to-user assignment assumed.
14. `seeded_deck` is safe for sequential invocations within the same process: calling it a second time after the first context has exited produces a correctly injected deck and a correct restoration.

---

## 5. Dependencies

| Dependency | Type | Notes |
|---|---|---|
| `simulation/` package (existing) | Internal | `SimulatedClient`, `EventLog`, `ScenarioRunner`, `app_factory.make_test_client`, `helpers.setup_two_players` — all reused without modification. |
| `poker_engine.engine.game_engine` | Internal (read-only) | The module-level name `fresh_shuffled_deck` is monkey-patched by `deck_control.py`. The import binding is `from .deck import deal_cards, fresh_shuffled_deck` at line 22 of `game_engine.py`. |
| `poker_engine.engine.models.Card`, `Rank`, `Suit` | Internal (read-only) | Used by `build_cards` to construct typed card objects. |
| `poker_engine.engine.evaluator` | Internal (read-only) | Understanding of hand ranking categories (0 = High Card … 9 = Royal/Straight Flush) is required to select deck orders that produce unambiguous single winners. |
| `fastapi.testclient.TestClient` | Third-party | Same version used by existing scenarios. No new dependency. |
| Python `contextlib` or `unittest.mock.patch` | Standard library | Suitable for implementing the context manager in `deck_control.py`. |
| Python `unittest.mock` | Standard library | Optional alternative; `contextlib.contextmanager` with direct attribute assignment is preferred to avoid pulling in `mock` for non-mock purposes. |

---

## 6. Risks

**R1 — Deck position assumptions break on rule changes.**
If a house rule (e.g., straddle, defined in `poker_engine/rules/`) causes additional cards to be consumed from the deck before community cards are dealt, the positions assumed by DS2 (flop at `[4:7]`, turn at `[7]`, river at `[8]`) will be wrong and the scenario will assert against the wrong cards. Mitigation: deterministic scenarios must check community card content directly from received `COMMUNITY_CARDS` events rather than computing expected values from deck positions arithmetically — or they must explicitly configure tables with no house rules active.

**R2 — Monkey-patch leaked by test crash.**
If a scenario crashes inside the `seeded_deck` context without proper cleanup, subsequent scenarios in the same process may use the injected deck instead of a fresh shuffle. Mitigation: implement `seeded_deck` with a `try/finally` block (or `contextlib.contextmanager` with a `finally` clause) so restoration is unconditional. `ScenarioRunner.run()` already wraps each scenario in a try/except, but that does not replace the need for a `finally`-guarded restoration inside `deck_control.py` itself.

**R3 — Seat assignment is not deterministic across runs.**
`setup_two_players` creates users in a fixed order but seat assignment depends on join order and server-side seat allocation logic. If the server assigns seats non-deterministically, the player dealt the "known stronger" hole cards may vary. Mitigation: DS1–DS2 scenarios must verify the winner by inspecting the `CARDS_DEALT` payload received by each player, confirming which player holds which hole cards before asserting the winner, rather than relying on a fixed seat-to-user mapping.

**R4 — Hand evaluator tie-breaking produces unexpected split pots.**
If the pre-ordered deck is chosen carelessly and both players make the same best 5-card hand from the board plus hole cards, `HAND_RESULT` may contain two winners or a split pot, breaking a single-winner assertion. Mitigation: scenario authors must calculate expected hand ranks offline before writing assertions and choose deck orders that guarantee a strict ranking difference between the two players' best hands.

**R5 — `seeded_deck` is not thread-safe.**
If tests are run with `pytest-xdist` in parallel within the same process, two concurrent uses of `seeded_deck` could interfere with each other because they write to the same module-level attribute. Mitigation: document that deterministic scenarios must not run concurrently with each other or with any other scenario that starts a hand. A process-level lock or a pytest marker restricting parallelism is the recommended guard.

---

## 7. Open Questions (Resolved)

**Q1: How should the deck be made deterministic without modifying production code?**
Resolved: Monkey-patch the module-level name `poker_engine.engine.game_engine.fresh_shuffled_deck`. Because `game_engine.py` imports `fresh_shuffled_deck` with `from .deck import deal_cards, fresh_shuffled_deck` (a name binding in the `game_engine` module namespace), replacing `poker_engine.engine.game_engine.fresh_shuffled_deck` with a substitute callable causes `start_hand()` — which calls `fresh_shuffled_deck()` at line 93 — to call the substitute on the next invocation. No production file is touched.

**Q2: Where should the deck-control utilities live?**
Resolved: In a new `simulation/deck_control.py` module. This file is exclusively test infrastructure. It must never be imported by any module under `poker_engine/` or `backend/`. It may freely import from `poker_engine.engine.models` to construct typed `Card` objects.

**Q3: Should existing s1–s6 scenarios be converted to use deterministic decks?**
Resolved: No. `s1–s6` remain nondeterministic. Deterministic variants are additive, placed in a new `simulation/scenarios/deterministic/` sub-package. This preserves the value of the nondeterministic scenarios as regression tests for arbitrary card distributions and avoids any risk of regressions in s1–s6.

**Q4: How should scenarios assert outcomes without coupling to internal engine state?**
Resolved: Scenarios inspect only the JSON payloads of server-sent WebSocket events captured in `EventLog`. For winner assertions, scenarios read `HAND_RESULT.payload["winner_id"]` (and optionally `"hand_description"`). For board assertions, they read `COMMUNITY_CARDS` event payloads. For hole card confirmation, they read `CARDS_DEALT` payloads received by each player. No scenario imports or accesses `GameState`, `HandState`, or any other internal engine object.

**Q5: How is test isolation guaranteed between deterministic scenario invocations?**
Resolved: Via the `seeded_deck` context manager's `finally` block. On context entry, the original function reference is saved to a local variable. On exit (normal or exceptional), the module attribute is restored to that saved reference. Each scenario wraps its entire hand-driving logic inside a single `with seeded_deck(cards):` block so that the patch is active only for the duration of the scenario's hand and is removed before the next scenario begins.

---

## 8. Minimum Deterministic Scenarios

### DS1 — Two-Player Hand with a Known Winner

**Purpose:** Verify that the winner reported in `HAND_RESULT` matches the player who was dealt a provably stronger hand, end-to-end through the full server stack.

**Deck order:** Choose hole cards so that Player A holds a hand that beats Player B regardless of all community cards (e.g., Player A: `Ah As`, Player B: `2d 3c`; community: `7h 8d 9c Jd Ks`). With `Ah As` vs `2d 3c` on a rainbow board with no straight or flush completing for Player B, Player A's pair of aces beats Player B's king-high. Deck positions: `[0]`=Ah, `[1]`=2d, `[2]`=As, `[3]`=3c, `[4]`=7h, `[5]`=8d, `[6]`=9c, `[7]`=Jd, `[8]`=Ks.

**Setup:** `setup_two_players`, both join as players, both call/check every street (no folding), hand runs to showdown.

**Assertions:**
- `HAND_RESULT.payload["winner_id"]` equals the `user_id` of the player whose `CARDS_DEALT` payload contained `Ah` and `As`.
- `HAND_RESULT.payload["pot_total"]` equals the sum of the two blinds (since both players only call/check).
- Neither player received an `ERROR` event.

---

### DS2 — Known Board/Runout with Expected Showdown Result

**Purpose:** Verify that all five community cards are dealt in the correct order and that the engine evaluates the showdown correctly for a hand where the winning hand type is uniquely determined by the pre-ordered deck.

**Deck order:** Choose a runout that produces a clear best hand. Example: Player A: `Kh Kd`, Player B: `Qh Qd`; community: `Ks Qc 2h 3d 4s`. Player A makes three kings; Player B makes three queens. Deck positions: `[0]`=Kh, `[1]`=Qh, `[2]`=Kd, `[3]`=Qd, `[4]`=Ks, `[5]`=Qc, `[6]`=2h, `[7]`=3d, `[8]`=4s.

**Setup:** Same two-player setup as DS1, hand runs to showdown.

**Assertions:**
- First `COMMUNITY_CARDS` event payload contains exactly `[Ks, Qc, 2h]` (the flop) in that order.
- Second `COMMUNITY_CARDS` event payload contains `[3d]` (the turn).
- Third `COMMUNITY_CARDS` event payload contains `[4s]` (the river).
- `HAND_RESULT.payload["winner_id"]` equals the player who was dealt `Kh Kd`.
- `HAND_RESULT.payload` contains a field indicating "Three of a Kind" or a hand rank category of 3 (or the server's equivalent representation for three-of-a-kind).

---

### DS3 — Reconnect Scenario with Expected Snapshot Contents

**Purpose:** Verify that when a player disconnects mid-hand and reconnects, the `STATE_SNAPSHOT` they receive reflects the current board state consistent with the injected deck — i.e., any community cards dealt before the disconnect appear in the snapshot.

**Deck order:** Same as DS2 or any order where the flop has been dealt before the disconnect is triggered. The scenario drives the hand through `BLINDS_POSTED` and to the point where the flop `COMMUNITY_CARDS` event is broadcast, then disconnects one player.

**Setup:** Two players, both join as players. After `BLINDS_POSTED`, both players call the preflop action. After the flop `COMMUNITY_CARDS` event is received by the observer, the acting player disconnects.

**Assertions:**
- After reconnect, the reconnecting player receives `STATE_SNAPSHOT`.
- `STATE_SNAPSHOT.payload["players"]` contains the reconnecting player's `user_id`.
- `STATE_SNAPSHOT.payload["community_cards"]` is a non-empty list matching the flop cards from the injected deck (`[4:7]`).
- The observer received `PLAYER_STATUS{status=disconnected}` for the disconnected player before the reconnect.
- After reconnect, the observer receives `PLAYER_STATUS{status=reconnected}` or the hand continues without error.
- No `ERROR` event appears in either player's log.

---

### DS4 — Spectator Filtering Under Deterministic Conditions

**Purpose:** Under deterministic card dealing, verify that a spectator observes the correct community cards and the correct winner in `HAND_RESULT`, while still never receiving any player's hole cards via `CARDS_DEALT`.

**Deck order:** Use the DS1 or DS2 deck order. The key property is that the winner is known in advance.

**Setup:** Two players and one spectator. The spectator joins mid-hand (after `BLINDS_POSTED`) as a spectator. Both players call/check every street. The hand runs to showdown.

**Assertions:**
- Spectator never receives a `CARDS_DEALT` event at any point.
- Spectator receives all `COMMUNITY_CARDS` events (three events: flop, turn, river).
- Community cards in spectator's log match those in the two players' logs exactly (same rank/suit, same order).
- Spectator's `HAND_RESULT` event identifies the same `winner_id` as the players' `HAND_RESULT` events.
- Spectator receives `TURN_CHANGED` events for each action opportunity during the hand.
- No `ERROR` event appears in the spectator's log.

---

### DS5 — Duplicate Request with Explicit Expected Behavior

**Purpose:** Verify idempotency of player action submission: if the client sends the same `ACTION` message with the same `request_id` twice (simulating a network retry), the server applies the action exactly once and does not produce duplicate `PLAYER_ACTED` events or corrupt game state.

**Deck order:** Any order that guarantees the hand reaches at least one `TURN_CHANGED` event before ending (to give the test a natural action point). The DS1 deck order is sufficient.

**Setup:** Two players. After `BLINDS_POSTED`, wait for `TURN_CHANGED` targeting Player A. Player A sends an `ACTION` (e.g., `call`) twice with the same `request_id` in immediate succession before receiving any server response.

**Assertions:**
- Exactly one `PLAYER_ACTED` event is emitted by the server for the duplicated `request_id` (counted across both players' event logs).
- The game state continues to a valid next event (`TURN_CHANGED` for the next player, `COMMUNITY_CARDS`, or `HAND_RESULT`) without stalling.
- No `ERROR` event with an error code indicating state corruption appears in either player's log. (A single idempotency-acknowledgement response to the duplicate is acceptable if the server design supports it, but no second game state mutation may occur.)
- The hand eventually reaches `HAND_RESULT` without timing out the scenario loop.
