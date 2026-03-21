# Task Breakdown: Mobile Live Hand Flow

**Feature:** mobile-live-hand-flow
**Date:** 2026-03-19
**Estimated total:** ~3 days engineering

Tasks are ordered by dependency. T-01 must be done first. T-02 through T-04 can be done in parallel after T-01. T-05 through T-08 depend on T-02/T-03. T-09 depends on T-05 through T-08. T-10 is independent. T-11 closes out the feature.

---

## T-01: Install @react-native-community/slider

**Size:** XS (15 min)
**Depends on:** nothing
**Blocks:** T-07 (RaisePanel)

Run:
```bash
npm install @react-native-community/slider
```

Add the mock to `jest.setup.js`:

```javascript
// jest.setup.js
jest.mock('@react-native-community/slider', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    __esModule: true,
    default: ({ accessibilityLabel, minimumValue, maximumValue, value, onValueChange, disabled }) =>
      React.createElement(View, {
        testID: 'slider',
        accessibilityLabel,
        // Expose props for test assertions via accessible attributes
      }),
  };
});
```

Verify: `npx expo doctor` passes; no native module errors on simulator build.

---

## T-02: Extend src/ws/types.ts — Add HandEndedPayload types

**Size:** XS (10 min)
**Depends on:** nothing
**Blocks:** T-03, T-05, T-08

Append to `/c/Users/LiorSw/Desktop/Zepo/mobile/src/ws/types.ts` (after line 95, after the existing `ClientEnvelope` interface):

```typescript
// ---------------------------------------------------------------------------
// HAND_ENDED payload (server → client)
// ---------------------------------------------------------------------------

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
  showdown_hands: HandEndedShowdownEntry[];
}
```

No existing types are modified.

---

## T-03: Extend tableStore — handResult state + event handlers

**Size:** S (30 min)
**Depends on:** T-02
**Blocks:** T-09

Modify `src/store/tableStore.ts`.

**Step 1:** Add import for `HandEndedPayload`:

```typescript
import type { ConnectionStatus, HandEndedPayload, StateSnapshotDTO } from '../ws/types';
```

**Step 2:** Extend the `TableState` interface:

```typescript
interface TableState {
  connectionStatus: ConnectionStatus;
  reconnectAttempt: number;
  gameState: StateSnapshotDTO | null;
  handResult: HandEndedPayload | null;      // NEW
  error: string | null;

  connect: (tableId: string, token: string) => void;
  disconnect: () => void;
  sendJoin: (role: 'player' | 'watcher') => void;
  sendSitIn: () => void;
  sendSitOut: () => void;
  sendAction: (type: 'FOLD' | 'CHECK' | 'CALL' | 'RAISE', amount?: number) => void;
  clearHandResult: () => void;              // NEW
  reset: () => void;
}
```

**Step 3:** Extend `onMessage` callback (replace the existing callback registration):

```typescript
socketClient.onMessage((envelope) => {
  if (envelope.type === 'STATE_SNAPSHOT') {
    set({ gameState: envelope.payload as unknown as StateSnapshotDTO, error: null });
  } else if (envelope.type === 'HAND_ENDED') {
    set({ handResult: envelope.payload as unknown as HandEndedPayload });
  } else if (envelope.type === 'HAND_STARTED') {
    set({ handResult: null });
  } else if (envelope.type === 'ERROR') {
    const msg =
      (envelope.payload['message'] as string | undefined) ?? 'An error occurred.';
    set({ error: msg });
  }
});
```

**Step 4:** Update initial state and add `clearHandResult` and update `reset`:

```typescript
return {
  connectionStatus: 'disconnected',
  reconnectAttempt: 0,
  gameState: null,
  handResult: null,                        // NEW
  error: null,

  // ... existing connect, disconnect, sendJoin, sendSitIn, sendSitOut, sendAction ...

  clearHandResult: () => set({ handResult: null }),    // NEW

  reset: () => {
    socketClient.disconnect();
    savedTableId = null;
    savedToken = null;
    set({
      connectionStatus: 'disconnected',
      reconnectAttempt: 0,
      gameState: null,
      handResult: null,                    // NEW — included in reset
      error: null,
    });
  },
};
```

---

## T-04: Create src/components/table/CardChip.tsx

**Size:** S (20 min)
**Depends on:** nothing (uses only `CardDTO` from existing types.ts)
**Blocks:** T-05, T-06, T-08

