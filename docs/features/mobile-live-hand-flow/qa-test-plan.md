# QA Test Plan: Mobile Live Hand Flow

**Feature:** mobile-live-hand-flow
**Date:** 2026-03-19

---

## Part A: Unit Tests (TC-01 through TC-36)

All unit tests live in `__tests__/`. They use Jest + `@testing-library/react-native`. The existing test infrastructure (jest.config.js, jest.setup.js, FakeWebSocket) is already established and is extended by these tests.

### A.1 tableStore — handResult state (TC-01 through TC-05)

Test file: `__tests__/tableStoreHandResult.test.ts`

Uses the same mock setup as `tableStore.test.ts` (TC-14 through TC-24).

---

**TC-01: HAND_ENDED event sets handResult in store**

Setup: emit `HAND_ENDED` with a valid `HandEndedPayload`.
Expected: `useTableStore.getState().handResult` equals the emitted payload.

```typescript
test('TC-01: HAND_ENDED sets handResult', () => {
  const payload: HandEndedPayload = {
    hand_id: 'h1',
    hand_number: 5,
    winners: [{ user_id: 'u1', amount: 300, hand_description: 'Full House' }],
    final_board: [
      { rank: 'A', suit: 's' },
      { rank: 'A', suit: 'h' },
      { rank: 'A', suit: 'd' },
      { rank: 'K', suit: 's' },
      { rank: 'J', suit: 'h' },
    ],
    showdown_hands: [],
  };
  emitMessage('HAND_ENDED', payload as unknown as Record<string, unknown>);
  expect(useTableStore.getState().handResult).toEqual(payload);
});
```

---

**TC-02: HAND_STARTED event clears handResult**

Setup: first emit `HAND_ENDED` to populate, then emit `HAND_STARTED`.
Expected: `handResult` is `null`.

```typescript
test('TC-02: HAND_STARTED clears handResult', () => {
  emitMessage('HAND_ENDED', { hand_id: 'h1', hand_number: 1, winners: [], final_board: [], showdown_hands: [] });
  expect(useTableStore.getState().handResult).not.toBeNull();

  emitMessage('HAND_STARTED', {});
  expect(useTableStore.getState().handResult).toBeNull();
});
```

---

**TC-03: clearHandResult() clears handResult**

Setup: emit `HAND_ENDED` to populate, then call `clearHandResult()`.
Expected: `handResult` is `null`.

```typescript
test('TC-03: clearHandResult clears handResult', () => {
  emitMessage('HAND_ENDED', { hand_id: 'h1', hand_number: 1, winners: [], final_board: [], showdown_hands: [] });
  useTableStore.getState().clearHandResult();
  expect(useTableStore.getState().handResult).toBeNull();
});
```

---

**TC-04: HAND_ENDED does not affect gameState**

Setup: emit `STATE_SNAPSHOT` then `HAND_ENDED`.
Expected: `gameState` still equals the snapshot; `handResult` is set.

```typescript
test('TC-04: HAND_ENDED does not overwrite gameState', () => {
  const snap = { table_id: 'tbl_1', your_user_id: 'u1', players: [], current_hand: null };
  emitMessage('STATE_SNAPSHOT', snap);
  emitMessage('HAND_ENDED', { hand_id: 'h1', hand_number: 1, winners: [], final_board: [], showdown_hands: [] });
  expect(useTableStore.getState().gameState).toEqual(snap);
  expect(useTableStore.getState().handResult).not.toBeNull();
});
```

---

**TC-05: reset() clears handResult**

Setup: emit `HAND_ENDED`, then call `reset()`.
Expected: `handResult` is `null`.

```typescript
test('TC-05: reset clears handResult', () => {
  emitMessage('HAND_ENDED', { hand_id: 'h1', hand_number: 1, winners: [], final_board: [], showdown_hands: [] });
  useTableStore.getState().reset();
  expect(useTableStore.getState().handResult).toBeNull();
});
```

---

### A.2 canAct derivation logic (TC-06 through TC-10)

Test file: `__tests__/canActDerivation.test.ts`

