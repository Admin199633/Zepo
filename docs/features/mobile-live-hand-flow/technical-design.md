# Technical Design: Mobile Live Hand Flow

**Feature:** mobile-live-hand-flow
**Date:** 2026-03-19
**Stack:** Expo SDK 52, React Native 0.76, Expo Router v4, TypeScript, Zustand 5, native WebSocket

---

## 1. Architecture Overview

This feature extends the existing data-flow pipeline without changing SocketClient or the WS protocol:

```
SocketClient (native WS)
    │ onMessage
    ▼
tableStore (Zustand)
  ├── gameState: StateSnapshotDTO | null        ← existing
  ├── handResult: HandEndedPayload | null        ← NEW
  ├── connectionStatus: ConnectionStatus         ← existing
  └── clearHandResult: () => void                ← NEW

    │ useTableStore()
    ▼
TableScreen ([tableId].tsx)
  ├── derives: canAct, myPlayer, totalPot
  ├── renders: HandInfoBar, CommunityCards, MyHoleCards, PlayerList
  ├── renders: ActionBar (conditional)
  └── renders: HandResultOverlay (conditional)
```

No new network calls. No new backend endpoints. All live-hand data arrives through the existing WS connection.

---

## 2. tableStore Changes

### 2.1 New State Fields

```typescript
// src/store/tableStore.ts — additions to TableState interface

interface TableState {
  // ... existing fields ...
  handResult: HandEndedPayload | null;           // NEW
  clearHandResult: () => void;                   // NEW
}
```

### 2.2 New onMessage Handlers

Inside the existing `socketClient.onMessage` callback, add two new branches:

```typescript
socketClient.onMessage((envelope) => {
  if (envelope.type === 'STATE_SNAPSHOT') {
    set({ gameState: envelope.payload as unknown as StateSnapshotDTO, error: null });

  } else if (envelope.type === 'HAND_ENDED') {
    set({ handResult: envelope.payload as unknown as HandEndedPayload });

  } else if (envelope.type === 'HAND_STARTED') {
    // Clear any stale hand result when a new hand begins
    set({ handResult: null });

  } else if (envelope.type === 'ERROR') {
    const msg =
      (envelope.payload['message'] as string | undefined) ?? 'An error occurred.';
    set({ error: msg });
  }
});
```

### 2.3 clearHandResult and reset

```typescript
clearHandResult: () => set({ handResult: null }),

reset: () => {
  socketClient.disconnect();
  savedTableId = null;
  savedToken = null;
  set({
    connectionStatus: 'disconnected',
    reconnectAttempt: 0,
    gameState: null,
    handResult: null,          // NEW — clear on reset
    error: null,
  });
},
```

### 2.4 Initial State

```typescript
return {
  connectionStatus: 'disconnected',
  reconnectAttempt: 0,
  gameState: null,
  handResult: null,            // NEW
  error: null,
  // ... existing actions ...
  clearHandResult: () => set({ handResult: null }),
};
```

---

## 3. New Types (src/ws/types.ts)

Append after existing types — do not modify existing interfaces:

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

---

## 4. TableScreen Changes (app/(app)/table/[tableId].tsx)

### 4.1 Derived State (pure computation, no side effects)

```typescript
// Derived values computed at render time
const myPlayer = gameState?.players.find((p) => p.user_id === gameState.your_user_id) ?? null;
const myStatus = myPlayer?.status ?? null;

const isMyTurn =
  gameState?.current_hand?.current_actor_id === gameState?.your_user_id;
const isPlaying = myStatus === 'playing';
const handInProgress = gameState?.current_hand != null;
const canAct = isMyTurn && isPlaying && handInProgress && connectionStatus === 'connected';

const totalPot =
  gameState?.current_hand?.pots.reduce((s, p) => s + p.amount, 0) ?? 0;

const showMyCards =
  myPlayer?.hole_cards != null && myPlayer.hole_cards.length > 0;
```

### 4.2 Reconnect: re-send JOIN after reconnect

Add `joinedRole` local state and re-send on reconnect:

```typescript
const [joinedRole, setJoinedRole] = useState<'player' | 'watcher' | null>(null);

// On reconnect, re-send JOIN with preserved role
const prevStatusRef = useRef<ConnectionStatus>('disconnected');
useEffect(() => {
  const prev = prevStatusRef.current;
  prevStatusRef.current = connectionStatus;

  if (
    connectionStatus === 'connected' &&
    (prev === 'reconnecting' || prev === 'connecting') &&
    joinedRole !== null
  ) {
    sendJoin(joinedRole);
  }
}, [connectionStatus]);
```

Note: the first JOIN (role selection modal) already calls `sendJoin` and sets `joinedRole`. The above effect only fires on subsequent reconnects.