Create the file at `src/components/table/CardChip.tsx`:

```typescript
import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';

const SUIT_SYMBOLS: Record<string, string> = {
  s: '♠',
  h: '♥',
  d: '♦',
  c: '♣',
};

const SUIT_COLORS: Record<string, string> = {
  s: '#F8FAFC',
  h: '#EF4444',
  d: '#EF4444',
  c: '#F8FAFC',
};

const SUIT_NAMES: Record<string, string> = {
  s: 'spades',
  h: 'hearts',
  d: 'diamonds',
  c: 'clubs',
};

interface CardChipProps {
  card: CardDTO;
  size?: 'sm' | 'md';
}

export default function CardChip({ card, size = 'md' }: CardChipProps) {
  const width = size === 'sm' ? 32 : 44;
  const height = size === 'sm' ? 44 : 60;
  const suitSymbol = SUIT_SYMBOLS[card.suit] ?? card.suit;
  const suitColor = SUIT_COLORS[card.suit] ?? '#F8FAFC';
  const suitName = SUIT_NAMES[card.suit] ?? card.suit;

  return (
    <View
      style={[styles.card, { width, height }]}
      accessibilityLabel={`${card.rank} of ${suitName}`}
      accessibilityRole="text"
    >
      <Text style={styles.rank}>{card.rank}</Text>
      <Text style={[styles.suit, { color: suitColor }]}>{suitSymbol}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
    justifyContent: 'center',
  },
  rank: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 14,
  },
  suit: {
    fontSize: 12,
  },
});
```

---

## T-05: Create src/components/table/HandInfoBar.tsx

**Size:** S (20 min)
**Depends on:** nothing (no sub-components needed)

```typescript
import { StyleSheet, Text, View } from 'react-native';

const PHASE_LABELS: Record<string, string> = {
  preflop: 'Pre-Flop',
  flop: 'Flop',
  turn: 'Turn',
  river: 'River',
  showdown: 'Showdown',
};

const PHASE_COLORS: Record<string, string> = {
  preflop: '#94A3B8',
  flop: '#60A5FA',
  turn: '#34D399',
  river: '#F59E0B',
  showdown: '#A78BFA',
};

interface HandInfoBarProps {
  handNumber: number;
  phase: string;
  totalPot: number;
}

export default function HandInfoBar({ handNumber, phase, totalPot }: HandInfoBarProps) {
  const label = PHASE_LABELS[phase] ?? phase;
  const color = PHASE_COLORS[phase] ?? '#94A3B8';

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        <Text style={styles.handNumber}>Hand #{handNumber}</Text>
        <Text style={[styles.phase, { color }]}>{label}</Text>
      </View>
      <Text style={styles.pot}>Pot: {totalPot}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  handNumber: { color: '#F8FAFC', fontWeight: '700', fontSize: 16 },
  phase: { fontWeight: '600', fontSize: 15 },
  pot: { color: '#94A3B8', fontSize: 13 },
});
```

---

## T-06: Create src/components/table/CommunityCards.tsx and MyHoleCards.tsx

**Size:** S (25 min)
**Depends on:** T-04 (CardChip)

**CommunityCards.tsx:**

```typescript
import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';
import CardChip from './CardChip';

interface CommunityCardsProps {
  cards: CardDTO[];
  phase: string;
}

export default function CommunityCards({ cards }: CommunityCardsProps) {
  return (
    <View style={styles.container}>
      {cards.length === 0 ? (
        <Text style={styles.waiting}>Waiting for flop…</Text>
      ) : (
        <View style={styles.row}>
          {cards.map((card, i) => (
            <CardChip key={i} card={card} size="md" />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
    alignItems: 'center',
  },
  row: { flexDirection: 'row', gap: 8 },
  waiting: { color: '#64748B', fontSize: 14 },
});
```

**MyHoleCards.tsx:**

```typescript
import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';
import CardChip from './CardChip';

interface MyHoleCardsProps {
  cards: CardDTO[];
}

export default function MyHoleCards({ cards }: MyHoleCardsProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>YOUR CARDS</Text>
      <View style={styles.row}>
        {cards.map((card, i) => (
          <CardChip key={i} card={card} size="md" />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  label: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    marginBottom: 8,
  },
  row: { flexDirection: 'row', gap: 8 },
});
```

