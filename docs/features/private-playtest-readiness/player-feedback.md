# Player Feedback: private-playtest-readiness

**Reviewer perspective:** Friend-group player, first internal playtest session, 30-minute game with 4–6 people who all know each other but have never used this app before.
**Date:** 2026-03-19

---

## 1. What Feels Natural

These parts already work correctly and will not cause friction during a first session:

- **Phone OTP login** — mirrors WhatsApp. No one in a friend group wants email/password for a casual poker game.
- **Invite code to join a club** — mirrors Kahoot/Jackbox. Players will understand this immediately.
- **Play/Watch role selection** before entering — sets expectations before anyone is put in an awkward mid-game state.
- **Fold/Check/Call/Raise with a raise slider** — standard mobile poker UI. No re-learning needed.
- **Actor highlight (yellow border)** — players need to know whose turn it is instantly. A visual border is the correct approach.
- **Dealer badge** — real poker players always track who the dealer is. Having this visible builds confidence the game is tracking state correctly.
- **Hand result overlay with winner, hand description, and showdown cards** — the single most important moment of each hand. Getting this right (even with 4s auto-dismiss) means players feel the game paid out correctly.
- **Reconnect with 3 attempts and re-send JOIN** — the fact that reconnect logic exists puts this ahead of most hobby projects.
- **Connection banner for connecting/reconnecting/failed states** — players know something is happening. Silence during network issues is far worse.

---

## 2. What Feels Fragile or Confusing

These are the specific moments during a real 30-minute session that would generate table talk ("wait, did that work?") and slow everything down:

### 2a. "Enter Table" button with no immediate feedback
You press "Enter Table" and nothing happens for a moment. In a real game, someone will say "did it work for you?" A player does not know if they should tap again, wait, or restart. A double-tap could cause a double-join attempt. This is the first action a player takes and it already feels uncertain.

### 2b. Connection failed with no retry button
The banner says "Failed." Then what? A player's natural instinct is to look for a "Try Again" button. There is not one. The player either sits confused, kills the app, or asks the host what to do. In a friend group, the host gets blamed. This is a bad first impression.

### 2c. Background/foreground behavior is unknown
Someone will get a phone call. Someone's screen will lock. What happens when they come back? If the game continues and they miss their turn, they feel cheated. If the app shows stale state when they return, they do not trust anything they see. The other players also notice one person sitting frozen.

### 2d. Club list is empty after joining
A new player joins via invite code and then sees an empty club list. They do not know if they joined. They will tap the join button again. They may end up confused about whether they are in the club. This is a first-session trust killer that happens before a single card is dealt.

### 2e. No table info before entering
Players in a real game always ask "what are the blinds?" before sitting down. There is no way to see this before pressing "Enter Table." Not a crisis but a repeated friction point across the whole session.

### 2f. "Sitting out" banner with no confirmation
You tap "Tap to rejoin." Nothing visibly confirms it worked. Did the server receive it? Are you back in? A player who is unsure will either tap repeatedly or silently miss hands and get frustrated.

### 2g. Hand result overlay edge cases between hands
If the overlay does not clear properly, the next hand starts visually on top of the previous result. A player sees new community cards but the old winner text is still visible. Even one instance of this in a 30-minute game makes everyone distrust the result screen permanently.

### 2h. No confirmation that game state was restored after reconnect
Reconnect succeeds and re-sends JOIN, but the player just sees the table and does not know if their chips, hole cards, position, and the current action are all accurate. They have to assume. In a game involving bragging rights, assumption is not good enough.

---

## 3. Playtest Blockers

These issues would cause a player to stop trusting the app or stop being able to play:

**Blocker 1 — No retry button on connection failure.**
If one player hits "Failed" and cannot get back in without killing the app, the game stops. The host has to troubleshoot. If this happens twice, the session ends early.

**Blocker 2 — Unknown background/foreground behavior.**
If someone gets a call and comes back to a frozen screen or stale state, everyone at the table is affected. This must be tested and have a defined behavior before any real players sit down.

**Blocker 3 — Club list empty after join.**
If a player cannot confirm they joined, they will not reach the table. A playtest where participants cannot even get into the game is not a playtest.

**Blocker 4 — Hand result overlay persisting or misfiring between hands.**
If the result of Hand 3 appears during Hand 4, at least one player will say the wrong winner was announced. Trust in the entire session collapses. Must be tested with rapid hand completion before the playtest.

---

## 4. Trust Moments

These are the moments where a player's confidence in the game is either earned or lost:

