# Technical Design: private-playtest-readiness

**Project:** Zepo Mobile (React Native / Expo SDK 52)
**Scope:** Hardening the auth → club → table entry → live table flow for private playtest
**Status:** Approved
**Date:** 2026-03-19

---

## 0. Executive Summary

Nine concrete gaps exist between the current codebase and a stable private playtest session. This document specifies exact changes needed to close each gap: store state additions, screen changes, a new logger utility, a new display component, an error boundary, and new unit tests. No new backend contracts are introduced. SocketClient reconnect logic is untouched. Existing hand gameplay and hole-card guard logic are untouched.

---

## 1. Architecture Changes

### 1.1 Store Changes

**`src/store/tableStore.ts`** — three targeted additions:

1. **`joinPending: boolean`** field — `true` from the moment `sendJoin` is called until the first `STATE_SNAPSHOT` is received. Cleared by `STATE_SNAPSHOT`, `disconnect()`, and `reset()`.
2. **`gameState` cleared on `disconnect()`** — currently preserved after disconnect, which can show a stale board when re-entering a table. Must be `null` after `disconnect()`.
3. **`sendSyncRequest()` action** — sends `SYNC_REQUEST` via `socketClient.send('SYNC_REQUEST')`. Called by the TableScreen reconnect effect after `sendJoin` succeeds.

**`src/store/clubStore.ts`** — no new state fields. Existing `isLoadingClub`, `isLoadingTable`, `error` fields are already correct. The gap is purely in how the screens use them.

**`src/store/authStore.ts`** — no state changes. Instrumentation calls only.

### 1.2 Screen Changes

**`app/(app)/clubs/[clubId].tsx`**
- Accept optional `tableId` route param alongside `clubId`.
- Call `fetchTableInfo(tableId)` on mount when `tableId` param is present.
- Render `LoadingSpinner` while `isLoadingClub === true`.
- Render `ErrorDisplay` + "Try again" button when `error` is non-null.
- Render `TableInfoCard` (new component) between invite code and "Enter table" button when `tableInfo !== null`.
- Show inline `ActivityIndicator` while `isLoadingTable === true`.

**`app/(app)/table/[tableId].tsx`**
- Consume `joinPending` from store — render "Joining table…" overlay when `joined && gameState === null && connectionStatus === 'connected'`.
- Pass `onRetry={() => connect(tableId!, token!)}` to `ConnectionBanner`.
- In the reconnect `useEffect`, call `sendSyncRequest()` after `sendJoin(joinedRole)`.

**`app/(app)/index.tsx`**
- No functional changes. Instrumentation log only.

### 1.3 Component Changes

**`src/components/table/ConnectionBanner.tsx`**
- Add optional `onRetry?: () => void` prop.
- When `status === 'failed'` and `onRetry` is defined, render "Retry Connection" `TouchableOpacity` inside the banner.
- Banner height increases to accommodate the button in the `failed` state.

### 1.4 New Components and Files

| File | Type | Purpose |
|------|------|---------|
| `src/utils/logger.ts` | New utility | Namespaced `console.log` wrapper; exports `AuthLogger`, `ClubLogger`, `TableLogger`, `SocketLogger` |
| `src/components/common/TableInfoCard.tsx` | New component | Display component for `TableConfigDTO` (blinds, stack, max players, timer) |
| `src/components/common/AppErrorBoundary.tsx` | New component | Class-based React Error Boundary wrapping the `(app)` layout |

---

## 2. clubStore Hardening

**Gap 1 — `fetchTableInfo` never called.** `ClubDTO` does not include `table_id`. Fix: the club detail screen accepts `tableId` as an optional route param and calls `fetchTableInfo(tableId)` on mount when present.

**Gap 2 — Error not rendered.** Replace inline error text with `ErrorDisplay` component plus retry `TouchableOpacity` that calls `clearError()` then `fetchClub(clubId)`.

**Gap 3 — `isLoadingTable` has no UI.** Add inline `ActivityIndicator` (color `#2563EB`, size `small`) conditional on `isLoadingTable`, rendered in the space where `TableInfoCard` will appear (96h placeholder to prevent layout jump).