---

## T-07: Create ActionBar.tsx and RaisePanel.tsx

**Size:** M (45 min)
**Depends on:** T-01 (slider dep), T-04 (CardChip not needed but Button is reused)

**RaisePanel.tsx:**

```typescript
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Slider from '@react-native-community/slider';
import Button from '../common/Button';

interface RaisePanelProps {
  minRaise: number;
  maxRaise: number;
  onConfirm: (amount: number) => void;
  onCancel: () => void;
}

export default function RaisePanel({ minRaise, maxRaise, onConfirm, onCancel }: RaisePanelProps) {
  const effectiveMin = Math.min(minRaise, maxRaise);
  const effectiveMax = maxRaise;
  const isAllIn = effectiveMin >= effectiveMax;
  const [value, setValue] = useState(effectiveMin);

  return (
    <View style={styles.container}>
      <Text style={styles.label}>
        {isAllIn ? `All-in: ${value}` : `Raise to: ${value}`}
      </Text>
      <Slider
        style={styles.slider}
        minimumValue={effectiveMin}
        maximumValue={isAllIn ? effectiveMax + 0.001 : effectiveMax}
        step={1}
        value={value}
        onValueChange={(v: number) => setValue(Math.round(v))}
        minimumTrackTintColor="#2563EB"
        maximumTrackTintColor="#334155"
        thumbTintColor="#7C3AED"
        disabled={isAllIn}
        accessibilityLabel={`Raise amount slider, current value ${value}`}
      />
      <View style={styles.buttons}>
        <Button
          label="Cancel"
          variant="secondary"
          style={styles.cancelBtn}
          onPress={onCancel}
          accessibilityLabel="Cancel raise"
        />
        <Button
          label="Confirm Raise"
          style={styles.confirmBtn}
          onPress={() => onConfirm(value)}
          accessibilityLabel={`Confirm raise ${value}`}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  label: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 8,
  },
  slider: { width: '100%', height: 40 },
  buttons: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cancelBtn: { flex: 1 },
  confirmBtn: { flex: 2 },
});
```

**ActionBar.tsx:**

```typescript
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Button from '../common/Button';
import RaisePanel from './RaisePanel';

interface ActionBarProps {
  callAmount: number;
  minRaise: number;
  myStack: number;
  onFold: () => void;
  onCheck: () => void;
  onCall: () => void;
  onRaise: (amount: number) => void;
}

export default function ActionBar({
  callAmount,
  minRaise,
  myStack,
  onFold,
  onCheck,
  onCall,
  onRaise,
}: ActionBarProps) {
  const insets = useSafeAreaInsets();
  const [raiseOpen, setRaiseOpen] = useState(false);

  const handleAction = (fn: () => void) => {
    setRaiseOpen(false);
    fn();
  };

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8 }]}>
      {raiseOpen && (
        <RaisePanel
          minRaise={minRaise}
          maxRaise={myStack}
          onConfirm={(amount) => {
            setRaiseOpen(false);
            onRaise(amount);
          }}
          onCancel={() => setRaiseOpen(false)}
        />
      )}
      <View style={styles.buttons}>
        <Button
          label="Fold"
          variant="secondary"
          style={styles.btn}
          onPress={() => handleAction(onFold)}
          accessibilityLabel="Fold"
          accessibilityRole="button"
        />
        <Button
          label={callAmount > 0 ? `Call ${callAmount}` : 'Check'}
          style={styles.btn}
          onPress={() => handleAction(callAmount > 0 ? onCall : onCheck)}
          accessibilityLabel={callAmount > 0 ? `Call ${callAmount}` : 'Check'}
          accessibilityRole="button"
        />
        <Button
          label="Raise"
          style={[styles.btn, styles.raiseBtn]}
          onPress={() => setRaiseOpen((v) => !v)}
          accessibilityLabel="Raise"
          accessibilityRole="button"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#0F172A',
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  buttons: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1 },
  raiseBtn: { backgroundColor: '#7C3AED' },
});
```

---

## T-08: Create HandResultOverlay.tsx

**Size:** M (40 min)
**Depends on:** T-02 (types), T-04 (CardChip)

