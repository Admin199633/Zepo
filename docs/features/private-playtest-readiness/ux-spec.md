# UX Specification: private-playtest-readiness

**Version:** 1.0
**Date:** 2026-03-19
**Scope:** Club list empty state, club detail table config, table entry flow hardening, loading/failure/recovery states, connection feedback, sit-in confirmation.

Design token reference: background `#0F172A`, surface `#1E293B`, border `#334155`, text primary `#F8FAFC`, text muted `#64748B`, text secondary `#94A3B8`, action blue `#2563EB`, success `#166534`/`#86EFAC`, error `#991B1B`/`#F87171`, warning amber `#B45309`/`#EAB308`, purple `#7C3AED`.

---

## 1. Screen-by-Screen UX Changes

---

### 1.1 Club List Screen — `/(app)/index`

#### 1.1.1 Loading State
While `loading === true`:
- Full-screen centered `ActivityIndicator`, size "large", color `#2563EB`.
- No text. Replaces the current inline "Loading…" muted text.

#### 1.1.2 API Error State
If fetch throws:
- Full-screen centered layout.
- Primary text: "Couldn't load your clubs" — fontSize 18, fontWeight "700", color `#F8FAFC`, marginTop 16.
- Secondary text: extracted error message — fontSize 14, color `#94A3B8`, textAlign "center", marginTop 4.
- Button: "Try again" — primary variant (`#2563EB`), full-width, borderRadius 10, paddingVertical 14, marginTop 24.

#### 1.1.3 Empty State (primary gap)
When `clubs.length === 0` and no error:
- Full-screen centered layout, padding 32.
- Icon placeholder: 64×64 rounded rect `#1E293B`, centered, containing a 2×2 grid of 24×28 `#334155` rounded rects (card-back indicator).
- Primary heading: "No clubs yet" — fontSize 20, fontWeight "700", color `#F8FAFC`, marginTop 20.
- Body: "Ask a club owner to share their invite code, then enter it below to join." — fontSize 15, color `#94A3B8`, textAlign "center", lineHeight 22, marginTop 8.
- **Invite-code input field**, marginTop 24:
  - Placeholder: "Enter invite code"
  - Placeholder color: `#64748B`
  - Text color: `#F8FAFC`
  - Background: `#1E293B`
  - Border: 1px `#334155`, borderRadius 10, paddingVertical 14, paddingHorizontal 16
  - `autoCapitalize="characters"`, `autoCorrect={false}`, `maxLength={12}`
- **"Join Club" button**: primary variant, full-width, marginTop 12.
  - Disabled (opacity 0.4) when input is empty.
  - During join call: shows `ActivityIndicator` size "small" color `#fff` in place of label; input disabled.
  - On error: `ErrorDisplay` below the button with extracted error message; button re-enables.
- **Separator**: `#1E293B` height 1, full-width, marginTop 32.
- **"Create Club" section** (below separator):
  - Label: "Or start your own" — fontSize 12, fontWeight "600", color `#64748B`, letterSpacing 1, textAlign "center", marginTop 16.
  - "Create Club" secondary button (transparent, border `#334155`), marginTop 8. Stubbed this phase — tapping shows inline muted "Coming soon" text.

#### 1.1.4 Populated State
No changes to existing card layout or navigation.

---

### 1.2 Club Detail Screen — `/(app)/clubs/[clubId]`

#### 1.2.1 Loading State
While `isLoadingClub === true`:
- Full-screen centered `ActivityIndicator`, size "large", color `#2563EB`.

#### 1.2.2 API Error State (improved)
Replace current raw text error with:
- `ErrorDisplay` component (existing: `#1E293B` surface, `#F87171` left border).
- Below it: "Try again" primary button, marginTop 16. Tapping calls `fetchClub(clubId)`.

#### 1.2.3 Table Config Card (new)
Shown between the invite code section and "Enter table" button when `tableInfo !== null`:
- Container: `#1E293B`, borderRadius 12, padding 16, marginBottom 24, border 1px `#334155`.
- Section label: "Table" — fontSize 11, fontWeight "600", color `#64748B`, letterSpacing 1, marginBottom 10.
- Three stat rows, each `flexDirection: "row"`, `justifyContent: "space-between"`, paddingVertical 6, separated by `#334155` 1px lines:
  - Row 1 — "Blinds" | `{small_blind} / {big_blind}`
  - Row 2 — "Starting stack" | `{starting_stack} chips`
  - Row 3 — "Max players" | `{max_players}`
