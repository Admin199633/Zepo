# Player Feedback — connection-resilience-and-session-recovery

> Agent: Poker Player Reviewer
> Date: 2026-03-19

---

## Reviewer Perspective

Reviewing as a regular friend-group Texas Hold'em player. We play on phones at home, in transit, and occasionally at bad WiFi spots. Disconnections happen. The question is: does the game feel fair and sane when they do?

---

## What Feels Natural

### 60-second reserve window
A 60-second reserve window feels right for real play. My phone can drop and reconnect in under 5 seconds on a good network, and even on a bad one, 60 seconds gives me time to reopen the app. If I'm going through a tunnel or switching networks, I'd want at least 30–60 seconds. This is well-calibrated.

### Seat is held during the reserve window
This is essential. If I drop and my seat disappears, I'd feel robbed — especially if I had a strong hand. Holding the seat and letting me come back is what a real game would do: your friends would wait for you to grab another beer and come back to the table.

### Reconnecting shows me the current state
Receiving a full `STATE_SNAPSHOT` on reconnect is the right behavior. I need to see exactly what happened while I was gone — the current pot, community cards, my stack, who acted. A partial view would be confusing.

### Timer fires → I'm sitting out, not removed
If I miss 60 seconds, being moved to `SIT_OUT` rather than kicked out feels proportionate. My chips are still there. I can rejoin the next hand. The alternative (removing me and redistributing my chips) would feel punishing and unfair. Sitting out is what a real dealer would do: "He's stepped away from the table."

### Reconnect after expiry → still at the table, but sitting out
I appreciate that I'm still at the table after a long disconnect. I can come back and sit in. I'm not gone forever. I just missed some hands. This is realistic.

---

## What Feels Unfair or Confusing

### Double-disconnect could feel like a hack
If someone's connection is repeatedly flapping (connect, disconnect, connect, disconnect), and each disconnect resets the 60-second clock, that's exploitable in a real game. A crafty player could stay at the table with an "unstable connection" while their hand is unplayable (e.g., bad cards), effectively pausing the game for 60 seconds repeatedly. This should be fixed: the clock starts once, and it doesn't reset if you were already disconnected.

### No feedback when reconnecting after expiry
When I reconnect after the 60-second window has passed, I should clearly understand what happened. The `STATE_SNAPSHOT` will show me as `SIT_OUT`, but it's not obvious *why*. In a real game, someone would tell me: "You were gone too long, so we moved on. You're sitting out now — type !sitin when you're ready." The current system is technically correct but the player experience depends entirely on whether the mobile client explains the `SIT_OUT` status clearly. For now this is acceptable — the data is there.

### My turn could pass while I'm disconnected
If it's my turn and I disconnect, the turn timer will eventually fire and auto-fold me. This is correct behavior — the game can't wait forever. But it could feel harsh if my connection dropped for 5 seconds right at the moment it was my turn. In a real friend group, you'd probably wait 10–15 seconds before the "fold on timeout" rule kicked in. The 30-second turn timer and 60-second reserve are independent mechanisms and together they provide reasonable coverage. This is acceptable.

### No visual signal to other players about reserve duration
Other players receive `PLAYER_STATUS{disconnected, reserve_until=...}`. The `reserve_until` field is there, but clients must parse and display it as a countdown. If the client ignores this field, other players just see "disconnected" with no indication of when the seat will clear. This is a client concern, not a backend concern — but it's worth calling out as a known gap in experience.

---

## Player Situations Still Missing

### What if I reconnect during the BLINDS phase?
If my hand starts while I'm disconnected but I reconnect before my first action, I should receive my cards in the `STATE_SNAPSHOT` or have them already in-hand (since the server dealt them regardless). This is currently handled correctly by the `build_player_view` which includes hole cards. No change needed.

### What if everyone at the table disconnects simultaneously?
If all players disconnect, no hand can start. No new hand will be dealt until connected eligible players return. This is correct behavior — the table effectively pauses. But there's no test for the edge case where a hand is in progress and the last connected player disconnects. The hand will continue waiting for the timer and then auto-fold. This is deferred but worth noting.

### Long-running sit-out
If I'm at a table with 2 other players and I'm sitting out, those 2 players can keep playing without me. My chips just sit there. There's no "blind-posting while sitting out" rule in this implementation. This matches typical friend-group rules (you don't post blinds while sitting out). Fine for this phase.

---

## What Would Most Improve Confidence

1. **Test proving double-disconnect doesn't extend the window** — The timer exploit should be provably fixed, not just by design.

2. **Test proving reconnect-after-expiry returns SIT_OUT status explicitly** — Developers and QA need to verify this path. Currently it's untested.

3. **S7 scenario: full disconnect-timeout flow at the table level** — An end-to-end scenario where a player's connection drops, the timer fires, the table continues without them, and they rejoin. This would give everyone confidence the whole flow works.

---

## Overall Assessment

The reconnect behavior is fair and functional. A friend-group poker player would find this natural — 60 seconds is generous, seat retention is correct, and coming back to find yourself sitting out (rather than kicked) is the right outcome. The double-disconnect timer reset is the one thing that feels exploitable and should be fixed. Everything else is already in the right shape; it just needs test coverage to prove it.

**Approved for implementation** with the double-disconnect fix as a mandatory change.
