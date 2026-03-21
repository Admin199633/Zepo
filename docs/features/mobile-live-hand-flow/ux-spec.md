# UX Spec: Mobile Live Hand Flow

**Feature:** mobile-live-hand-flow
**Date:** 2026-03-19
**Platform:** iOS + Android (portrait, React Native / Expo)

---

## 1. Screen Layout (Portrait, Single Column)

The table screen is a single scrollable column. From top to bottom:

```
┌──────────────────────────────────────┐
│  [ConnectionBanner — only if !connected] │  ← existing component
├──────────────────────────────────────┤
│  Table {tableId}          [RoleBadge] │  ← existing header
├──────────────────────────────────────┤
│  [SitOutBanner — only if sit_out]    │  ← existing banner
├──────────────────────────────────────┤
│                                      │
│   ┌──────────────────────────────┐   │
│   │  Hand #42  ·  Pre-Flop       │   │  ← HandInfoBar (new)
│   │  Pot: 300                    │   │
│   └──────────────────────────────┘   │
│                                      │
│   ┌──────────────────────────────┐   │
│   │  [Community Cards Zone]      │   │  ← CommunityCards (new)
│   │  [A♠][K♥][Q♦][ ][ ]         │   │
│   └──────────────────────────────┘   │
│                                      │
│   ┌──────────────────────────────┐   │
│   │  Your Cards                  │   │  ← MyHoleCards (new, only if playing)
│   │  [A♣][J♠]                   │   │
│   └──────────────────────────────┘   │
│                                      │
│   ── PLAYERS ──────────────────────  │
│   ┌──────────────────────────────┐   │
│   │ Alice [D]  1200 · Bet: 100   │ ← PlayerRow (extended)
│   │                   [Playing]  │
│   └──────────────────────────────┘   │
│   ┌──────────────────────────────┐   │  ← actor highlighted in yellow
│   │ Bob        900               │   │
│   │             [Playing]        │   │
│   └──────────────────────────────┘   │
│   ┌──────────────────────────────┐   │
│   │ You [D]   500 · Bet: 50      │   │  ← my row, blue border
│   │  [A♣][J♠]    [Playing]      │   │
│   └──────────────────────────────┘   │
│                                      │
└──────────────────────────────────────┘
│  [ActionBar — sticky bottom]         │  ← only when canAct=true
│  [Fold]  [Check/Call xxx]  [Raise]   │
│  ── Raise panel (expands upward) ─── │
│  Raise to: 150 ─────●───────────     │
│  [Cancel]        [Confirm Raise]     │
└──────────────────────────────────────┘
```

---

## 2. Component Tree

```
TableScreen (app/(app)/table/[tableId].tsx)
├── ConnectionBanner (existing)
├── TableHeader (inline in TableScreen)
│   ├── Text: "Table {tableId}"
│   └── RoleBadge (existing)
├── SitOutBanner (inline, existing logic)
├── ScrollView
│   ├── HandInfoBar (new: src/components/table/HandInfoBar.tsx)
│   ├── CommunityCards (new: src/components/table/CommunityCards.tsx)
│   ├── MyHoleCards (new: src/components/table/MyHoleCards.tsx)
│   └── PlayerList (extended: src/components/table/PlayerList.tsx)
│       └── PlayerRow (extended from existing inline logic)
│           ├── DealerBadge (inline)
│           ├── CardBackIndicator (inline, 2x for non-self players)
│           └── RoleBadge (existing)
├── ActionBar (new: src/components/table/ActionBar.tsx)
│   ├── Button "Fold" (existing Button component)
│   ├── Button "Check" or "Call {amount}" (existing Button)
│   ├── Button "Raise" (existing Button)
│   └── RaisePanel (new: src/components/table/RaisePanel.tsx) — conditionally rendered
│       ├── Slider
│       ├── Text "Raise to: {value}"
│       ├── Button "Cancel" (secondary)
│       └── Button "Confirm Raise" (primary)
├── HandResultOverlay (new: src/components/table/HandResultOverlay.tsx)
│   └── Modal (transparent, animationType="fade")
│       └── TouchableOpacity (dismiss on tap)
│           ├── Text: "Hand #{n} Complete"
│           ├── WinnerRow[] (winner name, amount, description)
│           ├── FinalBoard (CardChip[])
│           └── ShowdownHand[] (conditional)
└── ReconnectedBanner (new: local state in TableScreen, auto-hides after 2s)
```

---

## 3. HandInfoBar Component

**File:** `src/components/table/HandInfoBar.tsx`

**Props:**
```typescript
interface HandInfoBarProps {
  handNumber: number;
  phase: string;
  totalPot: number;
}
```

**Visual:**
- Dark card `#1E293B`, border-radius 10, padding 16, margin-bottom 12
- Top row: "Hand #{handNumber}" (left, bold, white) · phase label (right, colored per phase)
- Bottom row: "Pot: {totalPot}" (grey `#94A3B8`)