- Label text: color `#94A3B8`, fontSize 14.
- Value text: color `#F8FAFC`, fontWeight "600", fontSize 14.
- While `isLoadingTable === true`: inline `ActivityIndicator` size "small" color `#2563EB` in a 96-height placeholder (prevents layout jump).
- If `tableInfo` fetch failed: one-line muted "Table info unavailable" (color `#64748B`, fontSize 14) in place of card. "Enter table" button still shown.

#### 1.2.4 Enter Table Flow
Immediately on tap:
- Button background stays `#2563EB`.
- Label replaced by `ActivityIndicator` size "small" color `#fff`.
- Button becomes non-tappable.
- Navigation fires synchronously (the WS connects on the table screen).

---

### 1.3 Table Screen — `/(app)/table/[tableId]`

#### 1.3.1 WS Connecting State (`connectionStatus === 'connecting'`, `gameState === null`)
Replace muted "Connecting…" text with:
- `ActivityIndicator` size "large" color `#2563EB`, centered.
- Text below: "Connecting to table…" — fontSize 15, color `#64748B`, marginTop 12.
- `ConnectionBanner` (blue) still appears at top.
- Role modal does NOT appear during this state.

#### 1.3.2 Join-Pending State (`joined && gameState === null && connectionStatus === 'connected'`)
After role selection but before first `STATE_SNAPSHOT`:
- Centered overlay (replaces scroll area content):
  - `ActivityIndicator` size "large" color `#2563EB`.
  - Text below: "Joining table…" — fontSize 15, color `#94A3B8`, marginTop 12.
- Overlay disappears as soon as `gameState` becomes non-null.

#### 1.3.3 In-Lobby State (`gameState !== null && current_hand === null`)
Replace single muted "Waiting for next hand…" line with:
- Primary text: "Waiting for next hand" — fontSize 17, fontWeight "600", color `#F8FAFC`, textAlign "center".
- Secondary text: "{n} players at the table" — fontSize 14, color `#64748B`, textAlign "center", marginTop 4.
- `PlayerList` renders below (unchanged).

#### 1.3.4 Failed State (all 3 reconnect attempts exhausted)
Replace current static `ConnectionBanner` content for `status === 'failed'` with a taller banner:
- Background: `#7F1D1D`.
- Layout: `flexDirection: "column"`, paddingVertical 14, paddingHorizontal 16.
- Line 1: "Connection failed" — fontSize 14, fontWeight "700", color `#FECACA`, textAlign "center".
- Line 2: "Unable to reach the server after 3 attempts." — fontSize 12, color `#FCA5A5`, textAlign "center", marginTop 2.
- **"Retry Connection" button**, marginTop 10:
  - Background: `#EF4444`, borderRadius 8, paddingVertical 8, paddingHorizontal 20, alignSelf "center".
  - Label: "Retry Connection" — fontSize 13, fontWeight "700", color `#fff`.
  - `accessibilityLabel="Retry connection"`.
  - Tapping calls `tableStore.connect(tableId, token)`.
- Last known `gameState` content (if any) remains visible beneath the banner.

#### 1.3.5 Disconnected / Foreground-Resume State
When `connectionStatus === 'connecting'` following a background→foreground transition:
- **Resync pill** overlaid at top of scroll area:
  - Absolute position: top 8, alignSelf "center".
  - Background: `#1E3A5F`, borderRadius 20, paddingVertical 4, paddingHorizontal 12.
  - Text: "Refreshing…" — fontSize 12, fontWeight "600", color `#93C5FD`.
  - Disappears when `connectionStatus` returns to `'connected'`.

#### 1.3.6 Sit-Out / Sit-In Confirmation
Add `sitInPending: boolean` local state (useState, default false):
- On tap: `sitInPending = true`, call `sendSitIn()`.
- While `sitInPending === true`: banner text → "Sending request…"; `TouchableOpacity` disabled (opacity 0.6).
- Clear `sitInPending` when `myStatus` changes away from `'sit_out'` (useEffect on `myStatus`).
- Timeout: reset `sitInPending` to false after 5s if `myStatus` has not changed.

