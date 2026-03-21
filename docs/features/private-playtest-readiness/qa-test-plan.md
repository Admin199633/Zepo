# QA Test Plan: private-playtest-readiness

**Date:** 2026-03-19
**Base test count:** 71 passing (TC-01 through TC-34 + existing component tests)
**New tests:** TC-35 through TC-52 (18 unit/component) + TC-M1 through TC-M8 (8 manual E2E)

---

## 1. Test Strategy

| Layer | Tool | Coverage |
|-------|------|----------|
| Store unit tests | Jest + Zustand `getState()` / `setState()` | State mutations, message handling, SocketClient mock calls |
| Component tests | @testing-library/react-native | Rendered output, press handlers, conditional visibility |
| Manual E2E | Real device(s) + real backend | Full user journeys, network interruption, multi-device behavior |

### Mock harness (re-used as-is)
- `jest.setup.js`: AsyncStorage, expo-router, expo-constants, slider, safe-area-context
- SocketClient mock factory pattern from `tableStore.test.ts` (define state inside factory, expose via `__instance`)
- `jest.mock('react-native', () => ({ AppState: { addEventListener: jest.fn(() => ({ remove: jest.fn() })) } }))`

### New test files
| File | TCs |
|------|-----|
| `__tests__/tableStoreJoinPending.test.ts` | TC-35 – TC-40 |
| `__tests__/tableStoreDisconnectReset.test.ts` | TC-41 |
| `__tests__/tableStoreSyncRequest.test.ts` | TC-42 – TC-43 |
| `__tests__/ConnectionBanner.test.tsx` | TC-44 – TC-50 |
| `__tests__/TableInfoCard.test.tsx` | TC-51 – TC-52 |
| `__tests__/tableStore.test.ts` | TC-24 updated (existing) |

---

## 2. Unit Tests

### 2.1 tableStore — joinPending field

**TC-35**
- Description: `joinPending` is `false` in the initial state.
- Steps: `useTableStore.getState().reset()`. Read `joinPending`.
- Expected: `false`.
- File: `tableStoreJoinPending.test.ts`

**TC-36**
- Description: `joinPending` becomes `true` immediately after `sendJoin('player')`.
- Steps: Call `sendJoin('player')`. Read `joinPending`.
- Expected: `true`.
- File: `tableStoreJoinPending.test.ts`

**TC-37**
- Description: `joinPending` becomes `true` after `sendJoin('watcher')`.
- Steps: Call `sendJoin('watcher')`. Read `joinPending`.
- Expected: `true`.
- File: `tableStoreJoinPending.test.ts`

**TC-38**
- Description: `STATE_SNAPSHOT` clears `joinPending` to `false`.
- Steps: `sendJoin('player')` (sets true). `mock.__emit_message({ type: 'STATE_SNAPSHOT', payload: MOCK_SNAPSHOT })`. Read `joinPending`.
- Expected: `false`. `gameState` equals `MOCK_SNAPSHOT`.
- File: `tableStoreJoinPending.test.ts`

**TC-39**
- Description: `disconnect()` clears `joinPending` to `false`.
- Steps: `sendJoin('player')`. `disconnect()`. Read `joinPending`.
- Expected: `false`.
- File: `tableStoreJoinPending.test.ts`

**TC-40**
- Description: `reset()` clears `joinPending` to `false`.
- Steps: `sendJoin('player')`. `reset()`. Read `joinPending`.
- Expected: `false`.
- File: `tableStoreJoinPending.test.ts`

---

### 2.2 tableStore — reset-on-disconnect

**TC-41**
- Description: `gameState` is `null` after `disconnect()` even if `STATE_SNAPSHOT` was previously received.
- Steps: `connect('t1', 'tok')`. `mock.__emit_message({ type: 'STATE_SNAPSHOT', payload: MOCK_SNAPSHOT })`. Confirm `gameState !== null`. `disconnect()`. Read `gameState`.
- Expected: `null`.
- Notes: Will FAIL against existing code — this is the acceptance gate for the state-reset sub-feature.
- File: `tableStoreDisconnectReset.test.ts`

---

### 2.3 tableStore — SYNC_REQUEST on foreground resume

**TC-42**
- Description: `send('SYNC_REQUEST')` is called when foreground-resume fires while `connectionStatus === 'connected'`.
- Steps:
  1. Capture `AppState.addEventListener` callback.
  2. `connect('t1', 'tok')`. `mock.__emit_status('connected')`.
  3. Call AppState callback with `'active'`.
  4. Assert `mock.send` called with `('SYNC_REQUEST')`.
- Expected: `mock.send` called with `'SYNC_REQUEST'`.
- Notes: Will FAIL against existing code — acceptance gate for foreground SYNC_REQUEST.
- File: `tableStoreSyncRequest.test.ts`

