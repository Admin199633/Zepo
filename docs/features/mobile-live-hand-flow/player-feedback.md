# Player Feedback Spec: Mobile Live Hand Flow

**Feature:** mobile-live-hand-flow
**Date:** 2026-03-19

This document defines every piece of feedback the app gives to the user during a live hand — visual states, labels, error messages, and timing.

---

## 1. Action Availability Feedback

### 1.1 Your Turn — Action Bar Appears

When `current_actor_id === your_user_id` AND `myPlayer.status === 'playing'`, the ActionBar animates in from the bottom of the screen (slide-up, 200ms ease-out).

The active actor's player row receives a yellow border highlight (`borderColor: '#EAB308'`, `borderWidth: 2`) to visually indicate "it's your turn" in the player list as well.

### 1.2 Not Your Turn — Action Bar Hidden

When it is not the user's turn, the ActionBar is not mounted. There is no disabled/greyed-out button state — the buttons simply do not exist. This avoids confusion about tappable elements.

### 1.3 Spectator — No Action Bar

Watchers never see the ActionBar at all. Their header badge reads "Watching" (blue background, from existing `RoleBadge` STATUS_CONFIG).

---

## 2. Action Button Labels

| Condition | Button shown | Label |
|-----------|-------------|-------|
| `call_amount === 0` | Check | "Check" |
| `call_amount > 0` | Call | "Call 150" (amount appended) |
| Always | Fold | "Fold" |
| Always | Raise | "Raise" |

The Call button label dynamically reflects `HandViewDTO.call_amount`. If `call_amount` changes between renders (e.g., a new snapshot arrives mid-interaction), the label updates immediately.

---

## 3. Raise Panel Feedback

When the user taps "Raise":

- The raise panel slides up inline below the four action buttons (not a modal)
- A slider appears with label: `"Raise to: {value}"` where `{value}` is the current slider position
- Minimum value = `HandViewDTO.min_raise`, Maximum value = `myPlayer.stack`
- If `min_raise === myPlayer.stack`, the slider is disabled and the label reads `"All-in: {value}"`
- Two buttons: "Confirm Raise" (primary style, blue) and "Cancel" (secondary style, grey)
- Tapping Cancel collapses the panel with a slide-down animation (200ms); no message sent
- Tapping Confirm sends `RAISE { amount }` and immediately collapses the panel; action buttons disappear (canAct re-evaluates after next snapshot)

---

## 4. Hole Card Display

### 4.1 My Cards

When `myPlayer.hole_cards` is non-null and non-empty (always 2 in a standard hand), two card chips appear in a row labeled "Your Cards" above the action bar (or in my player row, whichever the UX spec chooses — see ux-spec.md).

Each card chip shows rank and suit as text, e.g., "A♠", "K♥". Suit symbols:
- `s` → ♠ (black)
- `h` → ♥ (red, `#EF4444`)
- `d` → ♦ (red, `#EF4444`)
- `c` → ♣ (black)

Card background: `#1E293B` with a white border `#F8FAFC`. Card size: 44×60 dp.

### 4.2 Other Players' Cards

Other players' cards are NEVER shown. The guard in `CardChip` and in the rendering parent is:

```tsx
const showCards = player.user_id === gameState.your_user_id && player.hole_cards !== null;
```

Even if the server sends `hole_cards` for another player (which it should not, but as a safety net), the client never renders them. Face-down placeholder cards (grey rectangle, same size) are shown in each player row to indicate "this player has cards" without revealing them.

---

## 5. Community Card Display

Community cards are shown as a horizontal row of card chips. The number rendered equals `community_cards.length`. Empty slots are not shown (MVP defers phase-based empty-slot placeholders).

- 0 cards: label "Waiting for flop…" shown in the community card zone
- 3 cards (flop): three card chips
- 4 cards (turn): four card chips
- 5 cards (river/showdown): five card chips

Label above the row: the phase label (e.g., "Flop", "Turn").

---