No new store state fields needed.

---

## 3. tableStore Hardening

### 3.1 joinPending State

Add to `TableState` interface:
```typescript
joinPending: boolean;
```

- Initial value: `false`
- Set to `true` inside `sendJoin()`, before `socketClient.send('JOIN', { role })`
- Set to `false` inside `onMessage` handler when `envelope.type === 'STATE_SNAPSHOT'`
- Set to `false` inside `disconnect()` and `reset()`

### 3.2 gameState Clearing on Disconnect

Inside `disconnect()`, add to the `set()` call:
```typescript
disconnect: () => {
  savedTableId = null;
  savedToken = null;
  socketClient.disconnect();
  set({ gameState: null, handResult: null, joinPending: false });
},
```

`handResult` is also cleared to avoid showing a stale hand result overlay on re-entry.

### 3.3 sendSyncRequest Action

```typescript
sendSyncRequest: () => {
  socketClient.send('SYNC_REQUEST');
},
```

Called from `TableScreen` reconnect `useEffect` after `sendJoin` on successful reconnect.

### 3.4 AppState Handler — Failed State Behavior

**Current** (in `tableStore.ts`):
```typescript
if (connectionStatus === 'disconnected' || connectionStatus === 'failed') {
  socketClient.connect(savedTableId, savedToken);
}
```

**Change to:**
```typescript
if (connectionStatus === 'disconnected') {
  socketClient.connect(savedTableId, savedToken);
}
// When 'failed': do NOT auto-reconnect. User must press Retry.
```

**Also add** for SYNC_REQUEST on foreground when already connected:
```typescript
if (nextState === 'active' && connectionStatus === 'connected') {
  socketClient.send('SYNC_REQUEST');
}
```

---

## 4. ConnectionBanner Retry

**Updated props interface:**
```typescript
interface ConnectionBannerProps {
  status: ConnectionStatus;
  attempt: number;
  maxAttempts: number;
  onRetry?: () => void; // new optional prop
}
```

**Render change for `failed` case:**
```tsx
// In the failed branch, replace static text with:
<View style={styles.failedContainer}>
  <Text style={styles.failedText}>Connection failed</Text>
  <Text style={styles.failedSubtext}>Unable to reach the server after 3 attempts.</Text>
  {onRetry && (
    <TouchableOpacity
      style={styles.retryButton}
      onPress={onRetry}
      accessibilityLabel="Retry connection"
      accessibilityRole="button"
    >
      <Text style={styles.retryText}>Retry Connection</Text>
    </TouchableOpacity>
  )}
</View>
```

**Wiring in TableScreen:**
```typescript
const handleRetry = () => {
  if (tableId && token) connect(tableId, token);
};

// In JSX:
<ConnectionBanner
  status={connectionStatus}
  attempt={reconnectAttempt}
  maxAttempts={3}
  onRetry={connectionStatus === 'failed' ? handleRetry : undefined}
/>
```

The `connect` action resets `shouldReconnect = true` and `reconnectAttempt = 0` via `socketClient.connect`, so pressing Retry gives a clean reconnect cycle.

---

## 5. App Lifecycle — Foreground Resume Behavior

**Revised behavior matrix:**

| Status when app foregrounds | Action |
|-----------------------------|--------|
| `'disconnected'` | Store auto-reconnects (existing, kept) |
| `'failed'` | No auto-reconnect. User sees ConnectionBanner with Retry button. |
| `'reconnecting'` | No action. Banner shows progress. Reconnect loop continues. |
| `'connected'` | Send `SYNC_REQUEST` for fresh state. |

**Screen-level reconnect `useEffect` (in `TableScreen`):**

Extend the existing reconnect effect:
```typescript
useEffect(() => {
  const prev = prevStatusRef.current;
  prevStatusRef.current = connectionStatus;

  if (
    connectionStatus === 'connected' &&
    (prev === 'reconnecting' || prev === 'connecting') &&
    joinedRole !== null
  ) {
    sendJoin(joinedRole);       // existing
    sendSyncRequest();          // new
    setShowReconnectedBanner(true);
    const bannerTimer = setTimeout(() => setShowReconnectedBanner(false), 2000);
    return () => clearTimeout(bannerTimer);
  }
}, [connectionStatus]);
```

