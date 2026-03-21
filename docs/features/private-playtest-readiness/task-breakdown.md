# Task Breakdown: private-playtest-readiness

**Date:** 2026-03-19
**Total tasks:** 21 (T-01 through T-21)
**Execution order:** T-01 first (logger utility), then T-02–T-09 (store/infra), then T-10–T-15 (UI), then T-16–T-21 (tests).

---

## Implementation Tasks

| ID | File | Description | Type | Depends On |
|----|------|-------------|------|------------|
| T-01 | `src/utils/logger.ts` | Create namespaced logger factory (`makeLogger`); export `AuthLogger`, `ClubLogger`, `TableLogger`, `SocketLogger` | New | — |
| T-02 | `src/store/authStore.ts` | Add `AuthLogger` calls to `hydrate` (start/success/no-session/error), `login`, `logout` | Modify | T-01 |
| T-03 | `src/store/clubStore.ts` | Add `ClubLogger` calls to `fetchClub` and `fetchTableInfo` (start/success/error) | Modify | T-01 |
| T-04 | `src/ws/SocketClient.ts` | Add `SocketLogger` calls to `connect`, `_openSocket`, `onopen`, `onclose` (reconnect/voluntary), max-attempts-reached, `disconnect` | Modify | T-01 |
| T-05 | `src/store/tableStore.ts` | Add `joinPending: boolean` field to `TableState`; set `true` in `sendJoin`; clear `false` in `STATE_SNAPSHOT` handler, `disconnect()`, `reset()` | Modify | — |
| T-06 | `src/store/tableStore.ts` | Add `sendSyncRequest()` action that calls `socketClient.send('SYNC_REQUEST')` | Modify | T-05 |
| T-07 | `src/store/tableStore.ts` | Clear `gameState: null` and `handResult: null` in `disconnect()` | Modify | T-05 |
| T-08 | `src/store/tableStore.ts` | Fix AppState handler: remove auto-connect on `failed`; add `socketClient.send('SYNC_REQUEST')` when `status === 'connected'` on foreground resume | Modify | T-05 |
| T-09 | `src/store/tableStore.ts` | Add `TableLogger` calls: connect, disconnect, sendJoin, STATE_SNAPSHOT, sendSyncRequest, HAND_STARTED, HAND_ENDED, sendAction, ERROR, reset | Modify | T-01, T-05 |
| T-10 | `src/components/table/ConnectionBanner.tsx` | Add `onRetry?: () => void` prop; render "Retry Connection" `TouchableOpacity` (`accessibilityLabel="Retry connection"`) in `failed` case when prop defined | Modify | — |
| T-11 | `src/components/common/TableInfoCard.tsx` | Create display component accepting `config: TableConfigDTO`; renders blinds, starting stack, max players, turn timer; omits empty house_rules | New | — |
| T-12 | `src/components/common/AppErrorBoundary.tsx` | Create class-based React Error Boundary with `getDerivedStateFromError`, `componentDidCatch` (console.error), and fallback UI with "Try again" reset button | New | — |
| T-13 | `app/(app)/_layout.tsx` | Import `AppErrorBoundary`; wrap `<Stack>` in `<AppErrorBoundary>` | Modify | T-12 |
| T-14 | `app/(app)/clubs/[clubId].tsx` | Accept optional `tableId` route param; call `fetchTableInfo(tableId)` on mount when present; render `LoadingSpinner` while `isLoadingClub`; render `ErrorDisplay` + retry button on `error`; render `TableInfoCard` when `tableInfo !== null`; show inline `ActivityIndicator` while `isLoadingTable` | Modify | T-11, T-03 |
| T-15 | `app/(app)/table/[tableId].tsx` | Destructure `joinPending`, `sendSyncRequest` from `useTableStore`; render "Joining table…" overlay when `joined && gameState === null && connectionStatus === 'connected'`; pass `onRetry` to `ConnectionBanner`; call `sendSyncRequest()` after `sendJoin(joinedRole)` in reconnect `useEffect`; update reconnected banner copy to "Back online" | Modify | T-05, T-06, T-10 |
| T-16 | `__tests__/tableStore.test.ts` | Update TC-24 (reset assertion) to include `joinPending: false`; update TC-20 (disconnect assertion) to include `gameState: null` | Modify | T-05, T-07 |
| T-17 | `__tests__/tableStoreJoinPending.test.ts` | Write TC-35 through TC-40: joinPending initial state, set by sendJoin (player), set by sendJoin (watcher), cleared by STATE_SNAPSHOT, cleared by disconnect, cleared by reset | New | T-05 |
| T-18 | `__tests__/tableStoreDisconnectReset.test.ts` | Write TC-41: gameState is null after STATE_SNAPSHOT then disconnect | New | T-07 |
| T-19 | `__tests__/tableStoreSyncRequest.test.ts` | Write TC-42: SYNC_REQUEST sent on foreground resume when connected; TC-43: no duplicate connect call | New | T-06, T-08 |
| T-20 | `__tests__/ConnectionBanner.test.tsx` | Write TC-44 through TC-50: connected=null, connecting=text, reconnecting=attempt-count, failed=error-text, failed=retry-button-visible, retry-calls-onRetry, reconnecting=no-retry-button | New | T-10 |
| T-21 | `__tests__/TableInfoCard.test.tsx` | Write TC-51: renders blinds/stack/max-players; TC-52: omits house_rules when empty | New | T-11 |