**Phase colors:**
| Phase | Color |
|-------|-------|
| preflop | `#94A3B8` (grey) |
| flop | `#60A5FA` (blue) |
| turn | `#34D399` (green) |
| river | `#F59E0B` (amber) |
| showdown | `#A78BFA` (purple) |

---

## 4. CommunityCards Component

**File:** `src/components/table/CommunityCards.tsx`

**Props:**
```typescript
interface CommunityCardsProps {
  cards: CardDTO[];
  phase: string;
}
```

**Visual:**
- Horizontal row, centered
- Each card chip: 44×60 dp, border-radius 6, background `#1E293B`, border `1px #334155`
- Card text: rank (bold, large) on top line, suit symbol below (red for hearts/diamonds, white for spades/clubs)
- No empty-slot placeholders in MVP (only render cards that exist)
- If `cards.length === 0`: show muted text "Waiting for flop…" centered

---

## 5. CardChip Component

**File:** `src/components/table/CardChip.tsx`

**Props:**
```typescript
interface CardChipProps {
  card: CardDTO;
  size?: 'sm' | 'md'; // 'sm' = 32×44, 'md' = 44×60 (default)
}
```

Suit symbol mapping:
```
s → ♠   color: #F8FAFC
h → ♥   color: #EF4444
d → ♦   color: #EF4444
c → ♣   color: #F8FAFC
```

---

## 6. MyHoleCards Component

**File:** `src/components/table/MyHoleCards.tsx`

**Props:**
```typescript
interface MyHoleCardsProps {
  cards: CardDTO[]; // always 2 in a live hand
}
```

**Visual:**
- Dark section card `#1E293B`, border-radius 10, padding 12, margin-bottom 12
- Label: "Your Cards" (grey `#94A3B8`, uppercase, letter-spacing 1)
- Two `CardChip` components side by side (size='md'), gap 8

**Render condition (in parent):** Only rendered when:
```tsx
const myPlayer = gameState.players.find(p => p.user_id === gameState.your_user_id);
const showMyCards = myPlayer?.hole_cards != null && myPlayer.hole_cards.length > 0;
```

---

## 7. ActionBar Component

**File:** `src/components/table/ActionBar.tsx`

**Props:**
```typescript
interface ActionBarProps {
  callAmount: number;
  minRaise: number;
  myStack: number;
  onFold: () => void;
  onCheck: () => void;
  onCall: () => void;
  onRaise: (amount: number) => void;
}
```

**Layout:**
- Sticky to bottom of screen (position absolute, bottom 0, left 0, right 0)
- Background `#0F172A` with top border `1px #1E293B`, padding 12 horizontal, 8 vertical
- Safe area bottom padding (use `useSafeAreaInsets().bottom`)
- Three buttons in a row: equal width using `flex: 1`, gap 8

**Button styles:**
- Fold: secondary (grey border)
- Check/Call: primary (blue)
- Raise: variant with `backgroundColor: '#7C3AED'` (purple), overrides primary

**RaisePanel expands upward** directly above the ActionBar button row. The panel uses `Animated.View` with a slide-up from 0 height to auto height (estimated 100 dp). When collapsed it is unmounted.

---

## 8. RaisePanel Component

**File:** `src/components/table/RaisePanel.tsx`

**Props:**
```typescript
interface RaisePanelProps {
  minRaise: number;
  maxRaise: number; // myPlayer.stack
  onConfirm: (amount: number) => void;
  onCancel: () => void;
}
```

**Visual:**
- Background `#1E293B`, padding 16, border-radius top-left/top-right 12, no bottom radius
- Label: `"Raise to: {value}"` — large, bold, centered, white
- If all-in (`minRaise >= maxRaise`): label changes to `"All-in: {value}"` and slider thumb is disabled visually (but value is still sent correctly)
- Slider: full width, thumb color `#7C3AED`, track color `#2563EB`
- Two buttons side by side: Cancel (flex 1, secondary) / Confirm Raise (flex 2, primary)

---

## 9. HandResultOverlay Component

**File:** `src/components/table/HandResultOverlay.tsx`

**Props:**
```typescript
interface HandResultOverlayProps {
  result: HandEndedPayload;
  players: PlayerViewDTO[]; // for display_name lookup
  onDismiss: () => void;
}
```

**Behavior:**
- Rendered as `<Modal visible={true} transparent animationType="fade">`
- `useEffect` with `setTimeout(onDismiss, 4000)` on mount; clears on unmount
- Outer `TouchableOpacity` wrapping everything to catch tap-to-dismiss
- Inner card: `#0F172A` background, border `1px #1E293B`, border-radius 16, padding 24, max-width 340, centered