These tests verify the boolean logic that controls whether the ActionBar renders. Tested as pure function logic — extract and test `deriveCanAct`:

```typescript
// Testable helper (to be exported from a utils module or tested via rendered component)
function deriveCanAct(
  gameState: StateSnapshotDTO | null,
  connectionStatus: ConnectionStatus,
): boolean {
  if (!gameState?.current_hand) return false;
  if (connectionStatus !== 'connected') return false;
  const myPlayer = gameState.players.find(p => p.user_id === gameState.your_user_id);
  if (!myPlayer) return false;
  return (
    gameState.current_hand.current_actor_id === gameState.your_user_id &&
    myPlayer.status === 'playing'
  );
}
```

---

**TC-06: canAct is true when current_actor_id equals your_user_id and status is playing**

```typescript
test('TC-06: canAct true when actor matches and status is playing', () => {
  const gs = makeGameState({ actorId: 'u1', myStatus: 'playing' });
  expect(deriveCanAct(gs, 'connected')).toBe(true);
});
```

---

**TC-07: canAct is false when current_actor_id is a different player**

```typescript
test('TC-07: canAct false when actor is another player', () => {
  const gs = makeGameState({ actorId: 'u2', myStatus: 'playing' });
  expect(deriveCanAct(gs, 'connected')).toBe(false);
});
```

---

**TC-08: canAct is false when myPlayer status is sit_out (even if actor matches)**

```typescript
test('TC-08: canAct false when my status is sit_out', () => {
  const gs = makeGameState({ actorId: 'u1', myStatus: 'sit_out' });
  expect(deriveCanAct(gs, 'connected')).toBe(false);
});
```

---

**TC-09: canAct is false when myPlayer status is watcher**

```typescript
test('TC-09: canAct false when my status is watcher', () => {
  const gs = makeGameState({ actorId: 'u1', myStatus: 'watcher' });
  expect(deriveCanAct(gs, 'connected')).toBe(false);
});
```

---

**TC-10: canAct is false when connectionStatus is not connected**

```typescript
test('TC-10: canAct false when disconnected even if actor matches', () => {
  const gs = makeGameState({ actorId: 'u1', myStatus: 'playing' });
  expect(deriveCanAct(gs, 'reconnecting')).toBe(false);
  expect(deriveCanAct(gs, 'disconnected')).toBe(false);
  expect(deriveCanAct(gs, 'failed')).toBe(false);
});
```

---

**TC-11: canAct is false when current_hand is null**

```typescript
test('TC-11: canAct false when no hand in progress', () => {
  const gs = makeGameStateNoHand();
  expect(deriveCanAct(gs, 'connected')).toBe(false);
});
```

---

**TC-12: canAct is false when gameState is null**

```typescript
test('TC-12: canAct false when gameState is null', () => {
  expect(deriveCanAct(null, 'connected')).toBe(false);
});
```

---

**TC-13: canAct is false when current_actor_id is null (between actions)**

```typescript
test('TC-13: canAct false when current_actor_id is null', () => {
  const gs = makeGameState({ actorId: null, myStatus: 'playing' });
  expect(deriveCanAct(gs, 'connected')).toBe(false);
});
```

---

### A.3 ActionBar component (TC-14 through TC-18)

Test file: `__tests__/ActionBar.test.tsx`

Uses `@testing-library/react-native` render.

---

**TC-14: ActionBar shows Check when callAmount is 0**

```typescript
test('TC-14: shows Check button when callAmount is 0', () => {
  const { getByText } = render(
    <ActionBar callAmount={0} minRaise={100} myStack={500}
      onFold={jest.fn()} onCheck={jest.fn()} onCall={jest.fn()} onRaise={jest.fn()} />
  );
  expect(getByText('Check')).toBeTruthy();
  expect(queryByText('Call')).toBeNull();
});
```

---

**TC-15: ActionBar shows "Call 150" when callAmount is 150**