---

## 6. Instrumentation Plan

### 6.1 Logger Utility (`src/utils/logger.ts`)

```typescript
function makeLogger(namespace: string) {
  return {
    log: (...args: unknown[]) => console.log(`[Zepo:${namespace}]`, ...args),
    warn: (...args: unknown[]) => console.warn(`[Zepo:${namespace}]`, ...args),
    error: (...args: unknown[]) => console.error(`[Zepo:${namespace}]`, ...args),
  };
}

export const AuthLogger = makeLogger('AuthStore');
export const ClubLogger = makeLogger('ClubStore');
export const TableLogger = makeLogger('TableStore');
export const SocketLogger = makeLogger('SocketClient');
```

No third-party dependencies. No async I/O. Pure `console` wrapping.

### 6.2 Instrumentation Points

**`src/store/authStore.ts`**

| Event | Log call |
|-------|----------|
| `hydrate` start | `AuthLogger.log('hydrate: start')` |
| `hydrate` success with token | `AuthLogger.log('hydrate: restored session', userId)` |
| `hydrate` success without token | `AuthLogger.log('hydrate: no session found')` |
| `hydrate` catch | `AuthLogger.warn('hydrate: storage error', err)` |
| `login` | `AuthLogger.log('login: userId', userId)` |
| `logout` | `AuthLogger.log('logout')` |

**`src/store/clubStore.ts`**

| Event | Log call |
|-------|----------|
| `fetchClub` start | `ClubLogger.log('fetchClub: start', clubId)` |
| `fetchClub` success | `ClubLogger.log('fetchClub: success', club.name)` |
| `fetchClub` error | `ClubLogger.error('fetchClub: error', err)` |
| `fetchTableInfo` start | `ClubLogger.log('fetchTableInfo: start', tableId)` |
| `fetchTableInfo` success | `ClubLogger.log('fetchTableInfo: success', info.table_id)` |
| `fetchTableInfo` error | `ClubLogger.error('fetchTableInfo: error', err)` |

**`src/store/tableStore.ts`**

| Event | Log call |
|-------|----------|
| `connect` | `TableLogger.log('connect: tableId', tableId)` |
| `disconnect` | `TableLogger.log('disconnect: manual')` |
| `sendJoin` | `TableLogger.log('sendJoin: role', role)` |
| `STATE_SNAPSHOT` (joinPending cleared) | `TableLogger.log('joinPending cleared: STATE_SNAPSHOT received')` |
| `sendSyncRequest` | `TableLogger.log('sendSyncRequest: sent')` |
| `HAND_STARTED` | `TableLogger.log('HAND_STARTED received')` |
| `HAND_ENDED` | `TableLogger.log('HAND_ENDED hand#', payload.hand_number)` |
| `sendAction` | `TableLogger.log('sendAction:', type, amount ?? '')` |
| `ERROR` envelope | `TableLogger.error('server ERROR:', msg)` |
| `reset` | `TableLogger.log('reset')` |

**`src/ws/SocketClient.ts`**

| Event | Log call |
|-------|----------|
| `connect` | `SocketLogger.log('connect: tableId', tableId)` |
| `_openSocket` | `SocketLogger.log('opening socket, attempt:', attempt)` |
| `ws.onopen` | `SocketLogger.log('connected')` |
| `ws.onclose` + shouldReconnect | `SocketLogger.warn('closed, scheduling reconnect, attempt:', attempt)` |
| `ws.onclose` + !shouldReconnect | `SocketLogger.log('closed voluntarily')` |
| max attempts reached | `SocketLogger.error('max reconnect attempts reached — status: failed')` |
| `disconnect` | `SocketLogger.log('disconnect: manual')` |

---

## 7. Error Boundary

**Decision:** One React Error Boundary at the `(app)` layout level, wrapping all in-app screens.

New file: `src/components/common/AppErrorBoundary.tsx`