**TC-43**
- Description: `socketClient.connect` is NOT called again (no duplicate reconnect) when foreground-resume fires while `connectionStatus === 'connected'`.
- Steps: Follow TC-42 setup. After calling AppState callback, check `mock.connect` call count.
- Expected: `mock.connect` called exactly once (initial connect), not twice.
- File: `tableStoreSyncRequest.test.ts`

---

### 2.4 tableStore — TC-24 update (existing test)

**TC-24 (updated)**
- Description: `reset()` clears all state including new `joinPending` field.
- Add assertions: `expect(joinPending).toBe(false)` and after `STATE_SNAPSHOT` then `reset()`: `expect(gameState).toBeNull()`.
- File: `__tests__/tableStore.test.ts`

---

## 3. Component Tests

### 3.1 ConnectionBanner

**TC-44**
- Description: Renders `null` when `status === 'connected'`.
- Steps: `render(<ConnectionBanner status="connected" attempt={0} maxAttempts={3} />)`.
- Expected: No visible elements.
- File: `ConnectionBanner.test.tsx`

**TC-45**
- Description: Renders "Connecting…" text when `status === 'connecting'`.
- Steps: `render(<ConnectionBanner status="connecting" attempt={0} maxAttempts={3} />)`.
- Expected: `getByText('Connecting…')` truthy.
- File: `ConnectionBanner.test.tsx`

**TC-46**
- Description: Renders reconnecting text with attempt count when `status === 'reconnecting'`.
- Steps: `render(<ConnectionBanner status="reconnecting" attempt={2} maxAttempts={3} />)`.
- Expected: `getByText('Reconnecting… (2/3)')` truthy.
- File: `ConnectionBanner.test.tsx`

**TC-47**
- Description: Renders error text when `status === 'failed'`.
- Steps: `render(<ConnectionBanner status="failed" attempt={3} maxAttempts={3} onRetry={jest.fn()} />)`.
- Expected: Text matching "Connection failed" visible.
- File: `ConnectionBanner.test.tsx`

**TC-48**
- Description: Retry button IS rendered when `status === 'failed'` and `onRetry` is provided.
- Steps: Same as TC-47.
- Expected: `getByLabelText('Retry connection')` truthy.
- Notes: Will FAIL against existing code — acceptance gate for retry button feature.
- File: `ConnectionBanner.test.tsx`

**TC-49**
- Description: Pressing retry button calls `onRetry` exactly once.
- Steps: Render with `status="failed"` and `onRetry={jest.fn()}`. `fireEvent.press(getByLabelText('Retry connection'))`.
- Expected: `onRetry` called once.
- File: `ConnectionBanner.test.tsx`

**TC-50**
- Description: Retry button NOT rendered when `status === 'reconnecting'`.
- Steps: `render(<ConnectionBanner status="reconnecting" attempt={1} maxAttempts={3} onRetry={jest.fn()} />)`.
- Expected: `queryByLabelText('Retry connection')` is `null`.
- File: `ConnectionBanner.test.tsx`

---

### 3.2 TableInfoCard

**TC-51**
- Description: Renders blinds, stack, and max players from config.
- Steps: Render `<TableInfoCard config={MOCK_CONFIG} />` where `MOCK_CONFIG = { small_blind: 5, big_blind: 10, starting_stack: 1000, max_players: 8, turn_timer_seconds: 30, house_rules: [] }`.
- Expected: Text "5" or "5 / 10" visible, text "1000" or "1000 chips" visible, text "8" visible.
- File: `TableInfoCard.test.tsx`

**TC-52**
- Description: House rules section omitted when `house_rules` is empty array.
- Steps: Same config as TC-51 with `house_rules: []`.
- Expected: No text mentioning "house rules" or empty array artifacts in rendered output.
- File: `TableInfoCard.test.tsx`

---

## 4. Manual E2E Scenarios

All require: backend running, 1–3 physical devices, network simulation tools.

---

**TC-M1 — Happy path: auth → club → table → play 3 hands**
- Devices: 2 (Player A, Player B)
- Steps:
  1. Both players cold-start app, complete OTP auth.
  2. Player A creates a club, shares invite code.
  3. Player B joins via invite code.
  4. Both tap club → see loading spinner → club detail with Table Config Card (blinds, stack, max players).
  5. Both tap "Enter Table" → see "Connecting to table…" spinner → role modal → select Play.
  6. Both see "Joining table…" indicator briefly, then table loads.
  7. Play 3 complete hands. Hand result overlay appears each time. Overlay auto-dismisses or tap-dismissed.
- Pass criteria: No crash. Loading states visible. Table config correct. Hand numbers increment. Overlay clears cleanly between hands.

---