#### 1.3.7 WS Error Message (server ERROR envelope)
Add below `ConnectionBanner`:
- Condition: `error !== null && connectionStatus === 'connected'`.
- `ErrorDisplay` component with `error` string.
- Dismiss "×" button: 32×32 hit target, calls `useTableStore.setState({ error: null })`. `accessibilityLabel="Dismiss error"`.
- Auto-dismisses after 6 seconds.

#### 1.3.8 Reconnect Success Banner
Change copy from "Reconnected" to "Back online" (more natural for live poker).

---

## 2. State Machine

### 2.1 ConnectionBanner States

| Status | Visible | Background | Content |
|--------|---------|------------|---------|
| `connected` | No | — | Nothing rendered |
| `connecting` | Yes | `#1D4ED8` | "Connecting…" centered |
| `reconnecting` | Yes | `#B45309` | "Reconnecting… ({n}/3)" centered |
| `failed` | Yes (taller) | `#7F1D1D` | "Connection failed" + "Unable to reach the server after 3 attempts." + "Retry Connection" button |
| `disconnected` | Yes | `#374151` | "Disconnected" centered (no retry — foreground reconnect is automatic) |

**Transitions:**
- `disconnected` → `connecting`: `connect()` called (mount or foreground resume)
- `connecting` → `connected`: WS `onopen`
- `connecting` → `reconnecting`: first `onclose` (attempt 1/3)
- `reconnecting` → `connected`: `onopen` during retry
- `reconnecting` → `failed`: attempt >= 3 with no `onopen`
- `failed` → `connecting`: user taps "Retry Connection" → `connect()` called
- `connected` → `disconnected`: `disconnect()` called

### 2.2 Table Screen States

| State | Condition | What User Sees |
|-------|-----------|----------------|
| `ws-connecting` | `connectionStatus === 'connecting'` | Blue ConnectionBanner + spinner + "Connecting to table…" |
| `ws-reconnecting` | `connectionStatus === 'reconnecting'` | Amber ConnectionBanner + last known content |
| `role-select` | `connectionStatus === 'connected' && !joined` | Role selection modal |
| `join-pending` | `connected && joined && gameState === null` | Spinner + "Joining table…" |
| `in-lobby` | `connected && gameState && !current_hand` | "Waiting for next hand" + player count + PlayerList |
| `in-hand` | `connected && gameState && current_hand` | Full table view (HandInfoBar, CommunityCards, PlayerList, optional ActionBar) |
| `ws-failed` | `connectionStatus === 'failed'` | Red taller ConnectionBanner with "Retry Connection" button |
| `ws-disconnected` | `connectionStatus === 'disconnected'` | Grey ConnectionBanner; resync pill on foreground return |
| `sit-out-pending` | `myStatus === 'sit_out' && sitInPending` | "Sending request…" banner (dimmed) |
| `sit-out-idle` | `myStatus === 'sit_out' && !sitInPending` | "You are sitting out — Tap to rejoin" |

**Render order (top of screen):**
1. "Back online" flash banner (green, 2s transient)
2. ConnectionBanner
3. WS error inline display
4. Screen header
5. Sit-out banner
6. Scroll area content

---

## 3. Error Messaging

All exact user-facing copy:

| Trigger | Copy |
|---------|------|
| WS failed (3 retries) | Line 1: "Connection failed" / Line 2: "Unable to reach the server after 3 attempts." / Button: "Retry Connection" |
| WS disconnected (intentional) | "Disconnected" (banner only) |
| Club list API error | Heading: "Couldn't load your clubs" / Body: extracted error / Button: "Try again" |
| Club detail API error | `{extractErrorMessage(err)}` in `ErrorDisplay` / Button: "Try again" |
| Table info fetch error | "Table info unavailable" (inline muted, no button — entry still allowed) |
| Join club invite code error | `{extractErrorMessage(err)}` in inline `ErrorDisplay` below Join button |
| WS `ERROR` envelope | `{envelope.payload.message}` in dismissible `ErrorDisplay`, auto-dismisses after 6s |
| Sit-in request sent | "Sending request…" (replaces sit-out banner text) |
| Sit-in request timed out | Banner reverts silently to "You are sitting out — Tap to rejoin" |
| Foreground resync | "Refreshing…" (pill, top of scroll area) |

---

## 4. Loading States

