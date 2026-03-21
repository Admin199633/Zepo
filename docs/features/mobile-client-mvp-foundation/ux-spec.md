# UX Spec — mobile-client-mvp-foundation

> Agent: Senior UI/UX Designer
> Date: 2026-03-19

---

## Design Principles

1. **Speed to table** — Every decision that slows down the path from app open to seat is a problem.
2. **Clarity of role** — Player vs spectator must be unambiguous at all times once at the table.
3. **Graceful degradation** — Connection errors and loading states must be informative, not terrifying.
4. **Mobile-first** — Large tap targets, minimal text input, single-column layouts on small screens.
5. **No chrome** — No persistent navigation bar in MVP. Navigation is contextual (back button, inline CTAs).

---

## Screen Inventory

| # | Screen | Route | Access |
|---|--------|-------|--------|
| S1 | Login | `/auth/login` | Unauthenticated |
| S2 | Verify OTP | `/auth/verify` | After phone submitted |
| S3 | Clubs List | `/(app)/` | Authenticated |
| S4 | Club Detail | `/(app)/clubs/[clubId]` | Club member |
| S5 | Table Screen | `/(app)/table/[tableId]` | Club member |

---

## Navigation Structure

```
Root (_layout.tsx)
├── (auth) group — shown when no valid token
│   ├── login        S1
│   └── verify       S2
└── (app) group — shown when valid token exists
    ├── index        S3 (Clubs List / Home)
    ├── clubs/
    │   └── [clubId] S4 (Club Detail)
    └── table/
        └── [tableId] S5 (Table Screen)
```

On app launch:
- Token exists and not expired → navigate to `(app)/` (S3)
- No token or expired → navigate to `(auth)/login` (S1)

On logout or 401 error:
- Clear token → navigate to `(auth)/login`

---

## S1 — Login Screen

**Primary action**: Enter phone number → "Send Code"

**Layout**:
```
[App name / logo wordmark]

[Large phone number input — E.164 format]
[Country picker or +prefix field]

[Send Code button — full-width, prominent]

[Small text: "We'll send a 6-digit code to this number"]
```

**States**:
- **Idle**: field empty, button disabled
- **Valid phone**: button enabled
- **Loading**: button shows spinner, field disabled
- **Error**: error message below field ("Invalid phone number" / "Too many attempts")

**Notes**:
- No password field, no sign-up / sign-in distinction
- First visit vs return visit: same screen (new users register on OTP verify)

---

## S2 — Verify OTP Screen

**Primary action**: Enter 6-digit code → "Verify"

**Layout**:
```
[← Back]
"Enter the code sent to {phone}"

[6-digit OTP input — large, numeric, auto-focus]

[Verify button — full-width]

[Resend link — "Didn't get it? Resend" — tappable after 30s]
```

**States**:
- **Idle**: code empty, button disabled
- **Code entered**: button enabled
- **Loading**: spinner
- **Error**: inline error ("Invalid code", "Code expired")
- **New user**: if backend needs display_name, show name input inline before submit
  - "What's your name?" text field appears when code is valid (pre-submit)
  - Name is required only on first-time registration

**Notes**:
- On success → navigate to `(app)/` (replace history, no back)
- display_name input appears conditionally only for new users (server returns 400 if name missing → re-prompt inline)

---

## S3 — Clubs List Screen (Home)

**Primary action**: Tap a club → Club Detail

**Layout**:
```
[Header: "My Games"]

[List of clubs — each row:]
  [Club name]         [member count]
  [Last played or "No hands yet"]  →

[Empty state — if no clubs:]
  [Icon]
  "You're not in any clubs yet."
  "Ask a friend for their invite code to join a game."
  [— no action button —]
```

**States**:
- **Loading**: skeleton rows (3 shimmer placeholders)
- **Loaded — clubs present**: list rows
- **Loaded — empty**: empty state with guidance text
- **Error**: retry button + error message

**Notes**:
- No FAB for "Create Club" in MVP — deferred
- Pull-to-refresh supported
- Each row navigates to S4

---

## S4 — Club Detail Screen

**Primary action**: "Go to Table" button → Table Screen (S5)