```typescript
// Class component (required by React error boundary API)
export default class AppErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string }
> {
  state = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error) {
    console.error('[Zepo:ErrorBoundary] caught:', error.message);
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>{this.state.message}</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => this.setState({ hasError: false, message: '' })}
          >
            <Text style={styles.buttonText}>Try again</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}
```

**Placement in `app/(app)/_layout.tsx`:**
```tsx
import AppErrorBoundary from '../../src/components/common/AppErrorBoundary';

export default function AppLayout() {
  return (
    <AppErrorBoundary>
      <Stack ... />
    </AppErrorBoundary>
  );
}
```

---

## 8. TableInfoCard Component

New file: `src/components/common/TableInfoCard.tsx`

Accepts `config: TableConfigDTO` and renders:
- Section label: "Table"
- "Blinds": `{small_blind} / {big_blind}`
- "Starting stack": `{starting_stack} chips`
- "Max players": `{max_players}`
- "Turn timer": `{turn_timer_seconds}s` (omitted if 0 or undefined)
- `house_rules` as comma-separated string (omitted if empty array)

Card style: `backgroundColor: '#1E293B'`, `borderRadius: 12`, `padding: 16`, `borderWidth: 1`, `borderColor: '#334155'`.

---

## 9. Module Boundaries — Complete Change List

### New Files

| File | Description |
|------|-------------|
| `src/utils/logger.ts` | Namespaced logger factory |
| `src/components/common/TableInfoCard.tsx` | Display component for `TableConfigDTO` |
| `src/components/common/AppErrorBoundary.tsx` | Class-based error boundary |
| `__tests__/tableStoreJoinPending.test.ts` | TC-35 through TC-40 |
| `__tests__/tableStoreDisconnectReset.test.ts` | TC-41 |
| `__tests__/tableStoreSyncRequest.test.ts` | TC-42 through TC-43 |
| `__tests__/ConnectionBanner.test.tsx` | TC-44 through TC-50 |
| `__tests__/TableInfoCard.test.tsx` | TC-51 through TC-52 |

### Modified Files

| File | Changes |
|------|---------|
| `src/store/tableStore.ts` | Add `joinPending`; set in `sendJoin`; clear in STATE_SNAPSHOT handler, `disconnect`, `reset`; add `sendSyncRequest`; clear `gameState`+`handResult` in `disconnect`; fix AppState handler (no auto-connect on `failed`; add SYNC_REQUEST on `connected`) |
| `src/store/authStore.ts` | Add `AuthLogger` calls |
| `src/store/clubStore.ts` | Add `ClubLogger` calls |
| `src/ws/SocketClient.ts` | Add `SocketLogger` calls |
| `src/components/table/ConnectionBanner.tsx` | Add `onRetry?: () => void` prop; render Retry button in `failed` case |
| `app/(app)/_layout.tsx` | Wrap `<Stack>` in `<AppErrorBoundary>` |
| `app/(app)/clubs/[clubId].tsx` | Accept `tableId` param; call `fetchTableInfo`; render `TableInfoCard`; fix error/loading UI |
| `app/(app)/table/[tableId].tsx` | Consume `joinPending`, `sendSyncRequest`; render join-pending overlay; pass `onRetry` to ConnectionBanner; extend reconnect effect |
| `__tests__/tableStore.test.ts` | Update TC-24 to assert `joinPending: false` and `gameState: null` after reset/disconnect |

---

## 10. Testing Strategy

### New Tests (min 17)

| File | TCs | Coverage |
|------|-----|----------|
| `tableStoreJoinPending.test.ts` | TC-35–TC-40 | joinPending state transitions |
| `tableStoreDisconnectReset.test.ts` | TC-41 | gameState/handResult null after disconnect |
| `tableStoreSyncRequest.test.ts` | TC-42–TC-43 | sendSyncRequest + no duplicate connect |
| `ConnectionBanner.test.tsx` | TC-44–TC-50 | All banner states + retry button visibility/callback |
| `TableInfoCard.test.tsx` | TC-51–TC-52 | Config values rendered; empty house_rules omitted |

All new store tests follow the existing SocketClient mock pattern from `tableStore.test.ts`.

---

## 11. What Does NOT Change

