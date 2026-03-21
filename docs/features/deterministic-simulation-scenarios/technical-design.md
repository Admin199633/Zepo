# Technical Design: Deterministic Simulation Scenarios

**Feature ID:** deterministic-simulation-scenarios
**Status:** Engineering Design
**Author:** Senior Mobile Game Developer Agent
**Last Updated:** 2026-03-19

---

## Table of Contents

1. [Deterministic Strategy](#1-deterministic-strategy)
2. [simulation/deck_control.py — Module Design](#2-simulationdeck_controlpy--module-design)
3. [Known Winner Deck Recipes](#3-known-winner-deck-recipes)
4. [Scenario Module Layout](#4-scenario-module-layout)
5. [Per-Scenario Design](#5-per-scenario-design)
6. [Assertion Strategy](#6-assertion-strategy)
7. [Test Isolation](#7-test-isolation)
8. [Module Boundary Rules](#8-module-boundary-rules)
9. [Thread Safety](#9-thread-safety)

---

## 1. Deterministic Strategy

### Chosen Mechanism: Deck Injection via Module-Level Monkey-Patch

The production engine shuffles on every hand using `secrets.SystemRandom` (a CSPRNG). `game_engine.py` imports the shuffle function at module load time as a bare name binding:

```python
# poker_engine/engine/game_engine.py  line 22
from .deck import deal_cards, fresh_shuffled_deck
```

Because Python `from … import` copies the name into the importing module's namespace as `poker_engine.engine.game_engine.fresh_shuffled_deck`, assigning a replacement to that attribute intercepts all calls to `fresh_shuffled_deck()` inside `game_engine.py` — including the call at line 93 of `start_hand()`:

```python
deck = fresh_shuffled_deck()   # ← resolved via the module-level binding
```

The injection is applied and removed by a context manager that lives exclusively in `simulation/deck_control.py`. No file under `poker_engine/` or `backend/` is modified.

### Alternatives Considered

#### A — Seeded RNG (`random.seed()` / `secrets` replacement)

Replace `secrets.SystemRandom` globally with a seeded `random.Random` instance. This approach is fragile: it requires knowledge of exactly how many `random` calls produce a given shuffle, relies on Python version-specific PRNG internals, and bleeds across concurrent test threads. Additionally, `secrets.SystemRandom` is an OS-level source — seeding it has no guaranteed effect across platforms. Rejected.

#### B — Deck Injection via Constructor / Dependency Injection

Modify `GameEngine.__init__` to accept an optional `deck_factory` callable. This would require changing production code (a file under `poker_engine/engine/`), which the feature-spec explicitly prohibits. Rejected.

#### C — Full Replay (record and replay event log)

Record a real hand's event sequence and replay it as canned server responses. Replay-based approaches verify the test harness, not the live engine. They cannot detect regressions in engine logic. Rejected.

#### D — Deck Injection via Module-Level Monkey-Patch (Chosen)

Directly replace the module-level name `poker_engine.engine.game_engine.fresh_shuffled_deck` with a lambda that returns a pre-ordered list of `Card` objects. The original function reference is captured before replacement and unconditionally restored in a `finally` block. Key properties:

- Zero production code changes.
- The lambda returns a shallow copy of the caller-supplied list so that multiple `start_hand()` calls within one `with` block each consume a fresh list (the engine pops from the deck by slicing, not in-place mutation).
- `contextlib.contextmanager` is used rather than `unittest.mock.patch` to avoid importing the `mock` library for a purpose that is not mocking — it is controlled test input.
- Restoration is unconditional regardless of exception paths.

---

## 2. `simulation/deck_control.py` — Module Design

### Responsibilities

- Parse human-readable `(rank, suit)` string tuples into typed `Card` objects.
- Provide a context manager that installs a pre-ordered deck and tears it down unconditionally.

### `DeckSpec`

A plain type alias for documentation clarity; no runtime overhead:

```python
DeckSpec = list[tuple[str, str]]
```

A `DeckSpec` is a list of `(rank, suit)` pairs where:
- `rank` is one of `"2" "3" "4" "5" "6" "7" "8" "9" "T" "J" "Q" "K" "A"` (case-sensitive, matching `Rank` enum values).
- `suit` is one of `"S" "H" "D" "C"` (case-insensitive; normalized to uppercase internally).

### Full Implementation

```python
"""
simulation/deck_control.py
--------------------------
Deterministic deck injection for simulation scenarios.

BOUNDARY RULE: This module must NEVER be imported from poker_engine/ or backend/.
It is exclusively test-harness infrastructure.
"""
from __future__ import annotations

import poker_engine.engine.game_engine as _game_engine_module
from contextlib import contextmanager
from typing import Generator

from poker_engine.engine.models import Card, Rank, Suit

# Type alias for a deck specification: list of (rank_str, suit_str) pairs.
DeckSpec = list[tuple[str, str]]

# Lookup tables derived directly from the Rank and Suit enums.
_RANK_MAP: dict[str, Rank] = {r.value: r for r in Rank}
_SUIT_MAP: dict[str, Suit] = {s.value: s for s in Suit}


def build_deterministic_deck(cards: DeckSpec) -> list[Card]:
    """
    Convert a list of (rank_str, suit_str) pairs into a list of Card objects.

    rank_str must be one of: "2" "3" "4" "5" "6" "7" "8" "9" "T" "J" "Q" "K" "A"
    suit_str must be one of: "S" "H" "D" "C" (case-insensitive)

    Raises ValueError for any unrecognised rank or suit string.

    Example:
        build_deterministic_deck([("A", "S"), ("K", "S"), ("2", "H"), ("3", "D")])
    """
    result: list[Card] = []
    for rank_str, suit_str in cards:
        rank_upper = rank_str.upper()
        suit_upper = suit_str.upper()
        if rank_upper not in _RANK_MAP:
            raise ValueError(
                f"Unrecognised rank {rank_str!r}. "
                f"Valid ranks: {sorted(_RANK_MAP.keys())}"
            )
        if suit_upper not in _SUIT_MAP:
            raise ValueError(
                f"Unrecognised suit {suit_str!r}. "
                f"Valid suits: {sorted(_SUIT_MAP.keys())}"
            )
        result.append(Card(rank=_RANK_MAP[rank_upper], suit=_SUIT_MAP[suit_upper]))
    return result


@contextmanager
def injected_deck(cards: DeckSpec) -> Generator[None, None, None]:
    """
    Context manager that patches poker_engine.engine.game_engine.fresh_shuffled_deck
    to return a copy of the pre-ordered deck on every call, then restores the
    original function unconditionally on exit.

    Usage:
        with injected_deck([("A","S"),("K","S"),("2","H"),("3","D"), ...]):
            # any start_hand() call within this block receives the pre-ordered deck
            owner.drain_until("HAND_RESULT")

    The lambda returns list(typed_cards) so that each call to fresh_shuffled_deck()
    inside start_hand() receives its own independent list object. The engine slices
    the deck (deck[n:]) rather than mutating it in-place, so returning the same
    object would be safe, but a copy is cleaner and guards against future engine changes.
    """
    typed_cards: list[Card] = build_deterministic_deck(cards)
    original = _game_engine_module.fresh_shuffled_deck
    _game_engine_module.fresh_shuffled_deck = lambda: list(typed_cards)
    try:
        yield
    finally:
        _game_engine_module.fresh_shuffled_deck = original
```

### Notes on the Implementation

- `_game_engine_module` is captured at import time via `import poker_engine.engine.game_engine as _game_engine_module`. The attribute assignment `_game_engine_module.fresh_shuffled_deck = ...` modifies the module's `__dict__`, which is exactly the namespace that `game_engine.py`'s own function body reads when resolving `fresh_shuffled_deck()` at line 93.
- The `original` reference is bound to a local variable inside the `contextmanager`-wrapped generator frame. Even if the generator itself raises, the `finally` clause executes and restores the original, because `contextlib.contextmanager` wraps `GeneratorExit` and exception re-raising correctly.
- `build_deterministic_deck` is intentionally a public function so that scenario modules can call it to build a typed list for assertion comparisons without duplicating the parse logic.

---

## 3. Known Winner Deck Recipes

The dealing order for a 2-player hand (seats sorted ascending, seat 0 = owner, seat 1 = joiner) is:

| Deck Index | Recipient |
|------------|-----------|
| `[0]`      | seat 0 hole card 1 |
| `[1]`      | seat 1 hole card 1 |
| `[2]`      | seat 0 hole card 2 |
| `[3]`      | seat 1 hole card 2 |
| `[4]`      | flop card 1 |
| `[5]`      | flop card 2 |
| `[6]`      | flop card 3 |
| `[7]`      | turn |
| `[8]`      | river |

> Note: `game_engine._deal_hole_cards()` iterates seats in ascending order, dealing 2 cards to each seat via `deal_cards(hand.deck, 2)`. Deck positions `[0:2]` go to seat 0, `[2:4]` to seat 1. Community cards begin at index `[4]`.

---

### Recipe A — Owner Wins with Royal Flush

**Owner** = seat 0. **Joiner** = seat 1.

| Index | Card | Recipient |
|-------|------|-----------|
| `[0]` | `("A","S")` | owner hole card 1 |
| `[1]` | `("2","H")` | joiner hole card 1 |
| `[2]` | `("K","S")` | owner hole card 2 |
| `[3]` | `("3","D")` | joiner hole card 2 |
| `[4]` | `("Q","S")` | flop 1 |
| `[5]` | `("J","S")` | flop 2 |
| `[6]` | `("T","S")` | flop 3 |
| `[7]` | `("2","C")` | turn |
| `[8]` | `("3","C")` | river |

```python
RECIPE_A: DeckSpec = [
    ("A", "S"), ("2", "H"),   # seat0 hc1, seat1 hc1
    ("K", "S"), ("3", "D"),   # seat0 hc2, seat1 hc2
    ("Q", "S"), ("J", "S"), ("T", "S"),  # flop
    ("2", "C"),               # turn
    ("3", "C"),               # river
    # remaining 43 cards can be any non-duplicate cards
]
```

**Owner's hand:** A♠ K♠ Q♠ J♠ T♠ → **Royal Flush** (the strongest possible hand).
**Joiner's hand:** best 5 from {2♥ 3♦ Q♠ J♠ T♠ 2♣ 3♣} → Straight (T-J-Q-A not available; best is Q-J-T-3-2) → **Queen-high straight** at best.
**Expected winner:** owner (seat 0).
**Verdict:** Owner wins with Royal Flush vs Joiner's pair/straight. Unambiguous.

---

### Recipe B — Joiner Wins with Trip Aces

**Owner** = seat 0. **Joiner** = seat 1.

| Index | Card | Recipient |
|-------|------|-----------|
| `[0]` | `("2","S")` | owner hole card 1 |
| `[1]` | `("A","H")` | joiner hole card 1 |
| `[2]` | `("3","H")` | owner hole card 2 |
| `[3]` | `("A","D")` | joiner hole card 2 |
| `[4]` | `("A","C")` | flop 1 |
| `[5]` | `("K","S")` | flop 2 |
| `[6]` | `("Q","D")` | flop 3 |
| `[7]` | `("5","H")` | turn |
| `[8]` | `("6","C")` | river |

```python
RECIPE_B: DeckSpec = [
    ("2", "S"), ("A", "H"),   # seat0 hc1, seat1 hc1
    ("3", "H"), ("A", "D"),   # seat0 hc2, seat1 hc2
    ("A", "C"), ("K", "S"), ("Q", "D"),  # flop
    ("5", "H"),               # turn
    ("6", "C"),               # river
    # remaining 43 cards can be any non-duplicate cards
]
```

**Joiner's hand:** A♥ A♦ + A♣ K♠ Q♦ → **Three of a Kind, Aces** (A♥ A♦ A♣ K♠ Q♦).
**Owner's hand:** 2♠ 3♥ + A♣ K♠ Q♦ 5♥ 6♣ → best 5: A♣ K♠ Q♦ 6♣ 5♥ → **Ace-high** (no pair).
**Expected winner:** joiner (seat 1).
**Verdict:** Trips Aces beats Ace-high decisively. Unambiguous.

---

> **Recipe Note on Completeness:** Only the first 9 positions are prescribed. The remaining 43 positions in the `DeckSpec` passed to `injected_deck()` must be populated with non-duplicate cards for the deck to be valid. In practice, scenarios build only a 9-card prefix; the engine never deals past position `[8]` in a 2-player hand that runs to showdown without folding. If an engine change ever causes more cards to be consumed, `deal_cards` will raise `ValueError: Cannot deal N cards from deck of M`, which will surface as a loud test failure rather than silent corruption.
>
> For the full deck passed to `injected_deck()`, scenario authors should append the remaining 43 non-duplicate cards. A helper function can be provided:
>
> ```python
> def complete_deck(prefix: DeckSpec) -> DeckSpec:
>     """Pad a prefix to a full 52-card deck with non-duplicate cards."""
>     used = {(r.upper(), s.upper()) for r, s in prefix}
>     all_ranks = ["2","3","4","5","6","7","8","9","T","J","Q","K","A"]
>     all_suits = ["S","H","D","C"]
>     padding = [
>         (r, s)
>         for r in all_ranks
>         for s in all_suits
>         if (r, s) not in used
>     ]
>     return list(prefix) + padding
> ```

---

## 4. Scenario Module Layout

```
simulation/
  deck_control.py                          ← NEW
  app_factory.py                           existing
  client.py                                existing
  event_log.py                             existing
  helpers.py                               existing
  runner.py                                existing
  scenarios/
    __init__.py                            existing
    s1_two_player_hand.py                  existing (unmodified)
    s2_mid_hand_join.py                    existing (unmodified)
    s3_spectator_filtering.py              existing (unmodified)
    s4_reconnect.py                        existing (unmodified)
    s5_full_table_rejection.py             existing (unmodified)
    s6_timeout_auto_action.py              existing (unmodified)
    deterministic/
      __init__.py                          ← NEW (exports all 5 run functions)
      ds1_known_winner.py                  ← NEW
      ds2_known_board.py                   ← NEW
      ds3_deterministic_reconnect.py       ← NEW
      ds4_deterministic_spectator.py       ← NEW
      ds5_duplicate_request.py             ← NEW
```

### `simulation/scenarios/deterministic/__init__.py`

```python
"""
Deterministic simulation scenarios (DS1–DS5).

Each module exposes a single `run(http: TestClient) -> None` function
compatible with ScenarioRunner.run() and direct pytest invocation.
"""
from .ds1_known_winner import run as run_ds1
from .ds2_known_board import run as run_ds2
from .ds3_deterministic_reconnect import run as run_ds3
from .ds4_deterministic_spectator import run as run_ds4
from .ds5_duplicate_request import run as run_ds5

__all__ = ["run_ds1", "run_ds2", "run_ds3", "run_ds4", "run_ds5"]
```

---

## 5. Per-Scenario Design

### DS1 — Two-Player Hand with a Known Winner (`ds1_known_winner.py`)

**Purpose / Regression Caught:** Verifies that the engine's showdown evaluator selects the correct winner end-to-end when hole cards and board are prescribed. Catches winner-selection regressions that a nondeterministic run may never surface in CI (e.g., off-by-one in hand ranking, wrong player credited with pot).

**Deck Recipe:** Recipe A (Owner = Royal Flush, Joiner = low cards).

```
Full first 9: [("A","S"),("2","H"),("K","S"),("3","D"),("Q","S"),("J","S"),("T","S"),("2","C"),("3","C")]
```

**Setup Steps:**

```python
owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555700")
```

Both players connect as `"player"`. The hand runs to showdown by calling/checking on every `TURN_CHANGED`.

**Key Assertions:**

```python
# 1. Confirm hole cards via CARDS_DEALT (determines which user_id is "owner")
owner_dealt = owner.log.of_type("CARDS_DEALT")[0]
joiner_dealt = joiner.log.of_type("CARDS_DEALT")[0]

owner_cards = {(c["rank"], c["suit"]) for c in owner_dealt.payload["cards"]}
joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt.payload["cards"]}

assert ("A", "S") in owner_cards and ("K", "S") in owner_cards, \
    "owner must hold the Royal Flush hole cards"
assert ("2", "H") in joiner_cards and ("3", "D") in joiner_cards, \
    "joiner must hold the weak hole cards"

# 2. Winner assertion via HAND_RESULT
hand_result = owner.log.of_type("HAND_RESULT")[0]
winners = hand_result.payload["winners"]
assert len(winners) == 1, "must be exactly one winner (no split pot)"
winning_ids = winners[0]["winner_ids"]
assert owner.user_id in winning_ids, \
    f"owner must win; got winner_ids={winning_ids}"
assert joiner.user_id not in winning_ids, \
    "joiner must not be in winner_ids"

# 3. Pot sanity
assert hand_result.payload["pot_total"] > 0

# 4. No errors
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

---

### DS2 — Known Board / Runout with Expected Showdown Result (`ds2_known_board.py`)

**Purpose / Regression Caught:** Verifies that community cards are dealt in the correct deck positions (flop = `[4:7]`, turn = `[7]`, river = `[8]`) and that the evaluator produces the correct hand rank description at showdown. Catches community-card dealing order regressions and hand-description formatting regressions.

**Deck Recipe:** Recipe B (Joiner = Trip Aces, Owner = Ace-high).

```
Full first 9: [("2","S"),("A","H"),("3","H"),("A","D"),("A","C"),("K","S"),("Q","D"),("5","H"),("6","C")]
```

**Setup Steps:**

```python
owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555800")
```

Both connect as players, hand driven to showdown by check/call on every `TURN_CHANGED`.

**Key Assertions:**

```python
# 1. Confirm hole card assignment
owner_dealt = owner.log.of_type("CARDS_DEALT")[0]
joiner_dealt = joiner.log.of_type("CARDS_DEALT")[0]
joiner_cards = {(c["rank"], c["suit"]) for c in joiner_dealt.payload["cards"]}
assert ("A", "H") in joiner_cards and ("A", "D") in joiner_cards

# 2. Flop — first COMMUNITY_CARDS event
community_events = owner.log.of_type("COMMUNITY_CARDS")
assert len(community_events) == 3, "must receive exactly 3 COMMUNITY_CARDS events"

flop_cards = [(c["rank"], c["suit"]) for c in community_events[0].payload["cards"]]
assert flop_cards == [("A","C"), ("K","S"), ("Q","D")], \
    f"unexpected flop: {flop_cards}"

# 3. Turn
turn_cards = [(c["rank"], c["suit"]) for c in community_events[1].payload["cards"]]
assert turn_cards == [("5","H")], f"unexpected turn: {turn_cards}"

# 4. River
river_cards = [(c["rank"], c["suit"]) for c in community_events[2].payload["cards"]]
assert river_cards == [("6","C")], f"unexpected river: {river_cards}"

# 5. Winner
hand_result = owner.log.of_type("HAND_RESULT")[0]
winners = hand_result.payload["winners"]
assert len(winners) == 1
winning_ids = winners[0]["winner_ids"]
assert joiner.user_id in winning_ids, \
    f"joiner must win with trip aces; got winner_ids={winning_ids}"

# 6. Hand description contains "Three of a Kind" or equivalent
hand_desc = winners[0].get("hand_description", "")
assert "three" in hand_desc.lower() or "three_of_a_kind" in hand_desc.lower(), \
    f"expected trip-aces description, got: {hand_desc!r}"
```

---

### DS3 — Deterministic Reconnect Snapshot (`ds3_deterministic_reconnect.py`)

**Purpose / Regression Caught:** Verifies that the `STATE_SNAPSHOT` sent to a reconnecting player contains community cards consistent with the injected deck. Catches regressions in snapshot serialization (e.g., community cards missing from snapshot, or snapshot reflecting stale pre-flop state after the flop has been dealt).

**Deck Recipe:** Recipe B (same 9-card prefix; the flop cards `A♣ K♠ Q♦` are what the snapshot must reflect after reconnect).

**Setup Steps:**

```python
owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555900")
```

1. Both players connect and join as players.
2. Both drain to `BLINDS_POSTED`.
3. Drive preflop action to completion (both players call/check until `COMMUNITY_CARDS` is received).
4. Owner exits the WebSocket context (disconnect).
5. Joiner drains to `PLAYER_STATUS` confirming owner is disconnected.
6. Owner re-enters `connect(table_id)` and sends `JOIN_TABLE` with `role="player"`.
7. Owner drains to `STATE_SNAPSHOT`.

**Key Assertions:**

```python
# 1. Joiner saw the disconnect event before reconnect
disconnect_evt = joiner.log.of_type("PLAYER_STATUS")[-1]
assert disconnect_evt.payload["status"] == "disconnected"
assert disconnect_evt.payload["user_id"] == owner.user_id

# 2. Reconnect snapshot contains owner's seat
snap = owner.log.of_type("STATE_SNAPSHOT")[0]
assert owner.user_id in snap.payload.get("players", {})

# 3. Community cards in snapshot match injected flop
community_in_snap = snap.payload.get("community_cards", [])
assert len(community_in_snap) >= 3, \
    "snapshot must contain at least the 3 flop cards"
snap_flop = [(c["rank"], c["suit"]) for c in community_in_snap[:3]]
assert snap_flop == [("A","C"), ("K","S"), ("Q","D")], \
    f"snapshot flop mismatch: {snap_flop}"

# 4. No errors
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

---

### DS4 — Spectator Filtering Under Deterministic Conditions (`ds4_deterministic_spectator.py`)

**Purpose / Regression Caught:** Verifies that a spectator never receives `CARDS_DEALT`, receives all three `COMMUNITY_CARDS` events with cards matching the injected deck, and sees the same winner in `HAND_RESULT` as the two active players. Catches regressions in WebSocket broadcast filtering (e.g., hole cards accidentally unicast to spectators, or spectators receiving a different `HAND_RESULT` than players).

**Deck Recipe:** Recipe A (Owner = Royal Flush).

**Setup Steps:**

```python
owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1556000")
spectator = make_client(http, "+15560001003", "Spectator")
spectator.join_club(club_id, invite_code)
```

1. Owner and joiner connect and join as `"player"`.
2. Both drain to `BLINDS_POSTED`.
3. Spectator connects and joins as `"spectator"` (or `"viewer"` per the backend API).
4. Spectator drains to `STATE_SNAPSHOT`.
5. Hand is driven to showdown via check/call.

**Key Assertions:**

```python
# 1. Spectator never received CARDS_DEALT
assert not spectator.log.has_type("CARDS_DEALT"), \
    "spectator must never receive CARDS_DEALT"

# 2. Spectator received all 3 COMMUNITY_CARDS events
spec_community = spectator.log.of_type("COMMUNITY_CARDS")
assert len(spec_community) == 3, \
    f"spectator must receive 3 COMMUNITY_CARDS events, got {len(spec_community)}"

# 3. Community cards in spectator log match players' logs
owner_community = owner.log.of_type("COMMUNITY_CARDS")
for i, (spec_evt, own_evt) in enumerate(zip(spec_community, owner_community)):
    spec_cards = [(c["rank"], c["suit"]) for c in spec_evt.payload["cards"]]
    own_cards  = [(c["rank"], c["suit"]) for c in own_evt.payload["cards"]]
    assert spec_cards == own_cards, \
        f"COMMUNITY_CARDS[{i}] mismatch: spectator={spec_cards} owner={own_cards}"

# 4. Spectator HAND_RESULT winner matches owner's HAND_RESULT winner
spec_result  = spectator.log.of_type("HAND_RESULT")[0]
owner_result = owner.log.of_type("HAND_RESULT")[0]
assert spec_result.payload["winners"] == owner_result.payload["winners"], \
    "spectator HAND_RESULT winners must match owner HAND_RESULT winners"

# 5. No errors
assert not spectator.log.has_type("ERROR")
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

---

### DS5 — Duplicate Request Idempotency (`ds5_duplicate_request.py`)

**Purpose / Regression Caught:** Verifies that submitting the same `ACTION` message with an identical `request_id` twice in immediate succession causes the server to apply the action exactly once. Catches regressions in the server's idempotency layer (e.g., duplicate processing bug introduced when the request-deduplication cache is bypassed or has a race condition).

**Deck Recipe:** Recipe A (sufficient — we only need the hand to reach a `TURN_CHANGED` event before the test action).

**Setup Steps:**

```python
owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1556100")
```

1. Both players connect and join as players.
2. Both drain to `BLINDS_POSTED`.
3. Drive the event stream forward until `TURN_CHANGED` arrives with `user_id == owner.user_id`.
4. Capture the `request_id` to be reused.

**Duplicate-Send Mechanism:**

`SimulatedClient.send()` normally generates a new `uuid4` per call. For DS5, we send the same `request_id` value twice by calling `_ws.send_json()` directly (bypassing the `send()` helper's UUID generation), or by exposing a `send_with_id(msg_type, table_id, payload, request_id)` method. The raw WS JSON is:

```python
duplicate_req_id = str(uuid.uuid4())
envelope = {
    "type": "ACTION",
    "request_id": duplicate_req_id,
    "table_id": table_id,
    "payload": {"action": "call", "amount": 0},
}
owner._ws.send_json(envelope)   # first send
owner._ws.send_json(envelope)   # identical second send (same request_id)
```

**Key Assertions:**

```python
# Drain enough messages to see the result of the duplicate action
owner.drain_until("HAND_RESULT", max_msgs=100)
joiner.drain_until("HAND_RESULT", max_msgs=100)

# 1. Exactly one PLAYER_ACTED for the duplicated request_id
# Count across BOTH logs (owner + joiner both receive broadcast PLAYER_ACTED)
all_acted_owner  = owner.log.of_type("PLAYER_ACTED")
all_acted_joiner = joiner.log.of_type("PLAYER_ACTED")

# Each player's log should contain PLAYER_ACTED events for all actions in the hand.
# Assert that no PLAYER_ACTED event appears more than once per player's log
# with an identical (user_id, request_id) pair.
def count_acted(events, uid):
    return sum(
        1 for e in events
        if e.payload.get("user_id") == uid
        and e.payload.get("request_id") == duplicate_req_id
    )

assert count_acted(all_acted_owner, owner.user_id) == 1, \
    "owner log must contain exactly 1 PLAYER_ACTED for the duplicate request_id"
assert count_acted(all_acted_joiner, owner.user_id) == 1, \
    "joiner log must contain exactly 1 PLAYER_ACTED for the duplicate request_id"

# 2. Hand reached HAND_RESULT without stalling
assert owner.log.has_type("HAND_RESULT")
assert joiner.log.has_type("HAND_RESULT")

# 3. No state-corruption error events
assert not owner.log.has_type("ERROR")
assert not joiner.log.has_type("ERROR")
```

---

## 6. Assertion Strategy

All assertions in deterministic scenarios operate exclusively on the captured `EventLog` of each `SimulatedClient`. No scenario imports or inspects `GameState`, `HandState`, `hole_cards`, or any other internal engine object.

### Winner Assertion

```python
hand_result = client.log.of_type("HAND_RESULT")[0]
winners = hand_result.payload["winners"]
# winners is a list of winner records:
# [{"winner_ids": ["<uid>", ...], "pot_amount": N, "hand_description": "...", ...}]
```

- `winner_ids` — list of user ID strings for the winner(s) of a given pot (multiple IDs = split pot).
- `pot_amount` — integer chip amount awarded.
- `hand_description` — human-readable string (e.g., `"Three of a Kind"`, `"Royal Flush"`). Assert with a case-insensitive substring check to avoid coupling to exact formatting.
- `pot_total` — top-level field; the total chips in the pot before award.

### Community Card Assertion

```python
community_events = client.log.of_type("COMMUNITY_CARDS")
# community_events[0] → flop (3 cards)
# community_events[1] → turn (1 card)
# community_events[2] → river (1 card)
cards = [(c["rank"], c["suit"]) for c in community_events[0].payload["cards"]]
```

Each card in the payload is a dict with `"rank"` and `"suit"` keys matching `Rank.value` and `Suit.value` strings respectively (e.g., `{"rank": "A", "suit": "S"}`).

### Hole Card Assertion

```python
owner_dealt = owner.log.of_type("CARDS_DEALT")[0]
# payload["cards"] — list of card dicts, only this player's own cards
# Exactly 1 CARDS_DEALT event per player per hand (unicast, not broadcast)
assert len(owner.log.of_type("CARDS_DEALT")) == 1
```

Use `CARDS_DEALT` payloads to confirm which player received which hole cards before asserting the winner. This prevents false failures when seat assignment order differs from expected (see Risk R3 in feature-spec).

### Negative Assertions

- `assert not client.log.has_type("ERROR")` — no server-side error events.
- `assert not spectator.log.has_type("CARDS_DEALT")` — spectator never receives hole cards.

---

## 7. Test Isolation

### Context Manager Scope

Each deterministic scenario wraps its entire active hand execution in a single `with injected_deck(cards):` block. The patch is active only while that block executes. When `with` exits (normally or via exception), `fresh_shuffled_deck` is restored before the next scenario begins:

```python
def run(http: TestClient) -> None:
    owner, joiner, club_id, table_id, _ = setup_two_players(http, "+1555700")

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

    # patch is restored here — before any assertions read the log
    _assert_owner_wins(owner, joiner)
```

### `BETWEEN_HANDS_DELAY` Patch

`make_test_client()` in `simulation/app_factory.py` already patches `backend.sessions.session_manager.BETWEEN_HANDS_DELAY` to `0.05` seconds. Deterministic scenarios use `make_test_client()` via the standard pytest fixture, so no additional delay configuration is required.

### Per-Test `TestClient` Isolation

Each pytest test function receives a fresh `http: TestClient` fixture. The `TestClient` wraps a freshly constructed FastAPI app instance with its own in-memory state, so no database, session, or club state leaks between tests. Deterministic scenarios use distinct phone prefixes (e.g., `"+1555700"`, `"+1555800"`, …) to avoid any user-ID collisions if tests are accidentally invoked against a shared backend.

### pytest Integration

Deterministic scenarios are invoked from pytest test functions in `tests/test_simulation_deterministic.py` (new file, not `tests/test_simulation.py` which covers s1–s6):

```python
# tests/test_simulation_deterministic.py
import pytest
from fastapi.testclient import TestClient
from simulation.app_factory import make_test_client, restore_delays
from simulation.scenarios.deterministic import (
    run_ds1, run_ds2, run_ds3, run_ds4, run_ds5,
)

@pytest.fixture
def http():
    client = make_test_client()
    yield client
    client.__exit__(None, None, None)
    restore_delays()

def test_ds1_known_winner(http): run_ds1(http)
def test_ds2_known_board(http):   run_ds2(http)
def test_ds3_reconnect(http):     run_ds3(http)
def test_ds4_spectator(http):     run_ds4(http)
def test_ds5_duplicate(http):     run_ds5(http)
```

The `tests/` directory is already in `pytest.ini`'s `testpaths`, so these tests are discovered automatically.

---

## 8. Module Boundary Rules

### Rule 1: `simulation/deck_control.py` is test-infrastructure only

`deck_control.py` **must never** be imported from any module under:
- `poker_engine/` (engine code)
- `backend/` (application code)

It may freely import from `poker_engine.engine.models` (read-only access to `Card`, `Rank`, `Suit`) and `poker_engine.engine.game_engine` (to hold the module reference for patching).

### Rule 2: `simulation/scenarios/deterministic/` is test-infrastructure only

No module under `poker_engine/` or `backend/` may import from `simulation/scenarios/deterministic/`.

### Rule 3: The patch does not modify any `.py` file

The monkey-patch assigns to the Python module object's `__dict__` at runtime. No source file is written to disk. The file `poker_engine/engine/game_engine.py` is byte-for-byte identical before and after any test run.

### Rule 4: `build_deterministic_deck` may be used in assertions

Scenario assertion blocks may call `build_deterministic_deck(recipe_prefix)` to build a typed list for comparison against `CARDS_DEALT` or `COMMUNITY_CARDS` payloads, rather than duplicating the string-to-Card mapping inline.

### Enforcement

A CI lint step (or `conftest.py` import-order check) should assert that no file under `poker_engine/` or `backend/` contains the string `from simulation` or `import simulation`. This can be added as a `pytest` collect-time check or as a `ruff` custom rule.

---

## 9. Thread Safety

### Problem

`poker_engine.engine.game_engine.fresh_shuffled_deck` is a module-level attribute in a shared Python module object. If two threads simultaneously enter `injected_deck()`, they both write to the same attribute:

- Thread A saves `original_A` and writes `lambda_A`.
- Thread B saves `lambda_A` (not the true original) and writes `lambda_B`.
- Thread A's `finally` restores `lambda_A` (not the true original).
- Thread B's `finally` restores `lambda_A` (not the true original).

The attribute is permanently broken for the remainder of the process.

### Mitigation

**Do not run deterministic simulation tests with `pytest-xdist` parallelism** (`-n auto` or `-n <N>`).

The existing `pytest.ini` does not include `-n` in `addopts`. This is already correct. The recommendation is:

1. Document in `tests/test_simulation_deterministic.py` with a module-level comment:

```python
# IMPORTANT: These tests must NOT run in parallel (pytest-xdist -n>1).
# The deck injection mechanism is not thread-safe — concurrent patches
# to the same module-level attribute will corrupt the function reference.
# pytest.ini addopts deliberately omits -n to ensure sequential execution.
```

2. Optionally, add a `pytest` marker and a `conftest.py` guard:

```python
# conftest.py (in tests/ or project root)
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "serial: mark test as requiring serial (non-parallel) execution"
    )
```

```python
# tests/test_simulation_deterministic.py
pytestmark = pytest.mark.serial
```

3. If `pytest-xdist` is introduced in the future, deterministic scenarios should be isolated to a separate worker via `--dist=loadgroup` with a shared group key, ensuring all deterministic tests run in the same worker process.

### No Issue for Sequential Runs

In the default sequential run (`pytest` without `-n`), `injected_deck` is always entered and exited in strict LIFO order. There is no interference between scenarios when run sequentially, even if they share a single pytest process, because each `with injected_deck(...)` block fully exits (and restores) before the next test function begins.