### 4.3 handleRoleSelect update

```typescript
const handleRoleSelect = (role: 'player' | 'watcher') => {
  setRoleModalVisible(false);
  setJoined(true);
  setJoinedRole(role);   // NEW — preserve for reconnect
  sendJoin(role);
};
```

### 4.4 Reconnected Banner (local state)

```typescript
const [showReconnectedBanner, setShowReconnectedBanner] = useState(false);

useEffect(() => {
  if (connectionStatus === 'connected' && prevStatusRef.current === 'reconnecting') {
    setShowReconnectedBanner(true);
    const timer = setTimeout(() => setShowReconnectedBanner(false), 2000);
    return () => clearTimeout(timer);
  }
}, [connectionStatus]);
```

Rendered as a green banner above the connection banner zone:

```tsx
{showReconnectedBanner && (
  <View style={styles.reconnectedBanner}>
    <Text style={styles.reconnectedText}>Reconnected</Text>
  </View>
)}
```

Style: `backgroundColor: '#166534'`, text: `#86EFAC`.

### 4.5 ScrollView paddingBottom

```typescript
const ACTION_BAR_HEIGHT = 80; // dp
const insets = useSafeAreaInsets();
const scrollPaddingBottom = canAct
  ? ACTION_BAR_HEIGHT + insets.bottom + 16
  : 16;
```

### 4.6 Full render structure

```tsx
return (
  <View style={styles.container}>
    {showReconnectedBanner && <ReconnectedBanner />}
    <ConnectionBanner status={connectionStatus} attempt={reconnectAttempt} maxAttempts={3} />
    {/* Header */}
    <View style={styles.header}>
      <Text style={styles.tableId} numberOfLines={1}>Table {tableId}</Text>
      {myStatus && <RoleBadge status={myStatus} />}
    </View>
    {/* Sit-out banner */}
    {myStatus === 'sit_out' && (
      <TouchableOpacity style={styles.sitInBanner}
        onPress={() => useTableStore.getState().sendSitIn()}>
        <Text style={styles.sitInText}>You are sitting out — Tap to rejoin</Text>
      </TouchableOpacity>
    )}
    {/* Main content */}
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={[styles.scrollContent, { paddingBottom: scrollPaddingBottom }]}
    >
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
    </ScrollView>
    {/* Sticky action bar */}
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
    {/* Role selection modal (existing) */}
    <Modal visible={roleModalVisible} transparent animationType="fade">
      {/* ... existing modal content ... */}
    </Modal>
    {/* Hand result overlay */}
    {handResult && gameState && (
      <HandResultOverlay
        result={handResult}
        players={gameState.players}
        onDismiss={() => clearHandResult()}
      />
    )}
  </View>
);
```

---

## 5. New Components

### 5.1 src/components/table/HandInfoBar.tsx

```typescript
import { StyleSheet, Text, View } from 'react-native';

interface HandInfoBarProps {
  handNumber: number;
  phase: string;
  totalPot: number;
}

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

export default function HandInfoBar({ handNumber, phase, totalPot }: HandInfoBarProps) {
  const label = PHASE_LABELS[phase] ?? phase;
  const color = PHASE_COLORS[phase] ?? '#94A3B8';
  return (
    <View style={styles.container}>
      <View style={styles.row}>
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
  row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  handNumber: { color: '#F8FAFC', fontWeight: '700', fontSize: 16 },
  phase: { fontWeight: '600', fontSize: 15 },
  pot: { color: '#94A3B8', fontSize: 13 },
});
```

### 5.2 src/components/table/CardChip.tsx

```typescript
import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';

const SUIT_SYMBOLS: Record<string, string> = {
  s: '♠', h: '♥', d: '♦', c: '♣',
};
const SUIT_COLORS: Record<string, string> = {
  s: '#F8FAFC', h: '#EF4444', d: '#EF4444', c: '#F8FAFC',
};

interface CardChipProps {
  card: CardDTO;
  size?: 'sm' | 'md';
}

export default function CardChip({ card, size = 'md' }: CardChipProps) {
  const w = size === 'sm' ? 32 : 44;
  const h = size === 'sm' ? 44 : 60;
  const suitSymbol = SUIT_SYMBOLS[card.suit] ?? card.suit;
  const suitColor = SUIT_COLORS[card.suit] ?? '#F8FAFC';
  const suitName = { s: 'spades', h: 'hearts', d: 'diamonds', c: 'clubs' }[card.suit] ?? card.suit;
  return (
    <View
      style={[styles.card, { width: w, height: h }]}
      accessibilityLabel={`${card.rank} of ${suitName}`}
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
  rank: { color: '#F8FAFC', fontWeight: '700', fontSize: 14 },
  suit: { fontSize: 12 },
});
```