**TC-M2 — Join as spectator**
- Devices: 2 (1 player, 1 watcher)
- Steps:
  1. Player A enters table, selects "Play".
  2. Player B enters same table, selects "Watch".
  3. Player A plays a hand.
- Pass criteria: Player B has no ActionBar. Player B sees real-time PlayerList updates. Player A's action bar appears on their turn.

---

**TC-M3 — Reconnect during a hand**
- Devices: 1
- Steps:
  1. Enter table, select Play, hand in progress.
  2. Enable airplane mode. Observe: ConnectionBanner → reconnecting → failed (after 3 attempts, ~7s total: 1+2+4).
  3. Disable airplane mode.
  4. Tap "Retry Connection" button.
  5. Observe: banner → connecting → connected. "Back online" banner flashes.
  6. Verify hand state restored (community cards, pot, whose turn it is).
- Pass criteria: Attempt counter shows 1/3, 2/3, 3/3 before failing. Retry button visible only on failed. State consistent after retry.

---

**TC-M4 — Reconnect between hands**
- Devices: 1
- Steps:
  1. Hand ends, overlay dismissed.
  2. Enable airplane mode. Wait for failed state.
  3. Disable airplane mode. Tap Retry (or if within backoff window, observe auto-reconnect).
  4. Wait for next hand to start.
- Pass criteria: No stale game state visible after reconnect. Next hand starts correctly. "Joining table…" indicator not stuck.

---

**TC-M5 — App background during hand, foreground resume**
- Devices: 1
- Steps:
  1. Hand in progress. Press Home button (app backgrounds).
  2. Wait 15 seconds.
  3. Return app to foreground.
  4. Observe: ConnectionBanner shows connecting → connected (auto-reconnect fires).
  5. Verify SYNC_REQUEST sent (check Metro/backend logs for `[Zepo:TableStore] sendSyncRequest: sent`).
  6. Game state matches current server state.
- Pass criteria: Auto-reconnect fires without user action. SYNC_REQUEST log visible. State correct after resume.

---

**TC-M6 — WS failed state + retry button**
- Devices: 1
- Steps:
  1. Enter table.
  2. Kill network. Wait for all 3 retries to exhaust (~7 seconds).
  3. Verify red ConnectionBanner with "Connection failed" text and "Retry Connection" button.
  4. Restore network.
  5. Tap "Retry Connection".
  6. Verify banner → connecting → connected. Role modal does NOT reappear.
  7. Verify SYNC_REQUEST sent, game state restored.
- Pass criteria: Retry button only visible on failed state. Role modal suppressed on retry. Game state consistent after retry.

---

**TC-M7 — Background/foreground does not auto-reconnect on failed state**
- Devices: 1
- Steps:
  1. Kill network, reach failed state.
  2. Press Home button (background).
  3. Restore network.
  4. Return app to foreground.
  5. Verify: ConnectionBanner still shows failed state. No auto-reconnect fired.
  6. Tap Retry manually.
- Pass criteria: App does NOT auto-reconnect from failed state on foreground resume. User must press Retry. This verifies the AppState handler was changed correctly.

---

**TC-M8 — Multiple players: 2–3 devices, full 30-min session**
- Devices: 3 (Player A, Player B, Player C)
- Steps:
  1. All 3 authenticate and join the same table.
  2. A and B select Play. C selects Watch.
  3. Play 5 hands.
  4. Mid-session: Player B backgrounds app for 15 seconds, returns. Verify reconnect.
  5. One player sits out via sit-out banner. Verify "Sending request…" state, then sits back in.
  6. Player A folds on first action for 2 consecutive hands.
- Pass criteria: All clients show identical game state at all times. No split-brain winner announcements. B reconnects without disrupting active hand. Sit-out/sit-in flow works with pending indicator. No crash across 5 hands.

---

## 5. Regression Risk

| Test ID | File | Risk | Reason |
|---------|------|------|--------|
| TC-24 | `tableStore.test.ts` | HIGH | Adding `joinPending` to `TableState` requires updating `reset()` and all `setState` calls in tests. If `reset()` omits `joinPending`, TC-24 fails. Must be updated as part of T-16. |
| TC-20 | `tableStore.test.ts` | MEDIUM | Tests `disconnect()` calls `mock.disconnect`. Extending `disconnect()` to also `set({ gameState: null })` does not break TC-20, but TC-41 is the new gate. |
| TC-14 | `tableStore.test.ts` | MEDIUM | Tests initial state. Adding `joinPending` field means TS compilation fails if initial state doesn't include it. Must be included in the store's initial state object. |
| TC-01–TC-05 | `tableStoreHandResult.test.ts` | LOW | These use partial `useTableStore.setState(...)`. Zustand v5 allows partial setState; no breakage expected. Verify TS compilation with `npx tsc --noEmit`. |
| All component tests | various | LOW | Adding `onRetry` prop to `ConnectionBanner` is additive (optional prop). Existing render tests that don't pass `onRetry` will simply not show the retry button — correct behavior. |