---

## Detailed Notes per Task

### T-01 — Logger utility
```typescript
// src/utils/logger.ts
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

### T-05 — joinPending state
- Add to `TableState` interface: `joinPending: boolean`
- Add to initial state object in `create()`: `joinPending: false`
- In `sendJoin`: `set({ joinPending: true })` before `socketClient.send('JOIN', { role })`
- In `onMessage` STATE_SNAPSHOT branch: `set({ gameState: ..., joinPending: false })`
- In `disconnect()`: include `joinPending: false` in the `set()` call
- In `reset()`: include `joinPending: false` in the `set()` call

### T-07 — gameState clearing
- In `disconnect()`, change the `set()` call to include `gameState: null, handResult: null, joinPending: false`
- Do NOT clear `connectionStatus` — that transitions naturally via the SocketClient status listener

### T-08 — AppState handler fix
- Find the AppState `active` branch in `tableStore.ts`
- Change `if (connectionStatus === 'disconnected' || connectionStatus === 'failed')` to `if (connectionStatus === 'disconnected')`
- Add new `else if (nextState === 'active' && connectionStatus === 'connected') { socketClient.send('SYNC_REQUEST'); }`

### T-10 — ConnectionBanner retry
- Interface change: `onRetry?: () => void` is optional, so no breaking change
- In the `failed` status branch, wrap text in a `View` (column layout) and conditionally render the button
- Button styles: `#EF4444` background, white text, `borderRadius: 8`, `paddingVertical: 8`, `paddingHorizontal: 20`, `alignSelf: 'center'`, `marginTop: 10`

### T-14 — Club detail screen
- `useLocalSearchParams<{ clubId: string; tableId?: string }>`
- Add `useEffect` after `selectedClub` loads: if `tableId` param present, call `fetchTableInfo(tableId)`
- Render condition for `TableInfoCard`: `{tableInfo && <TableInfoCard config={tableInfo.config} />}`
- Render condition for loading table info: `{isLoadingTable && <ActivityIndicator ... />}` in a 96-height placeholder

### T-15 — TableScreen additions
- Destructure from `useTableStore`: `const { ..., joinPending, sendSyncRequest } = useTableStore()`
- Join-pending render condition: `{joined && gameState === null && connectionStatus === 'connected' && (<View style={styles.center}><ActivityIndicator ... /><Text style={styles.muted}>Joining table…</Text></View>)}`
- Reconnect effect: add `sendSyncRequest()` call after `sendJoin(joinedRole)`
- Change reconnected banner text: `'Back online'` instead of `'Reconnected'`

---

## Acceptance Gate

Before marking implementation complete:
1. `npx jest --no-coverage` — all tests pass (target: 89+ total)
2. `npx tsc --noEmit` — no TypeScript errors
3. Manual TC-M1 (happy path) and TC-M6 (retry button) verified on device/simulator