```typescript
test('TC-15: shows Call 150 when callAmount is 150', () => {
  const { getByText } = render(
    <ActionBar callAmount={150} minRaise={100} myStack={500}
      onFold={jest.fn()} onCheck={jest.fn()} onCall={jest.fn()} onRaise={jest.fn()} />
  );
  expect(getByText('Call 150')).toBeTruthy();
});
```

---

**TC-16: Tapping Fold calls onFold**

```typescript
test('TC-16: tapping Fold calls onFold', () => {
  const onFold = jest.fn();
  const { getByText } = render(
    <ActionBar callAmount={0} minRaise={100} myStack={500}
      onFold={onFold} onCheck={jest.fn()} onCall={jest.fn()} onRaise={jest.fn()} />
  );
  fireEvent.press(getByText('Fold'));
  expect(onFold).toHaveBeenCalledTimes(1);
});
```

---

**TC-17: Tapping Raise opens RaisePanel**

```typescript
test('TC-17: tapping Raise shows RaisePanel', () => {
  const { getByText, queryByText } = render(
    <ActionBar callAmount={0} minRaise={100} myStack={500}
      onFold={jest.fn()} onCheck={jest.fn()} onCall={jest.fn()} onRaise={jest.fn()} />
  );
  expect(queryByText(/Raise to/)).toBeNull();
  fireEvent.press(getByText('Raise'));
  expect(getByText(/Raise to/)).toBeTruthy();
});
```

---

**TC-18: RaisePanel Cancel collapses panel without calling onRaise**

```typescript
test('TC-18: Cancel collapses RaisePanel without calling onRaise', () => {
  const onRaise = jest.fn();
  const { getByText, queryByText } = render(
    <ActionBar callAmount={0} minRaise={100} myStack={500}
      onFold={jest.fn()} onCheck={jest.fn()} onCall={jest.fn()} onRaise={onRaise} />
  );
  fireEvent.press(getByText('Raise'));
  fireEvent.press(getByText('Cancel'));
  expect(queryByText(/Raise to/)).toBeNull();
  expect(onRaise).not.toHaveBeenCalled();
});
```

---

### A.4 RaisePanel slider bounds (TC-19 through TC-21)

Test file: `__tests__/RaisePanel.test.tsx`

---

**TC-19: RaisePanel initializes slider at minRaise**

```typescript
test('TC-19: RaisePanel label shows minRaise as initial value', () => {
  const { getByText } = render(
    <RaisePanel minRaise={100} maxRaise={500} onConfirm={jest.fn()} onCancel={jest.fn()} />
  );
  expect(getByText('Raise to: 100')).toBeTruthy();
});
```

---

**TC-20: RaisePanel shows All-in label when minRaise >= maxRaise**

```typescript
test('TC-20: shows All-in label when all-in', () => {
  const { getByText } = render(
    <RaisePanel minRaise={500} maxRaise={500} onConfirm={jest.fn()} onCancel={jest.fn()} />
  );
  expect(getByText('All-in: 500')).toBeTruthy();
});
```

---

**TC-21: Confirm Raise calls onConfirm with current slider value**

```typescript
test('TC-21: Confirm Raise calls onConfirm with value', () => {
  const onConfirm = jest.fn();
  const { getByText } = render(
    <RaisePanel minRaise={100} maxRaise={500} onConfirm={onConfirm} onCancel={jest.fn()} />
  );
  fireEvent.press(getByText('Confirm Raise'));
  expect(onConfirm).toHaveBeenCalledWith(100); // initial value = minRaise
});
```

---

### A.5 Hole card guard (TC-22 through TC-24)

Test file: `__tests__/holeCardGuard.test.tsx`

---

**TC-22: MyHoleCards renders cards for self**

```typescript
test('TC-22: MyHoleCards renders card rank and suit', () => {
  const cards: CardDTO[] = [{ rank: 'A', suit: 's' }, { rank: 'K', suit: 'h' }];
  const { getAllByLabelText } = render(<MyHoleCards cards={cards} />);
  expect(getAllByLabelText(/ace of spades/i)).toHaveLength(1);
  expect(getAllByLabelText(/king of hearts/i)).toHaveLength(1);
});
```

---