### 5.3 src/components/table/CommunityCards.tsx

```typescript
import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';
import CardChip from './CardChip';

interface CommunityCardsProps {
  cards: CardDTO[];
  phase: string;
}

export default function CommunityCards({ cards, phase }: CommunityCardsProps) {
  return (
    <View style={styles.container}>
      {cards.length === 0 ? (
        <Text style={styles.waiting}>Waiting for flop…</Text>
      ) : (
        <View style={styles.row}>
          {cards.map((card, i) => (
            <View key={i} style={styles.cardWrapper}>
              <CardChip card={card} size="md" />
            </View>
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
  cardWrapper: {},
  waiting: { color: '#64748B', fontSize: 14 },
});
```

### 5.4 src/components/table/MyHoleCards.tsx

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
          <View key={i} style={styles.cardWrapper}>
            <CardChip card={card} size="md" />
          </View>
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
  cardWrapper: {},
});
```

### 5.5 src/components/table/ActionBar.tsx

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

  const handleRaiseConfirm = (amount: number) => {
    setRaiseOpen(false);
    onRaise(amount);
  };

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8 }]}>
      {raiseOpen && (
        <RaisePanel
          minRaise={minRaise}
          maxRaise={myStack}
          onConfirm={handleRaiseConfirm}
          onCancel={() => setRaiseOpen(false)}
        />
      )}
      <View style={styles.buttons}>
        <Button
          label="Fold"
          variant="secondary"
          style={styles.btn}
          onPress={onFold}
          accessibilityLabel="Fold"
        />
        <Button
          label={callAmount > 0 ? `Call ${callAmount}` : 'Check'}
          variant="primary"
          style={styles.btn}
          onPress={callAmount > 0 ? onCall : onCheck}
          accessibilityLabel={callAmount > 0 ? `Call ${callAmount}` : 'Check'}
        />
        <Button
          label="Raise"
          style={[styles.btn, styles.raiseBtn]}
          onPress={() => setRaiseOpen((v) => !v)}
          accessibilityLabel="Raise"
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

### 5.6 src/components/table/RaisePanel.tsx

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
  const [value, setValue] = useState(effectiveMin);
  const isAllIn = effectiveMin >= effectiveMax;

  return (
    <View style={styles.container}>
      <Text style={styles.label}>
        {isAllIn ? `All-in: ${value}` : `Raise to: ${value}`}
      </Text>
      <Slider
        style={styles.slider}
        minimumValue={effectiveMin}
        maximumValue={effectiveMax}
        step={1}
        value={value}
        onValueChange={(v) => setValue(Math.round(v))}
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
  label: { color: '#F8FAFC', fontWeight: '700', fontSize: 16, textAlign: 'center', marginBottom: 8 },
  slider: { width: '100%', height: 40 },
  buttons: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cancelBtn: { flex: 1 },
  confirmBtn: { flex: 2 },
});
```

### 5.7 src/components/table/HandResultOverlay.tsx

```typescript
import { useEffect } from 'react';
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
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

  const getName = (userId: string) =>
    players.find((p) => p.user_id === userId)?.display_name ?? userId;

  return (
    <Modal visible transparent animationType="fade">
      <TouchableOpacity
        style={styles.backdrop}
        activeOpacity={1}
        onPress={onDismiss}
        accessibilityLabel="Hand result, tap to dismiss"
      >
        <View style={styles.card}>
          <Text style={styles.title}>Hand #{result.hand_number} Complete</Text>

          {result.winners.map((w, i) => (
            <View key={i} style={styles.winnerRow}>
              <Text style={styles.winnerName}>
                {getName(w.user_id)} wins{' '}
                <Text style={styles.winnerAmount}>{w.amount} chips</Text>
              </Text>
              {w.hand_description ? (
                <Text style={styles.handDesc}>{w.hand_description}</Text>
              ) : null}
            </View>
          ))}

          {result.final_board.length > 0 && (
            <>
              <Text style={styles.sectionLabel}>Final Board</Text>
              <View style={styles.boardRow}>
                {result.final_board.map((card, i) => (
                  <CardChip key={i} card={card} size="sm" />
                ))}
              </View>
            </>
          )}

          {result.showdown_hands.length > 0 && (
            <>
              <Text style={styles.sectionLabel}>Showdown</Text>
              {result.showdown_hands.map((entry, i) => (
                <View key={i} style={styles.showdownRow}>
                  <Text style={styles.showdownName}>{getName(entry.user_id)}</Text>
                  <View style={styles.showdownCards}>
                    {entry.hole_cards.map((card, j) => (
                      <CardChip key={j} card={card} size="sm" />
                    ))}
                  </View>
                  {entry.hand_description ? (
                    <Text style={styles.handDesc}>{entry.hand_description}</Text>
                  ) : null}
                </View>
              ))}
            </>
          )}

          <Text style={styles.dismissHint}>Tap to dismiss</Text>
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
  title: { color: '#F8FAFC', fontWeight: '700', fontSize: 18, textAlign: 'center', marginBottom: 16 },
  winnerRow: { marginBottom: 10 },
  winnerName: { color: '#F8FAFC', fontSize: 15 },
  winnerAmount: { color: '#86EFAC', fontWeight: '700' },
  handDesc: { color: '#94A3B8', fontSize: 13, fontStyle: 'italic', marginTop: 2 },
  sectionLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: 14,
    marginBottom: 8,
  },
  boardRow: { flexDirection: 'row', gap: 6 },
  showdownRow: { marginBottom: 10 },
  showdownName: { color: '#F8FAFC', fontSize: 13, marginBottom: 4 },
  showdownCards: { flexDirection: 'row', gap: 4, marginBottom: 2 },
  dismissHint: { color: '#64748B', fontSize: 12, textAlign: 'center', marginTop: 16 },
});
```