**Pre-implementation gate:** Run `npx tsc --noEmit` before running Jest whenever the `TableState` interface changes.

---

## 6. Playtest Readiness Checklist

### Code
- [ ] `tableStore.ts` interface includes `joinPending: boolean`
- [ ] `sendJoin()` sets `joinPending = true`
- [ ] `STATE_SNAPSHOT` handler clears `joinPending = false`
- [ ] `disconnect()` clears `gameState = null`, `handResult = null`, `joinPending = false`
- [ ] `reset()` includes `joinPending: false`
- [ ] AppState handler does NOT auto-connect when `connectionStatus === 'failed'`
- [ ] AppState handler sends `SYNC_REQUEST` when `connectionStatus === 'connected'` on foreground resume
- [ ] `ConnectionBanner` accepts `onRetry?: () => void` prop
- [ ] "Retry Connection" button (accessibilityLabel="Retry connection") renders only when `status === 'failed'`
- [ ] `TableScreen` passes `onRetry` wired to `connect(tableId, token)` to `ConnectionBanner`
- [ ] Club detail screen renders `TableInfoCard` when `tableInfo !== null`
- [ ] Instrumentation logs visible in Metro console at: WS connect, WS open, WS close, WS failed, sendJoin, STATE_SNAPSHOT received, SYNC_REQUEST sent, AppState change

### Tests
- [ ] All 71 existing tests still pass (`npx jest --no-coverage`)
- [ ] All new tests TC-35 through TC-52 pass
- [ ] `npx tsc --noEmit` exits 0

### Manual verification
- [ ] TC-M1 (happy path, 2 devices) passes across 3 hands
- [ ] TC-M6 (WS failed + retry) passes — retry button visible and functional
- [ ] TC-M5 (background/foreground) passes — SYNC_REQUEST in logs
- [ ] Club detail shows blinds and stack before entering table
- [ ] Connection banner absent during normal play
- [ ] "Back online" flash shows after reconnect
- [ ] "Joining table…" indicator appears and clears on role selection

---

## 7. What This Feature Does NOT Prove

- **Multi-table navigation.** SocketClient is a singleton. Navigating from one table to another requires disconnect → reconnect. This flow is not tested.
- **Token expiry mid-session.** The 401 logout hook covers REST. WS token expiry causes a server-side close; client has no specific handling beyond the reconnect logic.
- **Server SYNC_REQUEST behavior.** The plan verifies the client sends it. It does not verify the backend returns a correct STATE_SNAPSHOT in response.
- **Double-JOIN race condition.** If the network flickers during the role modal, `sendJoin` could be called twice. Not covered.
- **Sit-in/sit-out mid-hand state.** The `sendSitIn`/`sendSitOut` happy paths are unit-tested but the full UI feedback lifecycle is not component-tested.
- **Error envelope display.** `tableStore.error` is set but the table screen does not currently render it. Not changed in this phase.
- **OTP delivery reliability.** SMS latency is outside scope.
- **Tablet / landscape layout.** All components use fixed values; not tested on tablets.
- **Long-session memory.** No profiling or memory leak testing is included.
- **Accessibility.** Only `accessibilityLabel` on interactive elements is set; screen reader compatibility not validated.

---

## 8. Test Runtime Budget

### New automated tests
| File | New TCs | Est. per TC | Subtotal |
|------|---------|-------------|----------|
| `tableStoreJoinPending.test.ts` | 6 | ~15ms | ~90ms |
| `tableStoreDisconnectReset.test.ts` | 1 | ~15ms | ~15ms |
| `tableStoreSyncRequest.test.ts` | 2 | ~15ms | ~30ms |
| `ConnectionBanner.test.tsx` | 7 | ~30ms | ~210ms |
| `TableInfoCard.test.tsx` | 2 | ~30ms | ~60ms |
| **Total new** | **18** | | **~405ms** |

### Projected full suite
| | Count | Est. Runtime |
|-|-------|-------------|
| Existing | 71 | ~8s |
| New | 18 | ~2s |
| **Total** | **89** | **~10s** |

Well within a sub-30-second CI budget.

### Manual E2E budget
| Scenario | Est. Time |
|----------|----------|
| TC-M1 (happy path) | 20 min |
| TC-M2 (spectator) | 10 min |
| TC-M3 (reconnect during hand) | 10 min |
| TC-M4 (reconnect between hands) | 8 min |
| TC-M5 (background/foreground) | 8 min |
| TC-M6 (failed + retry) | 10 min |
| TC-M7 (no auto-reconnect on failed) | 8 min |
| TC-M8 (3 devices, full session) | 30 min |
| **Total** | **~1h 45min** |
