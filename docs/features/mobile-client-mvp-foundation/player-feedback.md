# Player Feedback — mobile-client-mvp-foundation

> Agent: Poker Player Reviewer
> Date: 2026-03-19

---

## Reviewer Perspective

Reviewing as a regular friend-group Texas Hold'em player who plays on a phone with friends. I'm used to other apps (PokerNow, ClubGG) and I know what getting to the table fast feels like — and what getting stuck in a flow feels like.

---

## What Feels Natural

### OTP Login
Phone number + code is the right auth method for friend-group poker. I don't want another password. My friends and I all know each other's numbers. This is natural.

### Clubs as the organizing unit
Having a "Clubs" concept that I'm a member of feels like how real home games work. I'm in my Thursday group, my work group, etc. This framing is correct. The clubs list as the home screen is the right starting point.

### Seeing blinds and player count before joining
If I'm about to sit down at a table, I want to know:
- How many people are at the table (is there room?)
- What the blinds are (am I in the right game?)
The fact that this is shown before I commit to joining feels correct.

### Explicit player vs spectator choice
Being asked "Join as Player" vs "Watch as Spectator" is the right pattern. In a real home game you sometimes just want to watch before buying in. Having this as a first-class choice is good. It should be obvious which is which — not buried in a sub-menu.

### Reconnect with a banner (not a hard error)
If my connection drops, I want a banner that says "Reconnecting..." and then goes away when it reconnects. I do NOT want to be kicked to a menu screen and have to re-join manually every time WiFi blips. This is how good mobile apps handle it.

### Seeing the player list immediately on join
After I join, I want to know who's at the table. Seeing the player list (name, stack, status) immediately from the STATE_SNAPSHOT is the right behavior.

---

## What Feels Confusing or Missing

### No "create club" from app (deferred)
If I'm a first-time user and there's no club to join, the empty state will feel dead. Even if I have to create the club from a different screen later, the empty clubs list with no obvious "what do I do?" is a friction point. The empty state should at minimum tell me what a club is and why I don't have one — not just show a blank screen.

### No "join by invite" from app (deferred)
If a friend sends me an invite code (WhatsApp, SMS), I need somewhere to paste it. Without this, onboarding new players requires backend-direct interaction, which no normal player can do. This should be deferred only if the dev/founder flow is the primary usage in this phase.

### Table screen is a placeholder (acceptable for MVP)
I understand the actual card UI isn't here yet. But the table screen placeholder must clearly indicate "game in progress" vs "waiting for players" vs "you're connected". A blank screen or loading spinner with no context is disorienting.

### Spectator mode is not visually distinguished
When I'm spectating vs playing, I should know which mode I'm in at a glance. If the screen looks identical regardless of role, I might forget I'm watching and think I can act.

### Sit-out status after reconnect
If I was disconnected long enough to be moved to SIT_OUT, the app should clearly tell me "You've been moved to sit out — tap to rejoin." Not just show my status as sit_out without explanation. (This is a UX gap to address when the table UI is built, but should be designed into the table screen from the start.)

---

## Flow Assessment

### Entry flow speed
Login (2 steps) → Clubs list → Club detail → Table entry = 4 taps minimum. That's fine. It's not 2 taps but it's not 8 either.

### The critical path
For a player who already has the app:
1. Open app → see clubs list (token already stored)
2. Tap club → see table entry
3. Tap "Join as Player" → connected

That's 3 taps from app open to connected. Good.

For a new player:
1. Enter phone → get OTP → enter code → see clubs list
2. Empty → needs to join a club somehow (gap noted above)

### Reconnect path
Disconnect → banner appears → auto-reconnect → banner disappears. Player doesn't have to do anything. This is correct.

Manual reconnect (after 3 auto attempts fail) → button "Tap to reconnect" visible. Player taps → tries again. Correct.

---

## What Would Most Improve Confidence

1. **Clear empty state with instructions** — When clubs list is empty, explain how to get started (even if the button isn't there yet)
2. **Role indicator always visible on table screen** — Small badge showing "Playing" or "Watching" at all times
3. **Status explanation after reconnect-as-sit-out** — Even if it's just text: "You were away too long. You're sitting out."
4. **Fast auth (skip OTP screen if token exists)** — This is the most important UX speedup — returning users should skip login entirely

---

## Overall Assessment

The entry flow is natural and correctly structured for a friend-group poker app. The key risks are the deferred "create club" and "join by invite" flows, which will hurt first-session onboarding for non-developer users. For the MVP foundation phase this is acceptable as long as the empty state is handled with real guidance. The reconnect behavior is the most important real-time UX concern and the proposed design (banner, auto-retry, manual fallback) is correct.

**Approved for implementation** with the following mandatory UX requests:
- Empty clubs list must have descriptive guidance text, not a blank screen
- Role badge (Playing / Watching) must be visible on the table screen from day one
- Token bypass on app startup must be implemented (returning users skip login)