**TC-23: PlayerList does not render other players' hole cards even if non-null**

```typescript
test('TC-23: PlayerList never shows other players hole cards', () => {
  const players: PlayerViewDTO[] = [
    {
      user_id: 'u2',
      display_name: 'Alice',
      status: 'playing',
      stack: 1000,
      seat: 1,
      is_dealer: false,
      hole_cards: [{ rank: 'A', suit: 's' }, { rank: 'K', suit: 'h' }], // server sent (should not happen, but guard)
      current_bet: 0,
      reserve_until: null,
    },
  ];
  const { queryByLabelText } = render(
    <PlayerList players={players} myUserId="u1" currentActorId={null} />
  );
  // No card chips labeled with actual ranks for other players
  expect(queryByLabelText(/ace of spades/i)).toBeNull();
  expect(queryByLabelText(/king of hearts/i)).toBeNull();
});
```

---

**TC-24: showMyCards guard is false when hole_cards is null**

```typescript
test('TC-24: showMyCards is false when hole_cards is null', () => {
  const myPlayer: PlayerViewDTO = {
    user_id: 'u1', display_name: 'Me', status: 'playing',
    stack: 500, seat: 2, is_dealer: false, hole_cards: null,
    current_bet: 0, reserve_until: null,
  };
  // Verify guard logic: hole_cards null → MyHoleCards not rendered
  const showMyCards = myPlayer?.hole_cards != null && myPlayer.hole_cards.length > 0;
  expect(showMyCards).toBe(false);
});
```

---

### A.6 HandResultOverlay (TC-25 through TC-29)

Test file: `__tests__/HandResultOverlay.test.tsx`

---

**TC-25: HandResultOverlay shows winner name and amount**

```typescript
test('TC-25: shows winner name and amount', () => {
  const players: PlayerViewDTO[] = [
    { user_id: 'u1', display_name: 'Alice', status: 'playing', stack: 0,
      seat: 1, is_dealer: false, hole_cards: null, current_bet: 0, reserve_until: null },
  ];
  const result: HandEndedPayload = {
    hand_id: 'h1', hand_number: 5,
    winners: [{ user_id: 'u1', amount: 300, hand_description: 'Full House' }],
    final_board: [], showdown_hands: [],
  };
  const { getByText } = render(
    <HandResultOverlay result={result} players={players} onDismiss={jest.fn()} />
  );
  expect(getByText(/Alice/)).toBeTruthy();
  expect(getByText(/300 chips/)).toBeTruthy();
  expect(getByText(/Full House/)).toBeTruthy();
});
```

---

**TC-26: HandResultOverlay shows "Hand #5 Complete" title**

```typescript
test('TC-26: shows hand number in title', () => {
  const { getByText } = render(
    <HandResultOverlay result={makeResult(5)} players={[]} onDismiss={jest.fn()} />
  );
  expect(getByText('Hand #5 Complete')).toBeTruthy();
});
```

---

**TC-27: HandResultOverlay calls onDismiss after 4 seconds**

```typescript
test('TC-27: auto-dismisses after 4000ms', () => {
  jest.useFakeTimers();
  const onDismiss = jest.fn();
  render(<HandResultOverlay result={makeResult(1)} players={[]} onDismiss={onDismiss} />);
  expect(onDismiss).not.toHaveBeenCalled();
  jest.advanceTimersByTime(4000);
  expect(onDismiss).toHaveBeenCalledTimes(1);
  jest.useRealTimers();
});
```

---

**TC-28: HandResultOverlay calls onDismiss on tap**

```typescript
test('TC-28: calls onDismiss on tap', () => {
  const onDismiss = jest.fn();
  const { getByLabelText } = render(
    <HandResultOverlay result={makeResult(1)} players={[]} onDismiss={onDismiss} />
  );
  fireEvent.press(getByLabelText('Hand result, tap to dismiss'));
  expect(onDismiss).toHaveBeenCalledTimes(1);
});
```

---

**TC-29: HandResultOverlay does not show Showdown section when showdown_hands is empty**