## 6. Player Row Feedback During a Hand

Each player row in the player list shows (in addition to existing name/stack/badge):

| Element | Condition | Display |
|---------|-----------|---------|
| Dealer button | `player.is_dealer === true` | "D" badge, gold background |
| Current bet | `player.current_bet > 0` | Grey sub-label "Bet: {amount}" |
| Actor highlight | `player.user_id === current_actor_id` | Yellow border on the row |
| My row highlight | `player.user_id === your_user_id` | Blue border (existing behavior) |
| Face-down card indicators | `player.status === 'playing'` AND `player.user_id !== your_user_id` | Two grey 14×18 dp card rectangles |
| Sit-out dim | `player.status === 'sit_out'` | Row opacity 0.5 |
| Disconnected dim | `player.status === 'disconnected'` | Row opacity 0.4, italic name |

When both the actor highlight and my-row highlight apply (it's my turn), actor highlight (yellow) takes precedence.

---

## 7. Pot Display

The pot area shows the total pot: `pots.reduce((sum, p) => sum + p.amount, 0)`.

Label: "Pot: {total}"

MVP does not break down side pots. If there are multiple PotDTOs, only the summed total is shown.

---

## 8. Hand Result Overlay Feedback

When `HAND_ENDED` is received, a semi-transparent overlay appears over the table with:

```
[Confetti animation — deferred to phase 2]

  Hand #42 Complete

  Alice wins 300 chips
  "Full House, Aces full of Kings"

  Bob wins 150 chips (side pot)
  "Two pair, Kings and Jacks"

  [Final Board: A♠ A♥ A♦ K♠ J♥]

  Tap anywhere to dismiss
```

- Auto-dismiss timer: 4 seconds after appearance
- Manual dismiss: tap anywhere on the overlay
- Transition: fade in (300ms), fade out (200ms)
- Background: `rgba(0, 0, 0, 0.85)`
- Text color: `#F8FAFC` for winner name, `#86EFAC` for amount, `#94A3B8` for hand_description
- If `showdown_hands` is non-empty, each player's hole cards at showdown are shown below the winner block (no privacy restriction at showdown — server explicitly sends these)
- If `hand_description` is empty string or missing, that line is omitted

---

## 9. Error Feedback

When the server sends an `ERROR` event (e.g., "Not your turn", "Invalid raise amount"), the existing `tableStore.error` field is set.

The error is shown as a red banner below the connection banner:

```
"Error: Not your turn"
```

- Red background `#991B1B`, white text
- Auto-clears after 5 seconds OR when the next `STATE_SNAPSHOT` is received (which sets `error: null`)
- Does not block the UI

---

## 10. Connection Feedback During a Hand

The existing `ConnectionBanner` handles this. Additional behavior specific to live hands:

- When `connectionStatus !== 'connected'`, the ActionBar is hidden even if the last snapshot showed it was the user's turn. This prevents sending actions over a dead socket.
- When `connectionStatus` becomes `'failed'`, an additional line appears below the red banner: "Leave the table and rejoin to continue."
- When `connectionStatus` returns to `'connected'` (after a reconnect), a brief green flash banner ("Reconnected") is shown for 2 seconds, then fades. This is implemented as a local component state in the table screen.

---

## 11. Waiting States

| Scenario | Feedback shown |
|----------|---------------|
| `gameState === null` AND `connectionStatus === 'connected'` | "Waiting for game state…" centered text (existing) |
| `gameState` exists but `current_hand === null` | "Waiting for next hand…" shown in the hand zone |
| `gameState.current_hand` exists but `current_actor_id === null` | Phase label and pot shown; no actor highlight; no ActionBar |
| Hand phase is `showdown` | Phase label "Showdown"; community cards shown; no ActionBar |

---

## 12. Sit-Out / Sit-In Banner

Existing behavior preserved. Additional: when a HAND_ENDED overlay is visible at the same time as the sit-out banner, the overlay takes z-index precedence and the banner is hidden behind it until dismissed.
