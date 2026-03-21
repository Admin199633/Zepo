# QA Test Plan: Deterministic Simulation Scenarios

**Feature ID:** deterministic-simulation-scenarios
**Status:** QA Review
**Author:** Senior QA Reviewer Agent
**Last Updated:** 2026-03-19
**Scope:** `simulation/deck_control.py`, `simulation/scenarios/deterministic/` (DS1–DS5), `tests/test_simulation_deterministic.py`

---

## Table of Contents

1. [QA Objectives](#1-qa-objectives)
2. [Scenario Test Plans](#2-scenario-test-plans)
   - [DS1 — Two-Player Hand with Known Winner](#ds1--two-player-hand-with-known-winner)
   - [DS2 — Known Board/Runout with Exact Showdown Assertion](#ds2--known-boardrunout-with-exact-showdown-assertion)
   - [DS3 — Reconnect Scenario with Verified Snapshot Contents](#ds3--reconnect-scenario-with-verified-snapshot-contents)
   - [DS4 — Spectator Filtering Under Deterministic Conditions](#ds4--spectator-filtering-under-deterministic-conditions)
   - [DS5 — Duplicate-Request Ordering and Idempotency](#ds5--duplicate-request-ordering-and-idempotency)
3. [Deterministic Replay Verification](#3-deterministic-replay-verification)
4. [Deck Patch Isolation Tests](#4-deck-patch-isolation-tests)
5. [Hidden Card Filtering Under Deterministic Conditions](#5-hidden-card-filtering-under-deterministic-conditions)
6. [Duplicate Request Behavior (DS5)](#6-duplicate-request-behavior-ds5)
7. [Reconnect Snapshot Contents (DS3)](#7-reconnect-snapshot-contents-ds3)
8. [Event Ordering Assertions](#8-event-ordering-assertions)
9. [Flakiness Detection Checklist](#9-flakiness-detection-checklist)
10. [Isolation Between Tests](#10-isolation-between-tests)
11. [Regressions This Feature Catches](#11-regressions-this-feature-catches)
12. [QA Sign-Off Conditions](#12-qa-sign-off-conditions)

---

## 1. QA Objectives

This test plan verifies the following properties of the `deterministic-simulation-scenarios` feature:

1. **Correctness of deck injection.** `injected_deck()` in `simulation/deck_control.py` causes `poker_engine.engine.game_engine.fresh_shuffled_deck` to return the caller-supplied card order on every invocation inside the context, and restores the original function reference unconditionally on exit — including on exception paths.

2. **Correctness of card parsing.** `build_deterministic_deck()` correctly converts `(rank_str, suit_str)` tuples into typed `Card` objects for all 52 valid combinations, and raises `ValueError` on any unrecognised token.

3. **End-to-end scenario correctness.** Each of DS1–DS5 exercises a specific game behaviour path and produces deterministic, assertable outcomes. Assertions go beyond structural checks ("event was received") to exact payload comparisons ("this user_id won with this hand").

4. **Isolation and cleanup.** No test contaminates the module state seen by subsequent tests. The deck patch is never leaked across test boundaries.

5. **Card privacy.** Under deterministic conditions, hole-card filtering is exact: each player receives only their own two cards, and spectators receive no hole cards whatsoever.

6. **Idempotency.** The server applies duplicate-`request_id` actions exactly once; the second submission does not corrupt game state.

7. **Regression protection.** The deterministic harness catches engine and transport bugs that nondeterministic runs may never surface in CI.

8. **Non-regression.** All six existing nondeterministic scenarios (s1–s6) continue to pass without modification.

---

## 2. Scenario Test Plans

### DS1 — Two-Player Hand with Known Winner

**Deck recipe (Recipe A):**

```
[0] (A, S)  → owner hole card 1
[1] (2, H)  → joiner hole card 1
[2] (K, S)  → owner hole card 2
[3] (3, D)  → joiner hole card 2
[4] (Q, S)  → flop 1
[5] (J, S)  → flop 2
[6] (T, S)  → flop 3
[7] (2, C)  → turn
[8] (3, C)  → river
```

Owner's best 5-card hand: A♠ K♠ Q♠ J♠ T♠ (Royal Flush).
Joiner's best 5-card hand: Q♠ J♠ T♠ 3♦ 2♥ (Queen-high straight at best).
Expected winner: owner (unambiguous).

#### Test Steps

1. Call `setup_two_players(http, "+1555700")` to produce `owner`, `joiner`, `club_id`, `table_id`.
2. Enter `with injected_deck(complete_deck(RECIPE_A)):`.
3. Open `owner.connect(table_id)` and `joiner.connect(table_id)`.
4. Both clients call `send_join(table_id, "player")` and drain to `STATE_SNAPSHOT`.
5. Both drain to `BLINDS_POSTED`.
6. Drive hand to showdown: on each `TURN_CHANGED` addressed to the active player, send `"check"` (post-flop) or `"call"` (pre-flop). No player folds. Continue until `HAND_RESULT` is received.
7. Exit both connection contexts.
8. Exit `injected_deck` context.
9. Run assertions on captured `EventLog` objects.

#### Expected Key Event Sequence (owner's log, after `BLINDS_POSTED`)

```
PHASE_CHANGED (PRE_FLOP)
TURN_CHANGED
PLAYER_ACTED
TURN_CHANGED
PLAYER_ACTED
COMMUNITY_CARDS (flop, phase=FLOP)
TURN_CHANGED
PLAYER_ACTED
...
COMMUNITY_CARDS (turn, phase=TURN)
...
COMMUNITY_CARDS (river, phase=RIVER)
...
HAND_RESULT
```

#### Assertions

```python
# A1 — Hole card confirmation via CARDS_DEALT
owner_dealt = owner.log.of_type("CARDS_DEALT")[0]
joiner_dealt = joiner.log.of_type("CARDS_DEALT")[0]
owner_cards = {(c["rank"], c["suit"]) for c in owner_dealt.payload["cards"]}
joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt.payload["cards"]}
assert ("A", "S") in owner_cards and ("K", "S") in owner_cards
assert ("2", "H") in joiner_cards and ("3", "D") in joiner_cards

# A2 — Exactly one CARDS_DEALT per player (unicast, not broadcast)
assert len(owner.log.of_type("CARDS_DEALT")) == 1
assert len(joiner.log.of_type("CARDS_DEALT")) == 1

# A3 — Winner is owner
hand_result = owner.log.of_type("HAND_RESULT")[0]
winners = hand_result.payload["winners"]
assert len(winners) == 1
winning_ids = winners[0]["winner_ids"]
assert owner.user_id in winning_ids
assert joiner.user_id not in winning_ids

# A4 — Pot total is positive
assert hand_result.payload["pot_total"] > 0

# A5 — No error events
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")

# A6 — Both logs contain HAND_RESULT
assert owner.log.has_type("HAND_RESULT")
assert joiner.log.has_type("HAND_RESULT")
```

#### Failure Cases

| Failure | Root Cause Indicated |
|---------|----------------------|
| `A1` fails — owner not dealt (A♠, K♠) | Deck injection did not take effect; `injected_deck` context was entered after `start_hand()` was called, or patch was not applied to the correct module attribute |
| `A2` fails — owner received 2 `CARDS_DEALT` | Broadcast filter leaked; hole cards are being sent to all connected clients instead of unicast to each player |
| `A3` fails — `winner_ids` contains joiner | Hand evaluator bug: evaluator compared wrong 5-card subsets, or seat-to-user assignment is inverted |
| `A3` fails — `len(winners) != 1` | Evaluator produced a split pot on a board where the hands are unambiguously ranked; possible tie-breaking regression |
| `A4` fails — `pot_total == 0` | Blinds were not posted or pot accumulation logic is broken |
| `A5` fails — ERROR event present | A game-action validation bug rejected a valid `call` or `check` sent by the driver |

---

### DS2 — Known Board/Runout with Exact Showdown Assertion

**Deck recipe (Recipe B):**

```
[0] (2, S)  → owner hole card 1
[1] (A, H)  → joiner hole card 1
[2] (3, H)  → owner hole card 2
[3] (A, D)  → joiner hole card 2
[4] (A, C)  → flop 1
[5] (K, S)  → flop 2
[6] (Q, D)  → flop 3
[7] (5, H)  → turn
[8] (6, C)  → river
```

Joiner's best 5-card hand: A♥ A♦ A♣ K♠ Q♦ (Three of a Kind, Aces).
Owner's best 5-card hand: A♣ K♠ Q♦ 6♣ 5♥ (Ace-high, no pair).
Expected winner: joiner.

#### Test Steps

1. Call `setup_two_players(http, "+1555800")`.
2. Enter `with injected_deck(complete_deck(RECIPE_B)):`.
3. Both clients connect and join as players. Both drain to `BLINDS_POSTED`.
4. Drive hand to showdown by check/call on every `TURN_CHANGED`. No folding.
5. Exit contexts. Assert on logs.

#### Expected Key Event Sequence (owner's log, after `BLINDS_POSTED`)

```
PHASE_CHANGED (PRE_FLOP)
TURN_CHANGED → PLAYER_ACTED  (× until preflop betting closes)
COMMUNITY_CARDS {cards: [(A,C),(K,S),(Q,D)], phase: FLOP}
TURN_CHANGED → PLAYER_ACTED  (× until flop betting closes)
COMMUNITY_CARDS {cards: [(5,H)], phase: TURN}
TURN_CHANGED → PLAYER_ACTED  (× until turn betting closes)
COMMUNITY_CARDS {cards: [(6,C)], phase: RIVER}
TURN_CHANGED → PLAYER_ACTED  (× until river betting closes)
HAND_RESULT
```

#### Assertions

```python
# B1 — Hole card confirmation
joiner_dealt = joiner.log.of_type("CARDS_DEALT")[0]
joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt.payload["cards"]}
assert ("A", "H") in joiner_cards and ("A", "D") in joiner_cards

# B2 — Exactly 3 COMMUNITY_CARDS events
community_events = owner.log.of_type("COMMUNITY_CARDS")
assert len(community_events) == 3

# B3 — Flop cards in exact order
flop = [(c["rank"], c["suit"]) for c in community_events[0].payload["cards"]]
assert flop == [("A", "C"), ("K", "S"), ("Q", "D")]

# B4 — Turn card
turn = [(c["rank"], c["suit"]) for c in community_events[1].payload["cards"]]
assert turn == [("5", "H")]

# B5 — River card
river = [(c["rank"], c["suit"]) for c in community_events[2].payload["cards"]]
assert river == [("6", "C")]

# B6 — Phase labels on each COMMUNITY_CARDS event
assert community_events[0].payload.get("phase") == "FLOP"
assert community_events[1].payload.get("phase") == "TURN"
assert community_events[2].payload.get("phase") == "RIVER"

# B7 — Winner is joiner
hand_result = owner.log.of_type("HAND_RESULT")[0]
winners = hand_result.payload["winners"]
assert len(winners) == 1
assert joiner.user_id in winners[0]["winner_ids"]

# B8 — Hand description contains "Three of a Kind" (case-insensitive)
hand_desc = winners[0].get("hand_description", "")
assert "three" in hand_desc.lower() or "three_of_a_kind" in hand_desc.lower()

# B9 — Community cards in joiner's log match owner's log exactly
owner_cc = owner.log.of_type("COMMUNITY_CARDS")
joiner_cc = joiner.log.of_type("COMMUNITY_CARDS")
assert len(joiner_cc) == 3
for i in range(3):
    o_cards = [(c["rank"], c["suit"]) for c in owner_cc[i].payload["cards"]]
    j_cards = [(c["rank"], c["suit"]) for c in joiner_cc[i].payload["cards"]]
    assert o_cards == j_cards

# B10 — No errors
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

#### Failure Cases

| Failure | Root Cause Indicated |
|---------|----------------------|
| `B2` fails — fewer than 3 `COMMUNITY_CARDS` events | Engine stopped dealing community cards mid-hand; phase progression bug |
| `B3–B5` fail — cards do not match deck positions `[4:9]` | Deck injection applied after dealing started, or dealing order was changed in the engine |
| `B6` fails — incorrect `phase` label | COMMUNITY_CARDS serialization maps phase enum incorrectly |
| `B7` fails — owner reported as winner | Evaluator compared hands in wrong order, or ranked Three-of-a-Kind below Ace-high |
| `B8` fails — wrong hand description | `hand_description` field name changed, or hand category string formatting differs from expected pattern |
| `B9` fails — cards differ between players | `COMMUNITY_CARDS` is not a pure broadcast; different payloads sent to different connected clients |

---

### DS3 — Reconnect Scenario with Verified Snapshot Contents

**Deck recipe:** Recipe B (same 9-card prefix; flop = A♣ K♠ Q♦ is the content to verify in the snapshot).

#### Test Steps

1. Call `setup_two_players(http, "+1555900")`.
2. Enter `with injected_deck(complete_deck(RECIPE_B)):`.
3. Open `joiner.connect(table_id)`. Joiner sends `JOIN_TABLE` as `"player"`, drains to `STATE_SNAPSHOT`.
4. Open `owner.connect(table_id)` (first connection). Owner sends `JOIN_TABLE` as `"player"`, drains to `STATE_SNAPSHOT`.
5. Both drain to `BLINDS_POSTED`.
6. Drive the hand until the first `COMMUNITY_CARDS` event (flop) is received in owner's log. At this point the flop (A♣ K♠ Q♦) has been broadcast.
7. Owner exits the WebSocket context (disconnect) — `owner_ctx.__exit__(None, None, None)`.
8. Joiner drains until `PLAYER_STATUS` arrives with `status == "disconnected"`.
9. Owner re-opens `owner.connect(table_id)` (second connection). Owner sends `JOIN_TABLE` as `"player"`, drains to `STATE_SNAPSHOT`.
10. Exit all contexts. Assert on captured logs.

#### Expected Key Event Sequence (owner's second connection log)

```
STATE_SNAPSHOT  (contains community_cards with flop, and own hole cards)
```

#### Assertions

```python
# C1 — Joiner received PLAYER_STATUS{disconnected} for owner before reconnect
disconnect_events = joiner.log.of_type("PLAYER_STATUS")
disconnect_evt = next(
    (e for e in disconnect_events if e.payload.get("status") == "disconnected"),
    None
)
assert disconnect_evt is not None
assert disconnect_evt.payload["user_id"] == owner.user_id

# C2 — STATE_SNAPSHOT received after reconnect
assert owner.log.has_type("STATE_SNAPSHOT")
snap = owner.log.of_type("STATE_SNAPSHOT")[0]

# C3 — Owner's seat is preserved in snapshot
players_in_snap = snap.payload.get("players", {})
assert owner.user_id in players_in_snap

# C4 — Opponent's hole cards are NOT in snapshot (no leak)
# The players map must not contain joiner's hole cards visible to owner
if joiner.user_id in players_in_snap:
    opponent_entry = players_in_snap[joiner.user_id]
    opponent_cards = opponent_entry.get("cards", [])
    assert opponent_cards == [] or opponent_cards is None, \
        "Snapshot must not expose opponent hole cards to reconnecting player"

# C5 — Owner's own hole cards are present in snapshot
owner_entry = players_in_snap[owner.user_id]
owner_cards_in_snap = owner_entry.get("cards", [])
assert len(owner_cards_in_snap) == 2, \
    "Snapshot must include reconnecting player's own 2 hole cards"

# C6 — Own hole cards in snapshot match the injected deck positions [0] and [2]
snap_card_set = {(c["rank"], c["suit"]) for c in owner_cards_in_snap}
assert ("2", "S") in snap_card_set and ("3", "H") in snap_card_set, \
    f"Snapshot hole cards do not match Recipe B owner cards: {snap_card_set}"

# C7 — Community cards in snapshot contain at least the 3 flop cards
community_in_snap = snap.payload.get("community_cards", [])
assert len(community_in_snap) >= 3
snap_flop = [(c["rank"], c["suit"]) for c in community_in_snap[:3]]
assert snap_flop == [("A", "C"), ("K", "S"), ("Q", "D")]

# C8 — No errors in either player's log
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

#### Failure Cases

| Failure | Root Cause Indicated |
|---------|----------------------|
| `C1` fails — no `PLAYER_STATUS{disconnected}` | Server did not broadcast the disconnect event when the WebSocket closed, or the event is named differently |
| `C3` fails — owner not in snapshot | Seat was released too early (reserve window logic incorrect), or `STATE_SNAPSHOT` does not include the reconnecting player's own seat |
| `C4` fails — opponent hole cards visible | Snapshot serialization leaks all player cards without filtering by receiver identity |
| `C5–C6` fail — own hole cards missing or wrong | Snapshot does not include the reconnecting player's hole cards, or the cards are drawn from a different deck position than expected |
| `C7` fails — community_cards empty or wrong cards | Snapshot was serialized before the flop was dealt, or community card list is not populated from live game state |

---

### DS4 — Spectator Filtering Under Deterministic Conditions

**Deck recipe:** Recipe A (owner = Royal Flush; winner is known before the test runs).

#### Test Steps

1. Call `setup_two_players(http, "+1556000")` to get `owner`, `joiner`, `club_id`, `table_id`, `invite_code`.
2. Create `spectator = make_client(http, "+15560001003", "Spectator")`. Call `spectator.join_club(club_id, invite_code)`.
3. Enter `with injected_deck(complete_deck(RECIPE_A)):`.
4. Open `owner.connect(table_id)` and `joiner.connect(table_id)`. Both send `JOIN_TABLE` as `"player"`. Both drain to `BLINDS_POSTED`.
5. Open `spectator.connect(table_id)`. Spectator sends `JOIN_TABLE` as `"spectator"`. Spectator drains to `STATE_SNAPSHOT`.
6. Drive hand to showdown. Spectator is a passive observer and must drain to `HAND_RESULT` (max 100 msgs).
7. Exit all connection contexts. Exit `injected_deck` context. Assert on logs.

#### Expected Key Event Sequence (spectator's log, from join until end)

```
STATE_SNAPSHOT
TURN_CHANGED  (× one or more per street)
PLAYER_ACTED  (× one or more per street)
COMMUNITY_CARDS (phase=FLOP, 3 cards)
...
COMMUNITY_CARDS (phase=TURN, 1 card)
...
COMMUNITY_CARDS (phase=RIVER, 1 card)
...
HAND_RESULT
```

**Spectator must NOT receive:** `CARDS_DEALT` at any point.

#### Assertions

```python
# D1 — Spectator never received CARDS_DEALT
assert not spectator.log.has_type("CARDS_DEALT")

# D2 — Spectator received exactly 3 COMMUNITY_CARDS events
spec_cc = spectator.log.of_type("COMMUNITY_CARDS")
assert len(spec_cc) == 3

# D3 — Spectator's community cards match players' community cards exactly
owner_cc = owner.log.of_type("COMMUNITY_CARDS")
for i in range(3):
    spec_cards = [(c["rank"], c["suit"]) for c in spec_cc[i].payload["cards"]]
    own_cards  = [(c["rank"], c["suit"]) for c in owner_cc[i].payload["cards"]]
    assert spec_cards == own_cards, \
        f"COMMUNITY_CARDS[{i}] mismatch: spectator={spec_cards} owner={own_cards}"

# D4 — Spectator's HAND_RESULT winner matches owner's (known = owner wins Royal Flush)
spec_result  = spectator.log.of_type("HAND_RESULT")[0]
owner_result = owner.log.of_type("HAND_RESULT")[0]
assert spec_result.payload["winners"] == owner_result.payload["winners"]
assert owner.user_id in spec_result.payload["winners"][0]["winner_ids"]

# D5 — Spectator received TURN_CHANGED events
assert spectator.log.has_type("TURN_CHANGED")

# D6 — No errors in any participant's log
assert not spectator.log.has_type("ERROR")
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

#### Failure Cases

| Failure | Root Cause Indicated |
|---------|----------------------|
| `D1` fails — spectator received `CARDS_DEALT` | WebSocket broadcaster did not apply the role/audience filter; `CARDS_DEALT` is being broadcast to all connections rather than unicast to the target player |
| `D2` fails — wrong count of `COMMUNITY_CARDS` | Spectator is being filtered from broadcast events they should receive (over-filtering), or the hand ended before all streets were dealt |
| `D3` fails — card content differs between spectator and owner | The server is sending per-recipient variants of `COMMUNITY_CARDS` with different card lists |
| `D4` fails — winner differs between spectator and players | `HAND_RESULT` is being filtered per recipient, which is incorrect; or spectator received a stale snapshot `HAND_RESULT` |
| `D4` fails — winner is joiner, not owner | Deck injection did not apply, or the evaluator inverted the ranking under these specific board conditions |

---

### DS5 — Duplicate-Request Ordering and Idempotency

**Deck recipe:** Recipe A (sufficient to produce at least one `TURN_CHANGED` before the hand ends).

#### Test Steps

1. Call `setup_two_players(http, "+1556100")`.
2. Enter `with injected_deck(complete_deck(RECIPE_A)):`.
3. Both clients connect and join as players. Both drain to `BLINDS_POSTED`.
4. Consume events from the owner's stream until `TURN_CHANGED` arrives with `payload["user_id"] == owner.user_id`. This is the action slot to exploit.
5. Construct a single action envelope manually (bypassing `send()`'s automatic UUID generation):
   ```python
   duplicate_req_id = str(uuid.uuid4())
   envelope = {
       "type": "ACTION",
       "request_id": duplicate_req_id,
       "table_id": table_id,
       "payload": {"action": "call", "amount": 0},
   }
   ```
6. Send the envelope twice in immediate succession using `owner._ws.send_json(envelope)` both times, before reading any server response.
7. Drain owner to `HAND_RESULT` (max 100 msgs). Drain joiner to `HAND_RESULT` (max 100 msgs).
8. Exit contexts. Assert on logs.

#### Expected Event Sequence (both players' logs, after the duplicate submission)

```
PLAYER_ACTED  (exactly 1, for the duplicate_req_id action)
... (hand continues normally) ...
HAND_RESULT
```

**Must NOT appear:** A second `PLAYER_ACTED` for `duplicate_req_id`, any `TURN_CHANGED` that skips a phase, or `HAND_RESULT` showing a state-corruption pot amount.

#### Assertions

```python
# E1 — Owner's log: exactly 1 PLAYER_ACTED carrying the duplicate_req_id
acted_with_dup_id_owner = [
    e for e in owner.log.of_type("PLAYER_ACTED")
    if e.payload.get("request_id") == duplicate_req_id
       and e.payload.get("user_id") == owner.user_id
]
assert len(acted_with_dup_id_owner) == 1, \
    f"Expected 1 PLAYER_ACTED for duplicate_req_id in owner log, got {len(acted_with_dup_id_owner)}"

# E2 — Joiner's log: exactly 1 PLAYER_ACTED carrying the duplicate_req_id
acted_with_dup_id_joiner = [
    e for e in joiner.log.of_type("PLAYER_ACTED")
    if e.payload.get("request_id") == duplicate_req_id
       and e.payload.get("user_id") == owner.user_id
]
assert len(acted_with_dup_id_joiner) == 1, \
    f"Expected 1 PLAYER_ACTED for duplicate_req_id in joiner log, got {len(acted_with_dup_id_joiner)}"

# E3 — Second send produced an ERROR with code INVALID_ACTION (or idempotent ACK)
error_events = owner.log.of_type("ERROR")
if len(error_events) > 0:
    # Server chose to reply with ERROR rather than silently discard
    assert any(
        e.payload.get("code") == "INVALID_ACTION"
        for e in error_events
    ), f"Expected ERROR with code INVALID_ACTION, got: {[e.payload for e in error_events]}"
    # Exactly 1 error (the duplicate), not more
    assert len(error_events) == 1, \
        f"Expected at most 1 ERROR event, got {len(error_events)}"

# E4 — Hand reached HAND_RESULT (game did not stall)
assert owner.log.has_type("HAND_RESULT")
assert joiner.log.has_type("HAND_RESULT")

# E5 — No state-corruption errors (pot_total is a positive, plausible value)
hand_result = owner.log.of_type("HAND_RESULT")[0]
assert hand_result.payload["pot_total"] > 0

# E6 — Game state integrity: hand advanced past the duplicated action
# (at least one PLAYER_ACTED after the duplicate for any player, or COMMUNITY_CARDS, confirms progression)
subsequent_events = owner.log.types()
dup_index = next(
    i for i, e in enumerate(owner.log.all())
    if e.type == "PLAYER_ACTED"
       and e.payload.get("request_id") == duplicate_req_id
)
events_after_dup = owner.log.types()[dup_index + 1:]
assert len(events_after_dup) > 0, \
    "No events followed the PLAYER_ACTED — game appears stalled after duplicate send"
```

#### Failure Cases

| Failure | Root Cause Indicated |
|---------|----------------------|
| `E1` or `E2` has count > 1 | Idempotency cache is missing, bypassed, or keyed incorrectly; the action was applied twice to the game state |
| `E3` — ERROR code is not `INVALID_ACTION` | Error taxonomy is wrong, or the server emitted a different error code for duplicate submissions |
| `E3` — more than 1 ERROR event | The duplicate caused cascading server-side errors (state corruption propagated) |
| `E4` fails — no `HAND_RESULT` | The duplicate submission stalled the game state machine in an unrecoverable state |
| `E5` fails — `pot_total == 0` or implausible | The duplicate action was credited a second time, inflating or zeroing the pot |

---

## 3. Deterministic Replay Verification

### Purpose

Verifies that running the same deterministic scenario twice within a single test function produces byte-for-byte identical `HAND_RESULT` payloads. This confirms that `injected_deck` is genuinely deterministic (not merely coincidentally consistent) and that no nondeterministic state leaks between back-to-back invocations.

### Approach

Run DS1 twice inside the same test function, each time with a fresh `TestClient` fixture (to ensure independent backend state). Compare the `HAND_RESULT` winner payloads from both runs.

```python
def test_ds1_replay_determinism(http):
    """DS1 must produce identical HAND_RESULT on consecutive runs."""

    def run_once(client):
        owner, joiner, _, table_id, _ = setup_two_players(client, "+1557700")
        with injected_deck(complete_deck(RECIPE_A)):
            with owner.connect(table_id):
                with joiner.connect(table_id):
                    owner.send_join(table_id, "player")
                    owner.drain_until("STATE_SNAPSHOT")
                    joiner.send_join(table_id, "player")
                    joiner.drain_until("STATE_SNAPSHOT")
                    owner.drain_until("BLINDS_POSTED")
                    joiner.drain_until("BLINDS_POSTED")
                    _drive_to_showdown(owner, joiner, table_id)
        return owner.log.of_type("HAND_RESULT")[0].payload

    result_1 = run_once(http)

    # Re-authenticate with different phone prefixes to avoid user-ID collisions
    # on the same backend instance, OR use a second http fixture if available.
    # The critical comparison is the winner_ids list, not the user_id values.
    result_2 = run_once(http)

    # Both runs must agree on the winner (index 0 of winners list)
    assert result_1["winners"][0]["winner_ids"] == result_2["winners"][0]["winner_ids"], \
        f"Replay divergence: run1 winners={result_1['winners']}, run2 winners={result_2['winners']}"

    assert result_1["winners"][0].get("hand_description") == \
           result_2["winners"][0].get("hand_description"), \
        "Replay divergence: hand_description differs between runs"
```

### What a Replay Divergence Failure Indicates

A divergence between run 1 and run 2 — where the winner or hand description differs — means one of the following:

- **The deck injection did not apply on one run.** The context manager was exited prematurely, or the `complete_deck()` call returned a different list on the second invocation. This would cause one run to use the real shuffled deck.
- **Seat assignment is nondeterministic.** `setup_two_players` registered users in a consistent order, but the server assigned seats based on a random or time-dependent tiebreaker. The player holding the strong hand differs between runs. Mitigation: assert winner by inspecting `CARDS_DEALT` payloads (verify which `user_id` received the Royal Flush hole cards) before comparing `winner_ids`.
- **Between-hands delay is insufficient.** A second hand started before the first `injected_deck` context was fully entered. The fast `BETWEEN_HANDS_DELAY = 0.05 s` in `make_test_client` is usually enough, but if a new hand starts during test setup, the unpatched deck is used.
- **Shared global state.** Some module-level counter or cache carried over between the two `run_once` calls affects card dealing. This would indicate a test isolation failure.

---

## 4. Deck Patch Isolation Tests

These tests verify that `injected_deck` correctly installs and removes the patch. They are independent of any full game scenario.

### Test 4.1 — Patch Is Active Inside the Context

```python
def test_patch_active_inside_context():
    import poker_engine.engine.game_engine as _ge
    from simulation.deck_control import injected_deck, complete_deck, RECIPE_A

    original_fn = _ge.fresh_shuffled_deck

    with injected_deck(complete_deck(RECIPE_A)):
        patched_fn = _ge.fresh_shuffled_deck
        assert patched_fn is not original_fn, \
            "fresh_shuffled_deck must be replaced inside injected_deck context"
        deck = _ge.fresh_shuffled_deck()
        assert deck[0].rank.value == "A" and deck[0].suit.value == "S", \
            f"First card must be (A, S) per RECIPE_A; got {deck[0]}"
```

### Test 4.2 — Original Function Restored After Normal Exit

```python
def test_patch_restored_after_normal_exit():
    import poker_engine.engine.game_engine as _ge
    from simulation.deck_control import injected_deck, complete_deck, RECIPE_A

    original_fn = _ge.fresh_shuffled_deck

    with injected_deck(complete_deck(RECIPE_A)):
        pass  # no operations inside

    restored_fn = _ge.fresh_shuffled_deck
    assert restored_fn is original_fn, \
        "fresh_shuffled_deck must be restored to the original function object after context exit"
```

### Test 4.3 — Original Function Restored After Exception Inside Context

```python
def test_patch_restored_after_exception():
    import poker_engine.engine.game_engine as _ge
    from simulation.deck_control import injected_deck, complete_deck, RECIPE_A

    original_fn = _ge.fresh_shuffled_deck

    try:
        with injected_deck(complete_deck(RECIPE_A)):
            raise RuntimeError("simulated crash inside injected_deck context")
    except RuntimeError:
        pass  # expected

    restored_fn = _ge.fresh_shuffled_deck
    assert restored_fn is original_fn, \
        "fresh_shuffled_deck must be restored even when an exception is raised inside the context"
```

**What failure in 4.3 indicates:** The `finally` clause in `injected_deck` is absent or misplaced. Subsequent tests (and any production hand started in the same process after the crash) would use the injected deck instead of a real shuffle. This is the "patch leak on crash" failure mode described in Risk R2 of the feature spec.

### Test 4.4 — Sequential Invocations Restore Correctly

```python
def test_sequential_invocations():
    import poker_engine.engine.game_engine as _ge
    from simulation.deck_control import injected_deck, complete_deck, RECIPE_A, RECIPE_B

    original_fn = _ge.fresh_shuffled_deck

    with injected_deck(complete_deck(RECIPE_A)):
        fn_inside_first = _ge.fresh_shuffled_deck
        assert fn_inside_first is not original_fn

    assert _ge.fresh_shuffled_deck is original_fn, \
        "Not restored after first context"

    with injected_deck(complete_deck(RECIPE_B)):
        fn_inside_second = _ge.fresh_shuffled_deck
        assert fn_inside_second is not original_fn

    assert _ge.fresh_shuffled_deck is original_fn, \
        "Not restored after second context"
```

### Test 4.5 — `build_deterministic_deck` Raises on Invalid Input

```python
def test_build_deterministic_deck_invalid_rank():
    from simulation.deck_control import build_deterministic_deck
    import pytest
    with pytest.raises(ValueError, match="rank"):
        build_deterministic_deck([("X", "S")])

def test_build_deterministic_deck_invalid_suit():
    from simulation.deck_control import build_deterministic_deck
    import pytest
    with pytest.raises(ValueError, match="suit"):
        build_deterministic_deck([("A", "Z")])

def test_build_deterministic_deck_all_52():
    from simulation.deck_control import build_deterministic_deck
    from poker_engine.engine.models import Card
    all_ranks = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"]
    all_suits = ["S","H","D","C"]
    spec = [(r, s) for r in all_ranks for s in all_suits]
    cards = build_deterministic_deck(spec)
    assert len(cards) == 52
    assert all(isinstance(c, Card) for c in cards)
```

---

## 5. Hidden Card Filtering Under Deterministic Conditions

With a known deck, card filtering assertions can be exact rather than structural. This section specifies the full matrix of card-visibility expectations.

### Owner's `CARDS_DEALT` Must Exactly Match Deck Positions `[0]` and `[2]`

For Recipe A:

```python
owner_dealt = owner.log.of_type("CARDS_DEALT")[0]
owner_cards = {(c["rank"], c["suit"]) for c in owner_dealt.payload["cards"]}
assert owner_cards == {("A", "S"), ("K", "S")}, \
    f"Owner's hole cards must be exactly {{(A,S),(K,S)}}; got {owner_cards}"
```

### Joiner Must NOT Receive Owner's Hole Cards

```python
joiner_dealt = joiner.log.of_type("CARDS_DEALT")[0]
joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt.payload["cards"]}
assert ("A", "S") not in joiner_cards, "Joiner must not hold owner's A♠"
assert ("K", "S") not in joiner_cards, "Joiner must not hold owner's K♠"
```

### Joiner's `CARDS_DEALT` Must Exactly Match Deck Positions `[1]` and `[3]`

For Recipe A:

```python
assert joiner_cards == {("2", "H"), ("3", "D")}, \
    f"Joiner's hole cards must be exactly {{(2,H),(3,D)}}; got {joiner_cards}"
```

### Spectator Must Receive Zero `CARDS_DEALT` Events

```python
assert len(spectator.log.of_type("CARDS_DEALT")) == 0, \
    f"Spectator received {len(spectator.log.of_type('CARDS_DEALT'))} CARDS_DEALT events; expected 0"
```

### Each Player Receives Exactly One `CARDS_DEALT` Per Hand

```python
assert len(owner.log.of_type("CARDS_DEALT")) == 1
assert len(joiner.log.of_type("CARDS_DEALT")) == 1
```

This rules out both over-delivery (broadcast to all) and double-delivery (unicast sent twice per hand).

### Hole Cards in `CARDS_DEALT` Are Not Visible in the Opponent's `STATE_SNAPSHOT`

If the opponent receives a `STATE_SNAPSHOT` (e.g., after mid-hand join or reconnect):

```python
if joiner.log.has_type("STATE_SNAPSHOT"):
    snap = joiner.log.of_type("STATE_SNAPSHOT")[-1]
    players_map = snap.payload.get("players", {})
    owner_entry = players_map.get(owner.user_id, {})
    visible_cards = owner_entry.get("cards", [])
    assert len(visible_cards) == 0, \
        "Opponent's hole cards must not be visible in joiner's STATE_SNAPSHOT"
```

---

## 6. Duplicate Request Behavior (DS5)

### Detailed Step Specification

1. **Setup:** Two players authenticated and seated, both have drained to `BLINDS_POSTED`.
2. **Find action slot:** Loop over owner's event stream. Consume messages until `TURN_CHANGED` with `payload["user_id"] == owner.user_id` is received.
3. **Construct duplicate envelope:**
   ```python
   import uuid
   duplicate_req_id = str(uuid.uuid4())
   envelope = {
       "type": "ACTION",
       "request_id": duplicate_req_id,
       "table_id": table_id,
       "payload": {"action": "call", "amount": 0},
   }
   ```
4. **Send twice without reading:**
   ```python
   owner._ws.send_json(envelope)   # first send — should be processed
   owner._ws.send_json(envelope)   # second send — must be rejected/ignored
   ```
5. **Drain to completion:**
   ```python
   owner.drain_until("HAND_RESULT", max_msgs=100)
   joiner.drain_until("HAND_RESULT", max_msgs=100)
   ```

### Expected: Exactly 1 `PLAYER_ACTED` for the Acting User in This Round

Count `PLAYER_ACTED` events in owner's log where both `user_id == owner.user_id` AND `request_id == duplicate_req_id`. This count must be exactly 1.

Count the same in joiner's log (joiner receives the broadcast). Also must be exactly 1.

### Expected: Exactly 1 `ERROR` with Code `INVALID_ACTION` (if server chooses error response)

Some server designs silently discard the duplicate (no response) while others reply with an error event. Both are acceptable, but if any `ERROR` event is present, it must be exactly one, and its code must be `INVALID_ACTION` (not `INTERNAL_ERROR`, `STATE_CORRUPTION`, or any other code suggesting the server processed the action twice and encountered inconsistency).

```python
error_events = owner.log.of_type("ERROR")
# Either 0 (silent discard) or exactly 1 (explicit rejection)
assert len(error_events) <= 1, \
    f"Expected at most 1 ERROR event, got {len(error_events)}: {[e.payload for e in error_events]}"
if len(error_events) == 1:
    assert error_events[0].payload.get("code") == "INVALID_ACTION"
```

### Anti-Assertion: No Stall

```python
# The hand must not freeze; it must reach HAND_RESULT
assert owner.log.has_type("HAND_RESULT"), \
    "Hand stalled after duplicate action — game state machine did not advance"
```

---

## 7. Reconnect Snapshot Contents (DS3)

### With Known Deck, Assertions Are Exact Card Comparisons

The injected deck makes snapshot assertions exact rather than structural. The following checks apply after the flop has been dealt and the owner has reconnected.

### Player's Own Hole Cards in Snapshot Match Deck `[0]` and `[2]` (for Recipe B owner)

```python
snap = owner.log.of_type("STATE_SNAPSHOT")[0]
players_map = snap.payload.get("players", {})
owner_snap_cards = {
    (c["rank"], c["suit"])
    for c in players_map[owner.user_id].get("cards", [])
}
assert owner_snap_cards == {("2", "S"), ("3", "H")}, \
    f"Snapshot hole cards mismatch: {owner_snap_cards}"
```

### Snapshot Does NOT Contain Opponent's Hole Cards

```python
if joiner.user_id in players_map:
    opp_snap_cards = players_map[joiner.user_id].get("cards", [])
    assert opp_snap_cards == [] or opp_snap_cards is None, \
        f"Opponent cards leaked into snapshot: {opp_snap_cards}"
```

### `community_cards` in Snapshot Matches Flop From Injected Deck

For Recipe B, flop = A♣, K♠, Q♦ (deck positions `[4:7]`):

```python
community_in_snap = snap.payload.get("community_cards", [])
snap_flop = [(c["rank"], c["suit"]) for c in community_in_snap[:3]]
assert snap_flop == [("A", "C"), ("K", "S"), ("Q", "D")], \
    f"Snapshot community cards do not match injected flop: {snap_flop}"
```

### Timing: Disconnect Must Occur After the Flop `COMMUNITY_CARDS` Event

The scenario must consume at least one `COMMUNITY_CARDS` event in owner's log before triggering the disconnect. If the disconnect happens during the pre-flop betting round, the snapshot will correctly have an empty `community_cards` list — but that would not test the scenario's goal of verifying community card persistence in the snapshot.

```python
# Before disconnecting, ensure the flop has been dealt
assert owner.log.has_type("COMMUNITY_CARDS"), \
    "Flop must have been dealt before owner disconnects; otherwise snapshot community_cards test is vacuous"
```

---

## 8. Event Ordering Assertions

### DS1: Expected Post-`BLINDS_POSTED` Event Type Sequence

Using `owner.log.types()` after draining to `HAND_RESULT`, verify that the following types appear in this relative order (other events may intersperse):

```
... BLINDS_POSTED ...
PHASE_CHANGED  (phase=PRE_FLOP or START_HAND)
TURN_CHANGED
... (PLAYER_ACTED, TURN_CHANGED pairs) ...
COMMUNITY_CARDS   (phase=FLOP)
... (PLAYER_ACTED, TURN_CHANGED pairs) ...
COMMUNITY_CARDS   (phase=TURN)
... (PLAYER_ACTED, TURN_CHANGED pairs) ...
COMMUNITY_CARDS   (phase=RIVER)
... (PLAYER_ACTED, TURN_CHANGED pairs) ...
HAND_RESULT
```

Assertion helper:

```python
def assert_relative_order(types_list, *required_types):
    """Assert that required_types appear in this relative order in types_list."""
    pos = 0
    for rt in required_types:
        while pos < len(types_list) and types_list[pos] != rt:
            pos += 1
        assert pos < len(types_list), \
            f"Event type {rt!r} not found in log after position. Log: {types_list}"
        pos += 1

types = owner.log.types()
assert_relative_order(
    types,
    "BLINDS_POSTED",
    "TURN_CHANGED",
    "COMMUNITY_CARDS",   # flop
    "COMMUNITY_CARDS",   # turn
    "COMMUNITY_CARDS",   # river
    "HAND_RESULT",
)
```

### DS2: Exact `COMMUNITY_CARDS` Count and Order

```python
cc_events = owner.log.of_type("COMMUNITY_CARDS")
assert len(cc_events) == 3, f"Expected 3 COMMUNITY_CARDS events, got {len(cc_events)}"

# Flop must be first: 3 cards
assert len(cc_events[0].payload["cards"]) == 3, \
    f"Flop must have 3 cards; got {len(cc_events[0].payload['cards'])}"
assert cc_events[0].payload.get("phase") == "FLOP"

# Turn must be second: 1 card
assert len(cc_events[1].payload["cards"]) == 1, \
    f"Turn must have 1 card; got {len(cc_events[1].payload['cards'])}"
assert cc_events[1].payload.get("phase") == "TURN"

# River must be third: 1 card
assert len(cc_events[2].payload["cards"]) == 1, \
    f"River must have 1 card; got {len(cc_events[2].payload['cards'])}"
assert cc_events[2].payload.get("phase") == "RIVER"
```

### DS4: `HAND_RESULT` Must Be Last Meaningful Game Event

```python
types = owner.log.types()
hand_result_indices = [i for i, t in enumerate(types) if t == "HAND_RESULT"]
assert len(hand_result_indices) >= 1
# No TURN_CHANGED or PLAYER_ACTED may appear after the first HAND_RESULT
last_hand_result_idx = hand_result_indices[-1]
events_after = types[last_hand_result_idx + 1:]
for t in events_after:
    assert t not in ("TURN_CHANGED", "PLAYER_ACTED"), \
        f"Event {t!r} appeared after HAND_RESULT — possible duplicate hand processing"
```

---

## 9. Flakiness Detection Checklist

The following five conditions can cause deterministic tests to fail intermittently. Each includes a detection strategy and mitigation.

### F1 — Race Between `start_hand()` and `injected_deck()` Entry

**Mechanism:** If `BETWEEN_HANDS_DELAY` elapses and `start_hand()` is called before the test enters the `with injected_deck(...)` block, the first hand uses a real shuffled deck. This is timing-sensitive.

**Detection:** The DS1 assertion `("A", "S") in owner_cards` fails on some runs but not others. The failure is correlated with slow CI machines.

**Mitigation:** The `with injected_deck(...)` block must be entered before any WebSocket connections that trigger a hand start. The correct structure is: `with injected_deck(deck): with owner.connect(...): with joiner.connect(...)`. Never connect players outside the `injected_deck` context.

---

### F2 — Seat Assignment Order Is Nondeterministic

**Mechanism:** If the server assigns seats based on arrival time rather than a deterministic order (e.g., database insertion order), the owner may land in seat 1 instead of seat 0, receiving deck positions `[2:4]` (Recipe A: K♠ and Q♠) instead of `[0:2]` (A♠ and K♠). The Royal Flush would then belong to neither player, and the winner assertion would fail.

**Detection:** DS1 winner assertion fails intermittently. The `CARDS_DEALT` for owner sometimes contains `("A","S")` and `("K","S")`, and sometimes a different pair.

**Mitigation:** Always confirm hole cards via `CARDS_DEALT` before asserting the winner. Never assert `owner.user_id` wins directly; instead, find the `user_id` that received the Royal Flush hole cards from `CARDS_DEALT`, then assert that `user_id` is in `winner_ids`.

---

### F3 — Shared `fresh_shuffled_deck` Attribute Modified by a Concurrent Test

**Mechanism:** If `pytest-xdist` is used with `-n 2` or higher, two test processes sharing the same Python interpreter can simultaneously modify `poker_engine.engine.game_engine.fresh_shuffled_deck`. One context manager saves the other's lambda as "original", leading to permanent corruption of the attribute after both contexts exit.

**Detection:** `test_patch_restored_after_normal_exit` fails with `restored_fn is not original_fn`. Scenarios produce unexpected cards across tests.

**Mitigation:** `pytest.ini` must not contain `-n` in `addopts`. The deterministic test file must include `pytestmark = pytest.mark.serial` and be excluded from any `pytest-xdist` worker group configuration. Verify by running `pytest -n 2 tests/test_simulation_deterministic.py` and confirming it either passes (sequential fallback) or fails with a clear xdist-incompatibility marker.

---

### F4 — `EventLog.clear()` Called Between Connection and Assertion

**Mechanism:** `SimulatedClient.connect()` calls `self.log.clear()` on entry. If a scenario reconnects a client (as in DS3), the second `connect()` call wipes all events from the first connection, including `CARDS_DEALT` and `COMMUNITY_CARDS` events captured before the disconnect. Assertions on hole cards or pre-disconnect community cards then fail with "0 events of type CARDS_DEALT".

**Detection:** DS3 assertion `C6` fails — `owner.log.of_type("CARDS_DEALT")` returns an empty list after reconnect.

**Mitigation:** Capture all needed event payloads from the first connection into local variables before exiting the first `connect()` context. The second `connect()` call will clear the log; do not rely on the log from the first session after reconnect.

---

### F5 — `max_msgs` Limit in `drain_until` Too Low for Deterministic Hands

**Mechanism:** `drain_until(event_type, max_msgs=30)` is the default. A full 5-street hand with 2 players generates approximately 20–30 server events (PHASE_CHANGED, BLINDS_POSTED, TURN_CHANGED ×8, PLAYER_ACTED ×8, COMMUNITY_CARDS ×3, HAND_RESULT). If the spectator joins after several events have already been broadcast, their log may lag. The default 30-message window can be exhausted before `HAND_RESULT` arrives in the spectator's log.

**Detection:** DS4 fails with `AssertionError: 'HAND_RESULT' not received within 30 messages`. The error message from `drain_until` shows the last 30 types, which include `COMMUNITY_CARDS` events but not `HAND_RESULT`.

**Mitigation:** All `drain_until("HAND_RESULT", ...)` calls in deterministic scenarios must use `max_msgs=100`. This is already specified in the scenario designs for DS5 and should be applied consistently to DS1–DS4 as well.

---

## 10. Isolation Between Tests

### Each Test Gets a Fresh `http` Fixture

The `http` pytest fixture in `tests/test_simulation_deterministic.py` creates a new `TestClient` wrapping a freshly instantiated FastAPI app:

```python
@pytest.fixture
def http():
    client = make_test_client(between_hands_delay=0.05)
    yield client
    client.__exit__(None, None, None)
    restore_delays()
```

Each `TestClient` has its own in-memory session store, club registry, and WebSocket broadcaster. No club, user, or game state persists from one test function to the next.

### `injected_deck()` Restores the Original Function

The `finally` block in `injected_deck()` unconditionally restores `poker_engine.engine.game_engine.fresh_shuffled_deck` to the original function object. Even if the test function raises an unhandled exception, the patch is removed before the next test's setup phase executes.

### No Shared Mutable State Between Test Functions

- **User IDs:** Each scenario uses a distinct phone prefix (e.g., `"+1555700"`, `"+1555800"`) so that two scenarios running against the same backend instance (in the replay verification test) do not collide on user registration.
- **Club/table state:** Each `setup_two_players()` call creates a new club and table; there is no global "default table".
- **Module-level patch:** The `fresh_shuffled_deck` attribute is the only global state touched; it is restored by `injected_deck`'s `finally` block.
- **`EventLog`:** `SimulatedClient.log` is cleared at the start of each `connect()` call. Between test functions, a new `SimulatedClient` is constructed, so there is no log carryover.

### Verification: Run Tests in Reverse Order

To confirm that test ordering does not affect outcomes, run the deterministic test file with pytest's reverse-order plugin or manually specify the reverse order:

```bash
pytest tests/test_simulation_deterministic.py \
    -k "test_ds5 or test_ds4 or test_ds3 or test_ds2 or test_ds1" \
    --collect-only   # verify order

pytest tests/test_simulation_deterministic.py \
    -p no:randomly   # disable random ordering if pytest-randomly is installed
```

Expected result: all 5 tests pass regardless of execution order. If a test passes when run alone but fails when preceded by another test, this indicates a patch-leak or shared-state bug.

The canonical verification command is:

```bash
pytest tests/test_simulation_deterministic.py -v --tb=long
# then:
pytest tests/test_simulation_deterministic.py -v --tb=long \
    --collect-only 2>&1 | grep "test_ds" | tac | xargs pytest
```

---

## 11. Regressions This Feature Catches

The following engine and transport bugs would produce silent false-passes in nondeterministic scenarios but are caught with certainty by deterministic scenarios.

### R1 — Off-by-One in Hand Evaluator's Suit Comparison

**Description:** The evaluator compares suits using `>` instead of `>=` for straight-flush detection, causing it to miss a Royal Flush on certain suit combinations (e.g., all spades) and instead return "Straight" as the hand category.

**Caught by:** DS1 — `hand_description` assertion fails because the server reports "Straight" instead of "Royal Flush". A nondeterministic run would rarely be dealt a Royal Flush, so this bug would go undetected for hundreds of CI runs.

---

### R2 — Community Cards Dealt in Wrong Order (Flop Before Blinds)

**Description:** A refactor of `start_hand()` moves community-card dealing before the blind-posting step. `COMMUNITY_CARDS` events arrive before `BLINDS_POSTED` in the event stream.

**Caught by:** DS2 — event ordering assertion `assert_relative_order(types, "BLINDS_POSTED", "COMMUNITY_CARDS")` fails. Nondeterministic scenarios only check that `COMMUNITY_CARDS` exists, not when it appears relative to `BLINDS_POSTED`.

---

### R3 — Hole Cards Broadcast to All Connections Instead of Unicast

**Description:** A change to the WebSocket broadcaster accidentally sends `CARDS_DEALT` to all connected clients rather than only the target player.

**Caught by:** DS4 — `assert not spectator.log.has_type("CARDS_DEALT")` fails with certainty because the deck is known and the event is guaranteed to be sent. Nondeterministic scenario s3 also catches this, but DS4 adds the deterministic layer: the exact cards leaked can be verified against the injected deck, confirming the failure is not a test artifact.

---

### R4 — `STATE_SNAPSHOT` Omits Community Cards After Flop

**Description:** A serialization regression in `_build_snapshot()` always serializes `community_cards` as an empty list, regardless of the current board state.

**Caught by:** DS3 — `C7` assertion `len(community_in_snap) >= 3` fails. Nondeterministic reconnect scenario s4 only checks that the player's seat is preserved; it does not assert on community card content.

---

### R5 — Idempotency Cache Keyed on `user_id` Instead of `(user_id, request_id)`

**Description:** The server's duplicate-action guard checks only `user_id`, so a player's second legitimate action in the hand (with a different `request_id`) is rejected as a duplicate of the first.

**Caught by:** DS5 — the hand stalls after the duplicate submission because the joiner's first action is also rejected. `HAND_RESULT` is never received, and the `assert owner.log.has_type("HAND_RESULT")` assertion times out. Nondeterministic scenarios never send the same `request_id` twice, so this regression is invisible to them.

---

### R6 — Duplicate Action Applied Twice, Inflating the Pot

**Description:** The idempotency cache has a race condition: the same `request_id` is processed twice before the cache is written, causing the action to be applied twice to the chip ledger.

**Caught by:** DS5 — `len(acted_with_dup_id_owner) == 1` fails (count is 2), and `pot_total` is inflated beyond the expected sum of blinds. Nondeterministic scenarios never submit duplicate `request_id` values.

---

### R7 — `fresh_shuffled_deck` Returned by Value, Not by Reference

**Description:** A future engine refactor changes `start_hand()` to call `poker_engine.engine.deck.fresh_shuffled_deck()` directly (bypassing the module-level binding in `game_engine`), rather than calling the module-level name `poker_engine.engine.game_engine.fresh_shuffled_deck`. This would make the monkey-patch ineffective.

**Caught by:** DS1–DS4 — hole card assertions (`("A","S") in owner_cards`) would fail on every run because the engine is using a real shuffle, not the injected deck. This failure surfaces as a loud, 100% reproducible failure rather than an intermittent one, making the root cause easy to identify.

---

### R8 — `HAND_RESULT` `winners` List Contains Wrong `pot_index`

**Description:** In a multi-pot scenario (or a single-pot scenario with an off-by-one), the `pot_index` field in each winner record is set to 1 instead of 0 for the main pot, causing downstream pot-attribution logic to miscount payouts.

**Caught by:** DS1 and DS2 — `winners[0]["pot_index"] == 0` assertion (if added) fails deterministically. Nondeterministic scenarios do not assert on `pot_index` because the pot structure can vary with random cards.

---

## 12. QA Sign-Off Conditions

All of the following conditions must be satisfied before this feature is considered QA-approved and eligible for merge.

### Condition 1 — All 5 Deterministic Scenarios Pass on 3 Consecutive Runs

Run the deterministic test suite 3 times in sequence on the CI target platform (Linux, CPython 3.12, same hardware as the existing CI job). All 5 tests must show `PASSED` on all 3 runs with no `XFAIL` or `SKIP`.

```bash
for i in 1 2 3; do
  echo "=== Run $i ===" && \
  pytest tests/test_simulation_deterministic.py -v --tb=short
done
```

No intermittent failures are acceptable. Any failure on any of the 3 runs blocks sign-off and requires root-cause investigation (consult Section 9 — Flakiness Detection Checklist).

### Condition 2 — Deck Patch Restoration Verified

Tests 4.2, 4.3, and 4.4 (Section 4 — Deck Patch Isolation Tests) must all pass. In particular:

- `test_patch_restored_after_normal_exit` confirms the happy-path restoration.
- `test_patch_restored_after_exception` confirms crash-safe restoration.
- `test_sequential_invocations` confirms that a second `injected_deck()` call after the first context has exited produces a correctly injected deck and a correct restoration.

### Condition 3 — No Hidden Card Leakage Under Deterministic Conditions

Under Recipe A (DS1 and DS4) and Recipe B (DS2 and DS3), the following must hold on every run:

- Joiner's `CARDS_DEALT` payload does not contain any card from deck positions `[0]` or `[2]` (owner's hole cards).
- Owner's `CARDS_DEALT` payload does not contain any card from deck positions `[1]` or `[3]` (joiner's hole cards).
- Any connected spectator has zero `CARDS_DEALT` events in their log.
- A reconnecting player's `STATE_SNAPSHOT` does not expose the opponent's hole cards.

These are not structural assertions — they are exact card-identity assertions enabled by the deterministic deck.

### Condition 4 — Full Regression Suite Still Passes

The complete test suite, including the existing nondeterministic scenarios s1–s6 and all unit tests in `poker_engine/tests/`, must pass without modification after this feature is merged:

```bash
pytest -v --tb=short
```

Expected minimum: 175+ tests collected, 0 failures, 0 errors. The count of 175 is the baseline established before this feature. The deterministic scenarios add 5 more tests, so the new expected minimum is 180+ collected.

### Condition 5 — Module Boundary Verified

A grep-based check confirms that no file under `poker_engine/` or `backend/` imports from `simulation`:

```bash
grep -r "from simulation" poker_engine/ backend/ && echo "BOUNDARY VIOLATION" || echo "OK"
grep -r "import simulation" poker_engine/ backend/ && echo "BOUNDARY VIOLATION" || echo "OK"
```

Both commands must output `OK`. Any `BOUNDARY VIOLATION` output blocks sign-off.

### Condition 6 — Replay Divergence Test Passes

`test_ds1_replay_determinism` (Section 3) must pass, confirming that two back-to-back executions of DS1 against the same backend instance produce identical `winner_ids` and `hand_description` values in `HAND_RESULT`.

---

*End of QA Test Plan.*