```typescript
import { useEffect } from 'react';
import { Modal, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { HandEndedPayload, PlayerViewDTO } from '../../ws/types';
import CardChip from './CardChip';

interface HandResultOverlayProps {
  result: HandEndedPayload;
  players: PlayerViewDTO[];
  onDismiss: () => void;
}

export default function HandResultOverlay({ result, players, onDismiss }: HandResultOverlayProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const getName = (userId: string): string =>
    players.find((p) => p.user_id === userId)?.display_name ?? userId;

  return (
    <Modal visible transparent animationType="fade">
      <TouchableOpacity
        style={styles.backdrop}
        activeOpacity={1}
        onPress={onDismiss}
        accessibilityLabel="Hand result, tap to dismiss"
        accessibilityRole="button"
      >
        <View style={styles.card}>
          <Text style={styles.title}>Hand #{result.hand_number} Complete</Text>

          {result.winners.map((w, i) => (
            <View key={i} style={styles.winnerBlock}>
              <Text style={styles.winnerLine}>
                {getName(w.user_id)}{' '}
                <Text style={styles.wins}>wins </Text>
                <Text style={styles.amount}>{w.amount} chips</Text>
              </Text>
              {Boolean(w.hand_description) && (
                <Text style={styles.desc}>{w.hand_description}</Text>
              )}
            </View>
          ))}

          {result.final_board.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>Final Board</Text>
              <View style={styles.cardRow}>
                {result.final_board.map((card, i) => (
                  <CardChip key={i} card={card} size="sm" />
                ))}
              </View>
            </View>
          )}

          {result.showdown_hands.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>Showdown</Text>
              {result.showdown_hands.map((entry, i) => (
                <View key={i} style={styles.showdownEntry}>
                  <Text style={styles.showdownName}>{getName(entry.user_id)}</Text>
                  <View style={styles.cardRow}>
                    {entry.hole_cards.map((card, j) => (
                      <CardChip key={j} card={card} size="sm" />
                    ))}
                  </View>
                  {Boolean(entry.hand_description) && (
                    <Text style={styles.desc}>{entry.hand_description}</Text>
                  )}
                </View>
              ))}
            </View>
          )}

          <Text style={styles.hint}>Tap to dismiss</Text>
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 16,
    padding: 24,
    width: '85%',
    maxWidth: 340,
  },
  title: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 18,
    textAlign: 'center',
    marginBottom: 16,
  },
  winnerBlock: { marginBottom: 10 },
  winnerLine: { color: '#F8FAFC', fontSize: 15 },
  wins: { color: '#F8FAFC' },
  amount: { color: '#86EFAC', fontWeight: '700' },
  desc: { color: '#94A3B8', fontSize: 13, fontStyle: 'italic', marginTop: 2 },
  section: { marginTop: 14 },
  sectionLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  cardRow: { flexDirection: 'row', gap: 6 },
  showdownEntry: { marginBottom: 10 },
  showdownName: { color: '#F8FAFC', fontSize: 13, marginBottom: 4 },
  hint: { color: '#64748B', fontSize: 12, textAlign: 'center', marginTop: 16 },
});
```

---

## T-09: Update [tableId].tsx — Wire all new components

**Size:** L (90 min)
**Depends on:** T-03 (store), T-05 (HandInfoBar), T-06 (CommunityCards, MyHoleCards), T-07 (ActionBar), T-08 (HandResultOverlay)

Key changes to `app/(app)/table/[tableId].tsx`:

**1. New imports:**
```typescript
import HandInfoBar from '../../../src/components/table/HandInfoBar';
import CommunityCards from '../../../src/components/table/CommunityCards';
import MyHoleCards from '../../../src/components/table/MyHoleCards';
import ActionBar from '../../../src/components/table/ActionBar';
import HandResultOverlay from '../../../src/components/table/HandResultOverlay';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRef } from 'react';
import type { ConnectionStatus } from '../../../src/ws/types';
```

**2. New store fields destructured:**
```typescript
const {
  connectionStatus, reconnectAttempt, gameState, handResult,
  sendJoin, sendAction, connect, disconnect, clearHandResult,
} = useTableStore();
```

**3. New state and refs:**
```typescript
const [joinedRole, setJoinedRole] = useState<'player' | 'watcher' | null>(null);
const [showReconnectedBanner, setShowReconnectedBanner] = useState(false);
const prevStatusRef = useRef<ConnectionStatus>('disconnected');
const insets = useSafeAreaInsets();
```