- **Backend contracts** — no changes to API endpoints, HTTP response shapes, or WS event schemas
- **SocketClient reconnect logic** — backoff array, max-3-attempts, `shouldReconnect` flag, `_scheduleReconnect` internals are untouched. Only instrumentation logs are added.
- **Hand gameplay** — `sendAction`, `sendSitIn`, `sendSitOut`, `ActionBar`, `RaisePanel`, `HandResultOverlay`, `CommunityCards`, `MyHoleCards` are untouched
- **Hole card guard** — the `(myPlayer?.hole_cards?.length ?? 0) > 0` guard in `TableScreen` is untouched
- **Auth flow** — login, verify, OTP logic unchanged; instrumentation is additive only
- **Club list screen** — `getUserClubs` stub stays; empty-state UI copy stays

---

## 12. Task List

| ID | File | Description | Type | Depends On |
|----|------|-------------|------|------------|
| T-01 | `src/utils/logger.ts` | Create namespaced logger factory; export 4 logger instances | New | — |
| T-02 | `src/store/authStore.ts` | Add `AuthLogger` calls to `hydrate`, `login`, `logout` | Modify | T-01 |
| T-03 | `src/store/clubStore.ts` | Add `ClubLogger` calls to `fetchClub`, `fetchTableInfo` | Modify | T-01 |
| T-04 | `src/ws/SocketClient.ts` | Add `SocketLogger` calls to connect/open/close/failed paths | Modify | T-01 |
| T-05 | `src/store/tableStore.ts` | Add `joinPending` field; set in `sendJoin`; clear in STATE_SNAPSHOT handler, `disconnect`, `reset` | Modify | — |
| T-06 | `src/store/tableStore.ts` | Add `sendSyncRequest` action | Modify | T-05 |
| T-07 | `src/store/tableStore.ts` | Clear `gameState` and `handResult` in `disconnect()` | Modify | T-05 |
| T-08 | `src/store/tableStore.ts` | Fix AppState handler: no auto-connect on `failed`; add SYNC_REQUEST on `connected` | Modify | T-05 |
| T-09 | `src/store/tableStore.ts` | Add `TableLogger` calls | Modify | T-01, T-05 |
| T-10 | `src/components/table/ConnectionBanner.tsx` | Add `onRetry` prop; render Retry button for `failed` status | Modify | — |
| T-11 | `src/components/common/TableInfoCard.tsx` | Create display component for `TableConfigDTO` | New | — |
| T-12 | `src/components/common/AppErrorBoundary.tsx` | Create class-based Error Boundary | New | — |
| T-13 | `app/(app)/_layout.tsx` | Wrap `<Stack>` with `<AppErrorBoundary>` | Modify | T-12 |
| T-14 | `app/(app)/clubs/[clubId].tsx` | Accept `tableId` param; call `fetchTableInfo`; render `TableInfoCard`, `LoadingSpinner`, `ErrorDisplay` | Modify | T-11, T-03 |
| T-15 | `app/(app)/table/[tableId].tsx` | Consume `joinPending` overlay; `onRetry` wiring; `sendSyncRequest` in reconnect effect | Modify | T-05, T-06, T-10 |
| T-16 | `__tests__/tableStore.test.ts` | Update TC-24 to assert `joinPending: false`, `gameState: null` | Modify | T-05, T-07 |
| T-17 | `__tests__/tableStoreJoinPending.test.ts` | TC-35 through TC-40 | New | T-05 |
| T-18 | `__tests__/tableStoreDisconnectReset.test.ts` | TC-41: gameState/handResult null after disconnect | New | T-07 |
| T-19 | `__tests__/tableStoreSyncRequest.test.ts` | TC-42–TC-43: sendSyncRequest sends, no duplicate connect | New | T-06, T-08 |
| T-20 | `__tests__/ConnectionBanner.test.tsx` | TC-44–TC-50: all banner states + retry | New | T-10 |
| T-21 | `__tests__/TableInfoCard.test.tsx` | TC-51–TC-52: TableInfoCard render | New | T-11 |

**Total: 21 tasks.** T-01 through T-09 are store/utility changes (no UI impact, merge first). T-10 through T-15 are UI changes. T-16 through T-21 are tests.
