# Feature Spec: Mobile Live Hand Flow

**Feature ID:** mobile-live-hand-flow
**Status:** Approved for implementation
**Date:** 2026-03-19
**Author:** Product (via agent pipeline)

---

## 1. Overview

This feature delivers the live poker hand experience on the mobile table screen. It extends the existing `app/(app)/table/[tableId].tsx` screen — which already handles WS connection, role selection, player list, and connection banners — with four new capabilities:

1. **Live hand display** — community cards, pot, phase, current actor indicator
2. **Action controls** — Fold / Check / Call / Raise buttons (only shown when it is the user's turn and they are in 'playing' status)
3. **Hand result overlay** — winner name, amount, hand description; auto-dismisses in 4 seconds
4. **Spectator mode** — read-only view with no action controls and a "Watching" label

All game logic remains on the server. The client is authoritative for nothing except rendering and sending user intent.

---

## 2. Problem Statement

The current table screen shows a player list and connection status, but provides no live hand information and no way for a player to act on their turn. Users who join as 'player' can sit in but cannot participate in actual hands. Users who join as 'watcher' see the same (empty) experience as players.

---

## 3. Goals

| Goal | Metric |
|------|--------|
| A player can see the live board (phase, community cards, pot) | Manual E2E test TC-M1 |
| A player sees Fold/Check-or-Call/Raise when it is their turn | Manual E2E test TC-M2 |
| A player cannot see or tap action buttons when it is not their turn | TC-08, TC-09 |
| Hand result is shown to all participants at showdown/end | Manual E2E test TC-M4 |
| Spectators see the board but have no action controls | Manual E2E test TC-M6 |
| Reconnect within the same session auto-requests a STATE_SNAPSHOT | TC-M7 |

---

## 4. Design Q&A (All 8 Required Questions)

### Q1: What exact live-hand states are rendered in this phase?

The `HandViewDTO.phase` field drives the board label. The following values are rendered with distinct labels:

| `phase` value | Displayed label |
|---------------|----------------|
| `preflop`     | Pre-Flop        |
| `flop`        | Flop            |
| `turn`        | Turn            |
| `river`       | River           |
| `showdown`    | Showdown        |

Any unrecognized phase value falls back to displaying the raw string. When `current_hand` is `null`, the table shows an idle state: "Waiting for next hand…"

### Q2: What exact information is always visible on the table screen?

The following elements are always rendered (when `gameState` is non-null):

- **Connection banner** — appears when status is not 'connected' (existing component)
- **Table ID** — top header, truncated with `numberOfLines={1}` (existing)
- **My status badge (RoleBadge)** — top-right header corner (existing)
- **Sit-out re-join banner** — shown when my status is 'sit_out' (existing)
- **Hand phase label** — e.g., "Pre-Flop", "Flop"
- **Hand number** — "Hand #42"
- **Total pot** — sum of all `PotDTO.amount` values
- **Community cards** — rendered as card chips; between 0 and 5 cards; face-down placeholder shown if count < expected for phase (MVP: placeholders are grey rectangles; actual card face is rank + suit text)
- **Player rows** — all players, each showing: display_name, stack, current_bet, dealer button indicator, status badge, active-actor highlight (yellow border when `current_actor_id === player.user_id`)
- **My hole cards** — shown ONLY for `your_user_id`; rendered as two card chips; guarded by `player.user_id === gameState.your_user_id` (never rendered for other players even if server sends non-null data)

### Q3: How does the client know when actions are available?

Actions are available if and only if ALL of the following are true, evaluated from `gameState`:

```
isMyTurn = (gameState.current_hand.current_actor_id === gameState.your_user_id)
isPlaying = (myPlayer.status === 'playing')
handInProgress = (gameState.current_hand !== null)
```

The ActionBar component receives these as a single `canAct: boolean` prop derived in the parent screen. When `canAct` is false, the ActionBar renders nothing. When `canAct` is true, the ActionBar renders: Fold, and either Check (if `call_amount === 0`) or Call (showing the call amount), and Raise.

### Q4: How is raise handled in MVP form?

Raise is an inline panel that expands below the action buttons when the user taps "Raise". The panel contains:

- A `Slider` (React Native `@react-native-community/slider` or `react-native`'s built-in `Slider`) with:
  - `minimumValue = min_raise` (from `HandViewDTO.min_raise`)
  - `maximumValue = myPlayer.stack` (player's current stack)
  - `step = 1`
  - Initial value = `min_raise`
- A text display showing the current slider value (e.g., "Raise to: 150")
- A "Confirm Raise" button that calls `sendAction('RAISE', amount)`
- A "Cancel" button that collapses the panel without sending

If `min_raise >= myPlayer.stack` (all-in situation), the Raise button is still offered but the slider has `min === max === myPlayer.stack` (forced all-in). The server enforces validity.

### Q5: How is spectator mode rendered differently from player mode?

A spectator is a user who joined with role `'watcher'`. Their `myPlayer` lookup from `gameState.players` will show `status === 'watcher'` (or they may not appear in the players array at all if the server excludes watchers).

Spectator differences:
- No ActionBar rendered (canAct is always false for watchers)
- No sit-out banner
- No sit-in/sit-out controls
- The RoleBadge in the header shows "Watching" (already handled by existing RoleBadge STATUS_CONFIG)
- Community cards and pot are visible (same as player view)
- Other players' hole cards are NEVER shown (same guard as for players)
- The "You are sitting out" banner is not shown

Implementation: the parent screen checks `myPlayer?.status !== 'playing' && myPlayer?.status !== 'waiting'` (or simply `myStatus === 'watcher'`) before rendering sit-out/sit-in controls. ActionBar's `canAct` naturally resolves to false because `myPlayer.status !== 'playing'`.

### Q6: What hand-result information is shown in the first playable version?

When the server sends a `HAND_ENDED` event, a modal overlay appears showing:

- For each winner: display_name (looked up from `gameState.players`) + amount won + `hand_description` (if present)
- The final board (community cards at end of hand) from `final_board` field
- If showdown: each `showdown_hands` entry shows player display_name + their hole cards + `hand_description` — but only if the user is the player themselves OR if the server included that player's cards (the client does not enforce privacy for showdown data since the server explicitly sends it)
- The overlay auto-dismisses after 4 seconds via `setTimeout`
- The overlay also dismisses immediately on user tap (TouchableOpacity overlay background)

The `HAND_ENDED` payload is stored in a separate `handResult` field in the tableStore (new field) and cleared either on dismiss or on next `HAND_STARTED`.

### Q7: What reconnect behavior is supported inside the live table screen?

Reconnect is handled by the existing `SocketClient` exponential backoff (1s / 2s / 4s, max 3 attempts). The live hand screen adds:

- When `connectionStatus` transitions from `reconnecting` / `connecting` back to `connected`, the store calls `sendJoin` again with the preserved role to re-register with the server
- After re-join, the server responds with `STATE_SNAPSHOT` which refreshes `gameState` automatically
- If the user was in the middle of acting (ActionBar visible), the ActionBar remains rendered pending the new snapshot; if the new snapshot shows a different actor, it simply re-evaluates `canAct`
- If `connectionStatus === 'failed'` (all 3 attempts exhausted), the screen shows the existing red ConnectionBanner and the ActionBar is hidden (canAct=false); the user must leave the screen and re-enter to retry

The AppState listener already handles background → foreground reconnect (existing in tableStore). No additional reconnect logic is needed in this feature beyond sending JOIN after reconnect.

### Q8: What important table-screen behaviors are explicitly deferred?

The following are explicitly out of scope for the MVP of this feature:

| Deferred item | Reason |
|---------------|--------|
| Animated card dealing | Complexity; phase 2 |
| Seat-based circular table layout | Requires layout engine work; phase 2 |
| Timer/clock for actor turn | Requires server-sent timer data not in current DTO |
| Chat (CHAT event) | UI surface not designed yet |
| Multi-pot (side pot) display | MVP shows total pot only; multiple PotDTOs merged |
| Sound effects | Audio permissions and asset pipeline not yet established |
| Sit-in during a live hand (mid-hand join) | Handled by server; client just sends SIT_IN, server responds with status change |
| Disconnected-player reserve timer countdown | `reserve_until` field exists but real-time countdown deferred |
| Landscape / tablet layout | Portrait only for MVP |
| SYNC_REQUEST on manual pull-to-refresh | Deferred; reconnect covers the primary recovery path |

---

## 5. Backend Contract Summary (Do Not Modify Backend)

### Events consumed

| Event | Trigger | Client action |
|-------|---------|---------------|
| `STATE_SNAPSHOT` | After JOIN or SYNC_REQUEST | Replace entire `gameState` in store |
| `HAND_STARTED` | New hand begins | Store in `handResult` slot, clear previous result; `gameState` is also refreshed by next STATE_SNAPSHOT |
| `HAND_ENDED` | Hand concludes | Store `HandEndedPayload` in `tableStore.handResult`; show result modal |
| `PLAYER_ACTED` | Any player acts | Replaced by subsequent STATE_SNAPSHOT from server; no client-side state mutation |
| `PLAYER_STATUS` | Player status changes | Replaced by subsequent STATE_SNAPSHOT; no client-side state mutation |
| `ERROR` | Server validation failure | Display `error` field; existing behavior |

### Events sent

| Event | When | Payload |
|-------|------|---------|
| `JOIN` | On connect (and on reconnect) | `{ role: 'player' | 'watcher' }` |
| `FOLD` | User taps Fold | `{}` |
| `CHECK` | User taps Check | `{}` |
| `CALL` | User taps Call | `{}` |
| `RAISE` | User confirms raise | `{ amount: number }` |
| `SIT_OUT` | User taps sit-out | `{}` (existing) |
| `SIT_IN` | User taps sit-in banner | `{}` (existing) |

---

## 6. New TypeScript Types Required

```typescript
// src/ws/types.ts — append (do not modify existing types)

export interface HandEndedWinner {
  user_id: string;
  amount: number;
  hand_description: string;
}

export interface HandEndedShowdownEntry {
  user_id: string;
  hole_cards: CardDTO[];
  hand_description: string;
}

export interface HandEndedPayload {
  hand_id: string;
  hand_number: number;
  winners: HandEndedWinner[];
  final_board: CardDTO[];
  showdown_hands: HandEndedShowdownEntry[]; // may be empty if no showdown
}
```

---

## 7. Store Changes Required

`tableStore.ts` needs two additions:

1. `handResult: HandEndedPayload | null` — set when HAND_ENDED received; cleared by `clearHandResult()` or on HAND_STARTED
2. `clearHandResult: () => void` — called by modal on dismiss or auto-dismiss timeout
3. Handler for `HAND_ENDED` in the `onMessage` callback: parse payload as `HandEndedPayload`, set `handResult`
4. Handler for `HAND_STARTED`: clear `handResult` so stale result is not shown

---

## 8. Acceptance Criteria

- [ ] A player who is the current actor sees Fold, Check/Call, Raise buttons
- [ ] A player who is not the current actor sees no action buttons
- [ ] A watcher sees no action buttons
- [ ] Tapping Fold sends `FOLD` WS message
- [ ] Tapping Check sends `CHECK` (only when call_amount === 0)
- [ ] Tapping Call sends `CALL` (only when call_amount > 0), button label shows the amount
- [ ] Tapping Raise opens the raise panel with slider bounded by [min_raise, myStack]
- [ ] Confirming raise sends `RAISE` with the selected amount
- [ ] My hole cards are shown (rank + suit) when I have 2 cards in `hole_cards`
- [ ] Other players' hole cards are NEVER shown, even if the server returns non-null
- [ ] Community cards are shown as card chips (up to 5)
- [ ] Phase label and hand number are shown
- [ ] Total pot amount is shown
- [ ] Each player row shows: name, stack, current_bet, dealer indicator, actor highlight
- [ ] HAND_ENDED shows winner(s), amount, hand_description overlay
- [ ] Hand result overlay dismisses on tap or after 4 seconds
- [ ] After reconnect, JOIN is re-sent with the preserved role
- [ ] ConnectionBanner shows correctly for all non-connected states (existing)