- **Action registration:** When I tap Fold/Call/Raise, I need immediate visual feedback that my action was received. If I tap Raise and nothing happens, I will tap again. Double-actions in poker are a serious problem.
- **Pot size and chip counts:** Players track these constantly in real poker. If displayed pot or stack sizes are wrong after an action, someone will notice within two hands.
- **Hole card delivery:** When a new hand starts, I need to see my hole cards appear clearly and promptly. Any delay or visual glitch raises "did I get my cards?" anxiety.
- **Showdown accuracy:** The hand result overlay is the verdict. If it shows the wrong hand description or attributes the win to the wrong player, the session is over.
- **Turn notification:** When it is my turn, I need to know immediately. Silent turn transitions lead to awkward pauses.

---

## 5. Session Continuity

These must survive a hiccup for the session to feel like the same game:

**Must survive a reconnect:**
- My chip stack (exact amount)
- My hole cards for the current hand (if mid-hand)
- Current community cards and street
- Whose turn it is and the current action (call amount, raise options)
- My position (dealer, SB, BB)

**Must survive backgrounding:**
- Same as reconnect above
- Ideally a clear visual indicator on return: "You've been away — here's the current state"

**The key principle:** If a player comes back and cannot immediately verify that their chips and position are correct, they spend the next 5 minutes asking the table "is my stack right?" This kills game flow.

---

## 6. Specific Recommendations

Practical changes only — confidence builders, not polish:

1. **Loading state on "Enter Table."** Immediately on tap: disable the button, show "Connecting..." text. Cost: ~30 minutes. Payoff: eliminates the first confusing moment of every session.
2. **Retry button on connection failed.** One button. "Retry" next to the "Failed" text. Cost: 1–2 hours. Payoff: players can self-recover without host intervention.
3. **Club membership confirmation after joining.** After invite code is accepted, show the club name and member count immediately. Cost: 1–2 hours. Payoff: eliminates "did I join?" confusion before it starts.
4. **Define and test background behavior before the playtest.** Simplest acceptable: when app returns to foreground, trigger reconnect and re-fetch table state, show "Reconnecting..." while doing so. Cost: 2–4 hours. Payoff: covers the most common real-world scenario.
5. **Visual feedback on action buttons after tap.** When I tap Fold/Call/Raise, immediately disable buttons. Re-enable only if the server rejects. Cost: 2–3 hours. Payoff: eliminates double-taps.
6. **Test the hand result overlay with back-to-back hands.** Run 10 consecutive hands and verify the overlay clears cleanly every time. Cost: 1–2 hours testing. Payoff: prevents the most trust-damaging visual bug.
7. **"Back online" indicator after successful reconnect.** A brief banner: "Back online." Two seconds. Converts an anxious moment into a confident one. Cost: under 1 hour.

---

## 7. Fairness & Honesty

Moments where a player might feel cheated, even if no actual cheating occurred:

- **No action confirmation:** If I tap Raise and the action does not visibly register, and the game moves on as if I folded, I will blame the app. This is the highest-stakes fairness issue.
- **Stale state after reconnect:** If I reconnect and the pot size shown does not match what I remember, I suspect the game advanced without me. Even if the numbers are correct, lack of a "state restored" message plants doubt.
- **Hand result showing wrong winner:** Even a visual glitch that corrects itself will cause a player to say "the app gave the pot to the wrong person" for the rest of the session.
- **Hole cards visible to others:** The architecture is correct (only your cards sent to you). But any display bug that shows another player's hole cards — even for a frame — ends the session and the host is accused of cheating. Worth a specific visual QA pass.
- **Disconnect during my turn:** If I lose connection when it is my turn and the game auto-folds me without showing that, I will feel robbed. A visible "you were auto-folded while disconnected" message after reconnect would at least make it honest.

---

## 8. What Can Be Deferred

These are real gaps but will not break a friend-group playtest:

- **Table info before entering (blinds, stack, max players):** Nice to have, but friends will just ask the host verbally before joining.
- **Full notification system for turns while app is backgrounded:** Push notifications for turn alerts are a proper feature. For a first playtest where everyone is in the same room, a verbal "hey it's your turn" is fine.
- **Full club management UI:** For a friend group testing with an invite code, the stub is survivable as long as joining works and is confirmed.
- **Bet history / action log:** Players in the same room can track this verbally.
- **UI polish, animations:** These improve feel but do not affect trust or playability. Save for after mechanics are confirmed solid.
- **Sit-out confirmation UX improvement:** Annoying but not a session killer. Players can watch until the next hand starts and check if they are dealt in.

---

## Summary Assessment

**Ready for internal playtest: Conditionally, after 3–4 targeted fixes.**

The core game loop — deal, act, resolve — is functional. The architecture choices are correct. What is missing is not features, it is confidence signals: small moments that tell a player "yes, that worked" or "yes, you're still in the game."

**The four things to fix before putting real friends in front of this app:**

1. Loading state on "Enter Table"
2. Retry button on connection failure
3. Club join confirmation (not an empty list)
4. Defined background/foreground behavior with a "reconnecting" indicator

Fix those four, and a 30-minute friend-group session has a reasonable chance of going smoothly.