**4. Reconnect effect (add AFTER existing effects):**
```typescript
useEffect(() => {
  const prev = prevStatusRef.current;
  prevStatusRef.current = connectionStatus;

  if (
    connectionStatus === 'connected' &&
    (prev === 'reconnecting' || prev === 'connecting') &&
    joinedRole !== null
  ) {
    sendJoin(joinedRole);
    setShowReconnectedBanner(true);
    const bannerTimer = setTimeout(() => setShowReconnectedBanner(false), 2000);
    return () => clearTimeout(bannerTimer);
  }
}, [connectionStatus]);
```

**5. handleRoleSelect update:**
```typescript
const handleRoleSelect = (role: 'player' | 'watcher') => {
  setRoleModalVisible(false);
  setJoined(true);
  setJoinedRole(role);
  sendJoin(role);
};
```

**6. Derived state:**
```typescript
const myPlayer = gameState?.players.find((p) => p.user_id === gameState.your_user_id) ?? null;
const myStatus = myPlayer?.status ?? null;
const isMyTurn = gameState?.current_hand?.current_actor_id === gameState?.your_user_id;
const isPlaying = myStatus === 'playing';
const handInProgress = gameState?.current_hand != null;
const canAct = isMyTurn && isPlaying && handInProgress && connectionStatus === 'connected';
const totalPot = gameState?.current_hand?.pots.reduce((s, p) => s + p.amount, 0) ?? 0;
const showMyCards = (myPlayer?.hole_cards?.length ?? 0) > 0;

const ACTION_BAR_HEIGHT = 80;
const scrollPaddingBottom = canAct ? ACTION_BAR_HEIGHT + insets.bottom + 16 : 16;
```

**7. Return JSX — replace existing ScrollView content:**
```tsx
{gameState ? (
  <>
    {gameState.current_hand ? (
      <>
        <HandInfoBar
          handNumber={gameState.current_hand.hand_number}
          phase={gameState.current_hand.phase}
          totalPot={totalPot}
        />
        <CommunityCards
          cards={gameState.current_hand.community_cards}
          phase={gameState.current_hand.phase}
        />
      </>
    ) : (
      <View style={styles.center}>
        <Text style={styles.muted}>Waiting for next hand…</Text>
      </View>
    )}
    {showMyCards && myPlayer?.hole_cards && (
      <MyHoleCards cards={myPlayer.hole_cards} />
    )}
    <PlayerList
      players={gameState.players}
      myUserId={gameState.your_user_id}
      currentActorId={gameState.current_hand?.current_actor_id ?? null}
    />
  </>
) : (
  <View style={styles.center}>
    <Text style={styles.muted}>
      {connectionStatus === 'connected' ? 'Waiting for game state…' : 'Connecting…'}
    </Text>
  </View>
)}
```

**8. After ScrollView, before Modal:**
```tsx
{canAct && gameState?.current_hand && (
  <ActionBar
    callAmount={gameState.current_hand.call_amount}
    minRaise={gameState.current_hand.min_raise}
    myStack={myPlayer?.stack ?? 0}
    onFold={() => sendAction('FOLD')}
    onCheck={() => sendAction('CHECK')}
    onCall={() => sendAction('CALL')}
    onRaise={(amount) => sendAction('RAISE', amount)}
  />
)}

{handResult && gameState && (
  <HandResultOverlay
    result={handResult}
    players={gameState.players}
    onDismiss={clearHandResult}
  />
)}
```

**9. Reconnected banner (above ConnectionBanner):**
```tsx
{showReconnectedBanner && (
  <View style={styles.reconnectedBanner}>
    <Text style={styles.reconnectedText}>Reconnected</Text>
  </View>
)}
```

Add style:
```typescript
reconnectedBanner: { backgroundColor: '#166534', paddingVertical: 6, paddingHorizontal: 16 },
reconnectedText: { color: '#86EFAC', fontWeight: '600', textAlign: 'center', fontSize: 13 },
```

---

## T-10: Update PlayerList.tsx — actor highlight + hand metadata

**Size:** M (40 min)
**Depends on:** nothing (standalone component change)

**New props:**
```typescript
interface PlayerListProps {
  players: PlayerViewDTO[];
  myUserId: string;
  currentActorId: string | null;   // NEW
}
```