```typescript
test('TC-29: no Showdown section when showdown_hands is empty', () => {
  const { queryByText } = render(
    <HandResultOverlay result={makeResult(1)} players={[]} onDismiss={jest.fn()} />
  );
  expect(queryByText(/Showdown/i)).toBeNull();
});
```

---

### A.7 CardChip (TC-30 through TC-32)

Test file: `__tests__/CardChip.test.tsx`

---

**TC-30: CardChip renders rank and suit symbol**

```typescript
test('TC-30: renders rank and spade symbol for As', () => {
  const { getByText } = render(<CardChip card={{ rank: 'A', suit: 's' }} />);
  expect(getByText('A')).toBeTruthy();
  expect(getByText('♠')).toBeTruthy();
});
```

---

**TC-31: CardChip accessibility label is correct**

```typescript
test('TC-31: accessibilityLabel is rank of suit-name', () => {
  const { getByLabelText } = render(<CardChip card={{ rank: 'K', suit: 'h' }} />);
  expect(getByLabelText('K of hearts')).toBeTruthy();
});
```

---

**TC-32: CardChip suit color is red for hearts**

```typescript
test('TC-32: heart suit text has red color style', () => {
  const { getByText } = render(<CardChip card={{ rank: '2', suit: 'h' }} />);
  const suitText = getByText('♥');
  expect(suitText.props.style).toMatchObject(expect.arrayContaining([
    expect.objectContaining({ color: '#EF4444' }),
  ]));
});
```

---

### A.8 HandInfoBar (TC-33 through TC-35)

Test file: `__tests__/HandInfoBar.test.tsx`

---

**TC-33: HandInfoBar renders hand number**

```typescript
test('TC-33: shows Hand #42', () => {
  const { getByText } = render(<HandInfoBar handNumber={42} phase="preflop" totalPot={150} />);
  expect(getByText('Hand #42')).toBeTruthy();
});
```

---

**TC-34: HandInfoBar renders phase label Pre-Flop for preflop**

```typescript
test('TC-34: phase preflop renders Pre-Flop label', () => {
  const { getByText } = render(<HandInfoBar handNumber={1} phase="preflop" totalPot={0} />);
  expect(getByText('Pre-Flop')).toBeTruthy();
});
```

---

**TC-35: HandInfoBar renders total pot**

```typescript
test('TC-35: renders Pot: 300', () => {
  const { getByText } = render(<HandInfoBar handNumber={1} phase="flop" totalPot={300} />);
  expect(getByText('Pot: 300')).toBeTruthy();
});
```

---

### A.9 CommunityCards (TC-36)

Test file: `__tests__/CommunityCards.test.tsx`

---

**TC-36: CommunityCards shows waiting text when cards is empty**

```typescript
test('TC-36: shows waiting text when no community cards', () => {
  const { getByText } = render(<CommunityCards cards={[]} phase="preflop" />);
  expect(getByText('Waiting for flop…')).toBeTruthy();
});
```

---

## Part B: Manual E2E Scenarios (TC-M1 through TC-M8)

These are performed on a physical device or emulator against a running backend.

---

**TC-M1: Player sees live hand board**

Preconditions: Two players in the same table, both seated and playing. A hand is in progress.

Steps:
1. Open table screen as Player A.
2. Observe the hand info zone.

Expected:
- HandInfoBar shows "Hand #N" and the current phase label.
- Pot amount matches the sum sent by server.
- Community cards are shown matching the current phase (0 on preflop, 3 on flop, etc.).

Pass criteria: All three elements render correctly and update when state updates.

---

**TC-M2: Player sees action controls on their turn**

Preconditions: Same as TC-M1; it is Player A's turn.

Steps:
1. Observe the bottom of the table screen when `current_actor_id === your_user_id`.

Expected:
- ActionBar slides up from the bottom.
- Buttons visible: "Fold", either "Check" (if no bet) or "Call X", and "Raise".
- Player A's row has a yellow border highlight.

Pass criteria: ActionBar appears within 500ms of STATE_SNAPSHOT arrival.

---

**TC-M3: Player performs Check action**