| Context | Component | Condition |
|---------|-----------|-----------|
| Club detail | `ActivityIndicator` (large, blue), full-screen centered | `isLoadingClub === true` |
| Table info (within club detail) | `ActivityIndicator` (small, blue), inline 96h placeholder | `isLoadingTable === true` |
| Table entry / WS connecting | `ActivityIndicator` (large, blue) + "Connecting to table…" text, scroll area centered | `connectionStatus === 'connecting'` |
| After role selection | `ActivityIndicator` (large, blue) + "Joining table…" text, scroll area centered | `joined && gameState === null && connectionStatus === 'connected'` |

---

## 5. Empty States

### 5.1 Club List — No Clubs
Full spec in §1.1.3 above. Summary: card-back placeholder, "No clubs yet" heading, body copy, invite-code input, "Join Club" button, separator, stubbed "Create Club" button.

### 5.2 Waiting for Hand (In-Lobby)
Shown when `gameState !== null && current_hand === null`:
- "Waiting for next hand" — fontSize 17, fontWeight "600", color `#F8FAFC`, textAlign "center".
- "{n} players at the table" — fontSize 14, color `#64748B`, marginTop 4.
- No spinner (connected and idle, not loading).

---

## 6. Recovery Actions

| Action | Location | Trigger | Behavior |
|--------|----------|---------|----------|
| "Retry Connection" | ConnectionBanner (`failed` state) | User tap | `tableStore.connect(tableId, token)` — resets attempt counter |
| "Try again" (club detail) | Below `ErrorDisplay` | User tap | `fetchClub(clubId)` |
| "Try again" (club list) | Error state | User tap | Re-run `getUserClubs()` |
| "Join Club" | Empty state invite input | User tap | `joinClub(inviteCode)` → navigate |
| Foreground resync | Automatic | AppState `active` | `connect()` if disconnected; `SYNC_REQUEST` if connected |

---

## 7. Copy Standards

### Club List Screen
| Context | String |
|---------|--------|
| Empty state heading | "No clubs yet" |
| Empty state body | "Ask a club owner to share their invite code, then enter it below to join." |
| Invite input placeholder | "Enter invite code" |
| Join button | "Join Club" |
| Create section label | "Or start your own" |
| Create button | "Create Club" |
| Create stub response | "Coming soon" |
| Error heading | "Couldn't load your clubs" |
| Retry button | "Try again" |

### Club Detail Screen
| Context | String |
|---------|--------|
| Table Config section label | "Table" |
| Blinds row label | "Blinds" |
| Stack row label | "Starting stack" |
| Stack value suffix | "chips" (e.g., "1000 chips") |
| Max players row label | "Max players" |
| Table info unavailable | "Table info unavailable" |
| Retry button | "Try again" |

### Table Screen
| Context | String |
|---------|--------|
| Connecting spinner text | "Connecting to table…" |
| Join-pending spinner text | "Joining table…" |
| In-lobby heading | "Waiting for next hand" |
| In-lobby subhead | "{n} players at the table" |
| Sit-out banner (idle) | "You are sitting out — Tap to rejoin" |
| Sit-out banner (pending) | "Sending request…" |
| Reconnected flash banner | "Back online" |
| Foreground resync pill | "Refreshing…" |
| Error dismiss button | "×" (accessibilityLabel: "Dismiss error") |

### ConnectionBanner
| Status | Line 1 | Line 2 | Button |
|--------|--------|--------|--------|
| connecting | "Connecting…" | — | — |
| reconnecting | "Reconnecting… ({n}/3)" | — | — |
| failed | "Connection failed" | "Unable to reach the server after 3 attempts." | "Retry Connection" |
| disconnected | "Disconnected" | — | — |

---

## 8. What Is NOT Changed in This Phase

These are explicitly out of scope and must not be modified:

1. Circular/oval seat layout — `PlayerList` remains a vertical list
2. Animations and transitions of any kind
3. Chat UI (CHAT event type exists but no UI)
4. `HandResultOverlay` component
5. `ActionBar` Fold/Check/Call/Raise controls
6. `CommunityCards`, `MyHoleCards`, `HandInfoBar` components
7. Dealer badge in `PlayerList`
8. Authentication screens (`/(auth)/login` and `/(auth)/verify`)
9. Push notifications
10. Toast libraries — all feedback uses inline banners consistent with existing pattern
11. Haptics
12. Dark/light mode theming (dark-only)
13. `PING/PONG` keep-alive mechanism
14. Navigation header (all screens use `headerShown: false`)
15. Card backs styling in `PlayerList`
16. Turn timer display
17. Hand history screen
18. Player profile screens