**Per-row logic additions:**
```typescript
const isActor = p.user_id === currentActorId;
const isMe = p.user_id === myUserId;
// Actor highlight takes priority over my-row highlight
const borderColor = isActor ? '#EAB308' : isMe ? '#2563EB' : 'transparent';
const hasBorder = isActor || isMe;
const opacity = p.status === 'sit_out' || p.status === 'disconnected' ? 0.5 : 1.0;

// Show face-down card indicators for other playing players
const showCardBacks =
  p.status === 'playing' && p.user_id !== myUserId;
```

**Row render:**
```tsx
<View
  key={p.user_id}
  style={[
    styles.row,
    hasBorder && { borderWidth: 2, borderColor },
    { opacity },
  ]}
>
  <View style={styles.left}>
    <View style={styles.nameRow}>
      <Text style={[styles.name, p.status === 'disconnected' && styles.italic]}>
        {p.display_name}
      </Text>
      {p.is_dealer && (
        <View style={styles.dealerBadge}>
          <Text style={styles.dealerText}>D</Text>
        </View>
      )}
    </View>
    <Text style={styles.stack}>{p.stack} chips</Text>
    {p.current_bet > 0 && (
      <Text style={styles.bet}>Bet: {p.current_bet}</Text>
    )}
  </View>
  <View style={styles.right}>
    {showCardBacks && (
      <View style={styles.cardBacks}>
        <View style={styles.cardBack} />
        <View style={styles.cardBack} />
      </View>
    )}
    <RoleBadge status={p.status} />
  </View>
</View>
```

Add styles:
```typescript
nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
italic: { fontStyle: 'italic' },
dealerBadge: {
  backgroundColor: '#B45309',
  borderRadius: 10,
  paddingHorizontal: 6,
  paddingVertical: 2,
},
dealerText: { color: '#FDE68A', fontSize: 11, fontWeight: '700' },
bet: { color: '#64748B', fontSize: 12, marginTop: 1 },
right: { alignItems: 'flex-end', gap: 4 },
cardBacks: { flexDirection: 'row', gap: 2 },
cardBack: {
  width: 14,
  height: 18,
  backgroundColor: '#334155',
  borderRadius: 2,
  borderWidth: 1,
  borderColor: '#475569',
},
```

---

## T-11: Write unit tests

**Size:** L (90 min)
**Depends on:** T-02 through T-10

Create or extend the following test files. All test cases are fully specified in `qa-test-plan.md`. Tests TC-01 through TC-36 must all pass before the feature is merged.

Files to create:
- `__tests__/tableStoreHandResult.test.ts` — TC-01 through TC-05
- `__tests__/canActDerivation.test.ts` — TC-06 through TC-13
- `__tests__/ActionBar.test.tsx` — TC-14 through TC-18
- `__tests__/RaisePanel.test.tsx` — TC-19 through TC-21
- `__tests__/holeCardGuard.test.tsx` — TC-22 through TC-24
- `__tests__/HandResultOverlay.test.tsx` — TC-25 through TC-29
- `__tests__/CardChip.test.tsx` — TC-30 through TC-32
- `__tests__/HandInfoBar.test.tsx` — TC-33 through TC-35
- `__tests__/CommunityCards.test.tsx` — TC-36

Run all with:
```bash
cd "C:/Users/LiorSw/Desktop/Zepo/mobile"
npm test
```

Expected: 36 new tests passing, all 24 existing tests (TC-14 through TC-34 in existing files) still passing.

---

## Task Summary

| Task | Description | Size | Dependencies |
|------|-------------|------|-------------|
| T-01 | Install @react-native-community/slider | XS | — |
| T-02 | Add HandEndedPayload types to types.ts | XS | — |
| T-03 | Extend tableStore (handResult, handlers) | S | T-02 |
| T-04 | Create CardChip component | S | — |
| T-05 | Create HandInfoBar component | S | — |
| T-06 | Create CommunityCards + MyHoleCards | S | T-04 |
| T-07 | Create ActionBar + RaisePanel | M | T-01 |
| T-08 | Create HandResultOverlay | M | T-02, T-04 |
| T-09 | Update [tableId].tsx (wire all) | L | T-03, T-05, T-06, T-07, T-08 |
| T-10 | Update PlayerList.tsx (actor highlight etc) | M | — |
| T-11 | Write unit tests (TC-01 – TC-36) | L | T-02 – T-10 |