---

## 6. PlayerList Changes

`PlayerList.tsx` receives two new props: `currentActorId: string | null`. Each player row gets:

- Actor highlight: `borderColor: '#EAB308'` when `player.user_id === currentActorId`
- My row highlight: existing `borderColor: '#2563EB'` when `player.user_id === myUserId`
- Priority: actor highlight overrides my-row highlight (actor border wins when both true)
- `current_bet > 0`: show "Bet: {n}" sub-label in grey
- `is_dealer`: show "D" badge inline
- `status === 'sit_out'` or `'disconnected'`: row opacity reduced
- Face-down card indicator: two small grey rectangles for `status === 'playing'` players who are not self

```typescript
// Updated PlayerList props interface
interface PlayerListProps {
  players: PlayerViewDTO[];
  myUserId: string;
  currentActorId: string | null;   // NEW
}
```

---

## 7. File Change Summary

| File | Change type | Description |
|------|-------------|-------------|
| `src/ws/types.ts` | Append | Add `HandEndedWinner`, `HandEndedShowdownEntry`, `HandEndedPayload` |
| `src/store/tableStore.ts` | Modify | Add `handResult` state, `clearHandResult`, `HAND_ENDED` + `HAND_STARTED` handlers |
| `app/(app)/table/[tableId].tsx` | Modify | Add derived state, reconnect re-join logic, HandInfoBar/CommunityCards/MyHoleCards/ActionBar/HandResultOverlay rendering |
| `src/components/table/HandInfoBar.tsx` | New | Hand number, phase, pot display |
| `src/components/table/CardChip.tsx` | New | Single card rendering component |
| `src/components/table/CommunityCards.tsx` | New | Community cards row |
| `src/components/table/MyHoleCards.tsx` | New | Self hole cards display |
| `src/components/table/ActionBar.tsx` | New | Fold/Check/Call/Raise buttons, sticky bottom |
| `src/components/table/RaisePanel.tsx` | New | Raise slider panel |
| `src/components/table/HandResultOverlay.tsx` | New | HAND_ENDED result modal |
| `src/components/table/PlayerList.tsx` | Modify | Add `currentActorId`, actor highlight, current_bet, dealer badge, card-back indicators |

---

## 8. Dependency Notes

`RaisePanel` uses `@react-native-community/slider`. This package is not in the current `package.json`. It must be added:

```
npm install @react-native-community/slider
```

Alternatively, React Native's built-in `Slider` (deprecated but still functional in RN 0.76) can be used as a temporary fallback. The import path would be:

```typescript
import { Slider } from 'react-native'; // deprecated, use @react-native-community/slider
```

The task breakdown marks installation of this dependency as task T-01.

---

## 9. Test Targets

New unit tests to be written in `__tests__/`:

| Test file | Coverage target |
|-----------|----------------|
| `__tests__/tableStoreHandResult.test.ts` | HAND_ENDED sets handResult; HAND_STARTED clears it; clearHandResult clears it |
| `__tests__/ActionBar.test.tsx` | canAct=false renders nothing; callAmount=0 shows Check; callAmount>0 shows Call with amount; Raise opens panel |
| `__tests__/HandResultOverlay.test.tsx` | Winner names + amounts rendered; auto-dismiss after 4s; tap dismisses; showdown section conditional |
| `__tests__/CardChip.test.tsx` | Rank and suit rendered; accessibilityLabel correct; red for hearts/diamonds |
| `__tests__/holeCardGuard.test.tsx` | Other players' hole cards never rendered even if non-null |

Full test cases are in `qa-test-plan.md`.