**Layout**:
```
[← Back]
[Club name — large header]
[Member count: N members]
[Invite code: XXXXXXXX — visible only to owner/admin]

[──────── Table ────────]
[Blinds: {sb}/{bb}]
[Players: N / max_players seated]
[Status: Waiting for players / Hand in progress]

[Go to Table — full-width button]
```

**States**:
- **Loading table info**: spinner in table section
- **Loaded**: full layout above
- **Error loading table**: retry inline
- **Admin view**: shows invite code field with copy-to-clipboard button
- **Non-admin view**: invite code not shown

**Notes**:
- Table info comes from `GET /clubs/{clubId}/table`
- "Players: N/max" requires knowing active session player count — this comes from STATE_SNAPSHOT after connecting; before connecting, show "–/max" from table config only
- "Go to Table" navigates to S5 passing `tableId`

---

## S5 — Table Screen

**Primary action on entry**: Role choice modal → WebSocket connect

**Role choice modal (shown before WS connect)**:
```
[Modal / bottom sheet]
"Join this table as:"

[Join as Player] ← primary button, larger
[Watch as Spectator] ← secondary button

[Dismiss / Cancel]
```

Decision rules:
- If no seats available (≥ max_players seated), "Join as Player" is disabled with label "Table is full"
- Spectator always available

**Layout after joining**:
```
[← Leave Table]                    [Role badge: 🟢 Playing | 👁 Watching]

[Connection status — top banner, hidden when connected]

[─────── Table Area (placeholder) ─────────]
[                                           ]
[   "Table in progress — gameplay UI       ]
[    coming soon"                           ]
[                                           ]
[───────────────────────────────────────────]

[Players section:]
  [Player row: display_name | seat | stack | status]
  [Player row: ...]

[Phase: {WAITING_FOR_PLAYERS | PRE_FLOP | FLOP | ...}]
[Hand: #{hand_number}]
```

**Connection status banner**:
```
Connecting...          ← yellow, while WS is connecting
Reconnecting... (1/3)  ← yellow, auto-reconnect in progress
Connection lost.       ← red + "Tap to retry" link, after 3 failed attempts
✓ Connected            ← green flash, 2s then hides
```

**Role badge**:
- `🟢 Playing` — always visible in top right when role = player
- `👁 Watching` — always visible in top right when role = spectator
- After expiry reconnect (status = sit_out): `⏸ Sitting Out` badge

**SIT_OUT state** (player reconnected after expiry):
```
[Yellow inline banner:]
"You were away too long. You're sitting out."
[Tap to rejoin → sends SIT_IN]
```

**States**:
- **Pre-join**: role choice modal visible
- **Connecting**: modal gone, banner shows "Connecting..."
- **Connected — waiting**: banner gone, placeholder table area, player list from snapshot
- **Connected — hand in progress**: phase label shows phase, hand number shown
- **Disconnected**: banner shows reconnect state
- **Leave**: WS closes, navigate back

---

## Error States (Global)

| Error | Display |
|-------|---------|
| Network unreachable | Red banner: "No internet connection" |
| API error (4xx) | Inline under action button |
| API error (5xx) | Toast: "Something went wrong. Please try again." |
| WebSocket never connects | After 3 attempts: "Connection lost. Tap to retry." |
| 401 (token expired) | Clear token → navigate to login silently |

---

## Information Hierarchy

### Before joining a table (S4)
Must know: blinds, max players
Nice to know: current phase, recent hand count
Not needed: hole cards, pot, betting state

### After joining as player (S5)
Must know: own role, own status, other players (name + stack), current phase
Nice to know: hand number
Deferred: cards, pot, betting controls

### After joining as spectator (S5)
Must know: role badge ("Watching"), player list, current phase
Not needed: hole cards, betting controls

---

## Accessibility and Mobile Basics

- Minimum tap target: 44×44pt
- Text inputs: `keyboardType="phone-pad"` for phone, `keyboardType="number-pad"` for OTP
- OTP input: auto-advance on 6th digit
- Keyboard: dismiss on outside tap
- Safe area: all screens use `SafeAreaView`
- Dark mode: not required in MVP; system default