**Content layout:**
```
Hand #{hand_number} Complete          (bold, white, centered, 18sp)

Alice wins 300 chips                  (white, 16sp)
Full House, Aces full of Kings        (#94A3B8, 13sp, italic)

Bob wins 150 chips                    (white, 16sp)
Two pair, Kings and Jacks             (#94A3B8, 13sp, italic)

── Final Board ──
[A♠] [A♥] [A♦] [K♠] [J♥]

── Showdown ──   (only if showdown_hands non-empty)
Alice: [A♠][A♦]  Full House, Aces full of Kings
Bob:   [K♠][K♥]  Two pair, Kings and Jacks

Tap to dismiss                        (#64748B, 12sp, centered)
```

---

## 10. Interaction Flow Diagram

```
User lands on table screen
        │
        ▼
WS connects → 'connecting'
        │
        ▼
WS opens → 'connected'
        │
        ▼
Role modal appears → user picks 'player' or 'watcher'
        │
        ├─ 'watcher' ──────────────────────────────────────────┐
        │                                                       │
        ▼                                                       ▼
JOIN sent (role: player)                              JOIN sent (role: watcher)
        │                                                       │
        ▼                                                       ▼
Server → STATE_SNAPSHOT                          Server → STATE_SNAPSHOT
        │                                                       │
        ▼                                                       ▼
gameState set in store                           gameState set in store
        │                                                       │
        ▼                                                       ▼
HandInfoBar + CommunityCards render             HandInfoBar + CommunityCards render
MyHoleCards render (if cards)                   No ActionBar ever
        │
        ▼
Is current_actor_id === my user_id?
AND myStatus === 'playing'?
        │
  yes ──┤
        ▼
ActionBar appears (slide up)
        │
        ├── Tap Fold → sendAction('FOLD') → ActionBar disappears
        ├── Tap Check → sendAction('CHECK') → ActionBar disappears
        ├── Tap Call → sendAction('CALL') → ActionBar disappears
        └── Tap Raise → RaisePanel slides up
                │
                ├── Adjust slider
                ├── Tap Cancel → RaisePanel slides down
                └── Tap Confirm → sendAction('RAISE', amount)
                                  → RaisePanel + ActionBar disappear

        [Server processes action → sends STATE_SNAPSHOT]
        [gameState updates → new current_actor_id → ActionBar logic re-evaluates]

        [Eventually HAND_ENDED arrives]
                │
                ▼
        HandResultOverlay appears
                │
                ├── Tap anywhere → onDismiss() → clearHandResult()
                └── After 4s → auto-dismiss → clearHandResult()
```

---

## 11. Scroll Behavior

- The ScrollView contains: HandInfoBar, CommunityCards, MyHoleCards, PlayerList
- The ActionBar is position-absolute at the bottom and does NOT scroll
- The ScrollView has `contentContainerStyle={{ paddingBottom: ACTION_BAR_HEIGHT + insets.bottom + 16 }}` to prevent content from being hidden behind the ActionBar when it is visible
- When `canAct` is false, `paddingBottom` returns to its default (16)

---

## 12. Z-Index Layers

| Layer | Z-index | Component |
|-------|---------|-----------|
| Base screen content | 0 | ScrollView, HandInfoBar, etc. |
| ActionBar | 10 | Position absolute bottom |
| RaisePanel | 11 | Attached above ActionBar |
| ReconnectedBanner | 20 | Position absolute top |
| HandResultOverlay | 100 | Modal (always on top) |

---

## 13. Colors Reference

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-dark` | `#0F172A` | Screen background |
| `bg-card` | `#1E293B` | Cards, panels |
| `border-subtle` | `#334155` | Subtle borders |
| `text-primary` | `#F8FAFC` | Main text |
| `text-muted` | `#94A3B8` | Secondary text |
| `text-dim` | `#64748B` | Tertiary / hints |
| `blue-action` | `#2563EB` | Primary action (Call) |
| `purple-raise` | `#7C3AED` | Raise button / slider |
| `yellow-actor` | `#EAB308` | Current actor border |
| `red-fold` | `#DC2626` | Fold button (secondary on dark bg) |
| `green-win` | `#86EFAC` | Win amount text |
| `red-card` | `#EF4444` | Hearts and diamonds suit color |

---

## 14. Accessibility

- All interactive elements have `accessibilityRole="button"` and `accessibilityLabel` props
- ActionBar buttons: `accessibilityLabel="Fold"`, `"Call 150"`, `"Raise"`, `"Confirm Raise 200"`, `"Cancel raise"`
- HandResultOverlay backdrop: `accessibilityLabel="Hand result, tap to dismiss"`
- Card chips: `accessibilityLabel="Ace of spades"` (generated from rank + suit name)
- Minimum touch target: 44×44 dp for all tappable elements (RN default)