Preconditions: It is Player A's turn, no bet to call (`call_amount === 0`).

Steps:
1. Tap "Check".

Expected:
- `CHECK` WS message sent.
- ActionBar disappears immediately.
- Server responds with STATE_SNAPSHOT showing next actor.
- Next player's row highlighted in yellow.

Pass criteria: No errors; ActionBar not visible for Player A after sending.

---

**TC-M4: Hand result overlay appears at hand end**

Preconditions: A hand is reaching conclusion (river or showdown).

Steps:
1. Wait for `HAND_ENDED` event.

Expected:
- Overlay appears over the table with "Hand #N Complete".
- Winner name(s), amount(s), and hand description shown.
- Final board displayed as card chips.
- Showdown section shown if server sent showdown_hands.
- Overlay auto-dismisses after 4 seconds if not tapped.

Pass criteria: Overlay appears, content matches server payload, auto-dismiss triggers.

---

**TC-M5: Hand result overlay dismisses on tap**

Preconditions: Overlay is visible (TC-M4 in progress, within 4 seconds).

Steps:
1. Tap anywhere on the overlay before the 4-second timer.

Expected:
- Overlay dismisses immediately.
- Table screen returns to normal state.
- `handResult` in store is null.

Pass criteria: Dismiss is instant on tap; no lingering overlay.

---

**TC-M6: Spectator (watcher) sees board but has no action controls**

Preconditions: User joins with role 'watcher'. A hand is in progress.

Steps:
1. Observe the table screen.

Expected:
- HandInfoBar, CommunityCards visible.
- Player list visible with all players.
- No ActionBar at any point, even when `current_actor_id` changes.
- RoleBadge in header shows "Watching" (blue).
- No sit-out banner shown.

Pass criteria: ActionBar never appears for watcher under any game state.

---

**TC-M7: Reconnect during live hand restores game state**

Preconditions: Player A is seated and a hand is in progress.

Steps:
1. Simulate a network drop (airplane mode for 2 seconds, then restore).
2. Observe connection banner and eventual state restoration.

Expected:
- ConnectionBanner shows "Reconnecting… (1/3)" during backoff.
- Green "Reconnected" flash banner appears when connection restores.
- JOIN is re-sent automatically with preserved role ('player').
- Server responds with STATE_SNAPSHOT; game state is fully restored.
- If it was Player A's turn before disconnection and still is after reconnect, ActionBar re-appears.

Pass criteria: Full game state restored within 5 seconds of network restoration; no stale state visible.

---

**TC-M8: Raise panel bounds are correct**

Preconditions: It is Player A's turn; `min_raise` is 200; Player A's stack is 800.

Steps:
1. Tap "Raise".
2. Observe the slider.
3. Try to move slider to minimum position.
4. Try to move slider to maximum position.
5. Set to 350 and tap "Confirm Raise".

Expected:
- Slider minimum value is 200.
- Slider maximum value is 800.
- Label reads "Raise to: {value}".
- Confirming at 350 sends `RAISE { amount: 350 }` WS message.

Pass criteria: Slider does not allow values below `min_raise` or above player stack. Correct amount sent.

---

## Test Coverage Summary

| Category | Count |
|----------|-------|
| Unit tests (TC-01 – TC-36) | 36 |
| Manual E2E (TC-M1 – TC-M8) | 8 |
| **Total** | **44** |

---

## Test Environment Notes

- Unit tests: `npm test` in `mobile/` — uses jest-expo preset, FakeWebSocket, Zustand store resets in `beforeEach`
- E2E: Requires running backend at `ws://localhost:8000` with at least 2 registered test users
- Device: iOS Simulator (iPhone 15) and Android Emulator (Pixel 7 API 34) for manual tests
- The existing `jest.setup.js` must mock `@react-native-community/slider` if it is not available in the test environment:

```javascript
// jest.setup.js addition
jest.mock('@react-native-community/slider', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    __esModule: true,
    default: (props) => React.createElement(View, {
      testID: 'slider',
      accessibilityLabel: props.accessibilityLabel,
    }),
  };
});
```
