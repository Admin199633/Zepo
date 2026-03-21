# Feature Spec: private-playtest-readiness

**Feature:** private-playtest-readiness
**Date:** 2026-03-19
**Status:** Draft → Pending Signoff
**Author:** Product Manager Agent

---

## Feature Goal

Move the current mobile + backend system from "playable in a controlled dev flow" to "usable in a real internal private playtest session."

A private playtest means: a small group of internal testers (5–8 people) installs the app, scans an invite code, enters a table, plays multiple Texas Hold'em hands, encounters common interruptions (network glitch, app backgrounded), and can report meaningful product issues.

**Not** a public launch. **Not** a QA regression gate. A real first-session confidence gate.

---

## Scope

### Included

1. **Flow hardening** — auth → club → table entry as a reliable path
2. **Loading states** — club detail fetch, table WS connecting, join-in-progress
3. **Empty states** — club list (no clubs yet), waiting for hand to start
4. **Failure states** — WS permanently failed, API errors on club/table fetch
5. **Retry mechanism** — "Retry Connection" button on WS failed state
6. **Table config display** — show blinds, stack size, max players on club detail before entering
7. **Manual resync** — send SYNC_REQUEST after foreground resume when WS is already connected
8. **App lifecycle** — foreground/background transitions do not silently break the session
9. **tableStore reset** — gameState cleared on disconnect to prevent stale UI
10. **joinPending state** — visual feedback between role selection and first STATE_SNAPSHOT
11. **Instrumentation** — lightweight console.log at key lifecycle points for tester bug reports
12. **Error display** — consistent API error display on club/table screens
13. **New unit tests** — cover all hardened behaviors

### Out of Scope

- Circular seat layout or animated card dealing
- Actor turn timer
- Chat UI
- Sound effects
- Multi-pot / side pot breakdown UI
- Pull-to-refresh on clubs list (no real API for clubs list yet)
- Real club list API (stub stays empty — testers will deep-link directly to club URL)
- Automated E2E tests (Detox/Maestro)
- Push notifications
- Landscape / tablet layout
- Tournament mode or buy-in flow
- Admin / moderation controls
- Any backend changes

---

## Required End-to-End Flows

For a private playtest to be considered viable, every one of these flows must work reliably:

| Flow ID | Flow | Must Work |
|---------|------|-----------|
| F-01 | Open app → already logged in → club detail → enter table | Yes |
| F-02 | Open app → not logged in → login → OTP → club detail → enter table | Yes |
| F-03 | Enter table → choose Play → play multiple consecutive hands | Yes |
| F-04 | Enter table → choose Watch → observe full hand without action controls | Yes |
| F-05 | Network drop during hand → auto-reconnect → game state restored | Yes |
| F-06 | Network drop between hands → auto-reconnect → next hand starts normally | Yes |
| F-07 | App backgrounded during hand → foreground → state current and correct | Yes |
| F-08 | WS permanently fails (3 retries exhausted) → clear error state → retry button works | Yes |
| F-09 | API error on club fetch → error message shown → user can retry (navigate back/retry) | Yes |
| F-10 | Multiple players (2–4) on same table, same session, ~30 minutes | Yes |

---

## Acceptance Criteria

All criteria must be satisfied before this feature is considered complete:

**Loading States**
1. Club detail screen shows a `LoadingSpinner` while `isLoadingClub = true`. No blank flash.
2. Club detail screen shows an `ErrorDisplay` when `clubStore.error` is non-null.
3. Table screen shows a "Connecting…" loading state between "Enter Table" press and WS `connected`.
4. After role selection (Play/Watch), a "Joining…" indicator is visible until the first `STATE_SNAPSHOT` is received.

**Table Config Display**
5. Club detail screen shows table configuration: small blind, big blind, starting stack, max players.
6. Table config data is fetched via the existing `GET /tables/{tableId}` endpoint using `tableStore.fetchTableInfo`.

**WS Failure & Retry**
7. When `connectionStatus === 'failed'`, a "Retry Connection" button is visible in the table screen (or within the ConnectionBanner).
8. Pressing "Retry Connection" calls `tableStore.connect(tableId, token)` with the preserved tableId and token.
9. After retry, the reconnect attempt counter resets and the WS attempts to reconnect from scratch.

**State Reset**
10. `gameState` is set to `null` when `disconnect()` is called — no stale game state visible after leaving a table.
11. `joinPending` is set to `false` when `disconnect()` is called or when `STATE_SNAPSHOT` is received.

**joinPending State**
12. `tableStore` has a `joinPending: boolean` field, initially `false`.
13. `sendJoin()` sets `joinPending = true`.
14. Receiving a `STATE_SNAPSHOT` sets `joinPending = false`.
15. The table screen renders a joining indicator when `joinPending === true`.

**App Lifecycle**
16. When app returns to foreground and `connectionStatus === 'connected'`, a `SYNC_REQUEST` is sent within 1 second.
17. When app returns to foreground and `connectionStatus === 'failed'`, no auto-reconnect fires — user must press Retry.
18. When app returns to foreground and `connectionStatus === 'reconnecting'`, the reconnect is allowed to continue — no duplicate attempt started.

**Instrumentation**
19. Console log emitted on WS connect, disconnect, reconnect attempt, reconnect success, reconnect fail.
20. Console log emitted on JOIN sent, STATE_SNAPSHOT received, HAND_ENDED received.
21. Console log emitted on auth login, auth hydration result, auth logout.
22. All logs use the prefix format `[Zepo:StoreName]` for easy filtering.

**Regression**
23. All 71 existing tests continue passing after implementation.
24. All new tests pass (minimum 15 new unit/component tests).

---

## Failure States Required

Every failure state below must have a visible, actionable UI response:

| Failure | Current State | Required State |
|---------|--------------|----------------|
| WS `failed` (3 retries exhausted) | ConnectionBanner shows "Failed" text | "Failed" banner + "Retry Connection" button |
| WS `disconnected` (voluntary) | ConnectionBanner shows "Disconnected" | Same; user can navigate back |
| Club fetch API error | `clubStore.error` set, not rendered | ErrorDisplay shown on club detail screen |
| Table fetch API error | `clubStore.error` set, not rendered | ErrorDisplay shown on club detail screen |
| WS connecting timeout | No loading indicator | "Connecting…" spinner on table screen |
| Join action dropped (WS not open) | Silent | Not applicable for MVP — server sends ERROR envelope |

---

## Minimum Instrumentation Required

Instrumentation is console.log only — no analytics service, no Sentry, no crash reporting in this phase.

**Purpose:** Allow internal testers to share a screenshot or copy-paste of the console log so developers can understand what happened.

**Required log points:**

| Store/Module | Event | Log message format |
|--------------|-------|-------------------|
| authStore | hydration complete | `[Zepo:AuthStore] hydrated userId={userId} authenticated={bool}` |
| authStore | login | `[Zepo:AuthStore] login userId={userId}` |
| authStore | logout | `[Zepo:AuthStore] logout` |
| clubStore | fetchClub start | `[Zepo:ClubStore] fetchClub clubId={id}` |
| clubStore | fetchClub error | `[Zepo:ClubStore] fetchClub error: {message}` |
| tableStore | connect | `[Zepo:TableStore] connect tableId={id}` |
| tableStore | status change | `[Zepo:TableStore] status {prev} → {next} attempt={n}` |
| tableStore | sendJoin | `[Zepo:TableStore] sendJoin role={role}` |
| tableStore | STATE_SNAPSHOT | `[Zepo:TableStore] STATE_SNAPSHOT players={n} hand={handId|null}` |
| tableStore | HAND_ENDED | `[Zepo:TableStore] HAND_ENDED hand={n} winners={ids}` |
| tableStore | SYNC_REQUEST | `[Zepo:TableStore] SYNC_REQUEST sent (foreground resume)` |
| tableStore | error | `[Zepo:TableStore] error: {message}` |

---

## Dependencies

- Backend WebSocket gateway — no changes required; all new behavior is client-side
- `GET /tables/{tableId}` — already exists, returns `TableInfoDTO` with `config` (blinds, stack, max_players)
- `GET /clubs/{clubId}` — already exists, returns `ClubDTO`
- `SYNC_REQUEST` client message type — already defined in `types.ts`, server already handles it

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| SYNC_REQUEST not implemented on server | Medium | Test against real server before playtest; if not supported, server sends STATE_SNAPSHOT naturally after reconnect anyway |
| Native slider not working in Expo Go | Low | Already resolved — @react-native-community/slider installed |
| tableStore.connect() called twice if user presses Retry during reconnecting | Medium | Disable Retry button when status !== 'failed' |
| Stale gameState showing after table exit and re-entry | High without fix | Fixed by clearing gameState on disconnect() |
| joinPending never cleared if server sends ERROR before STATE_SNAPSHOT | Low | Clear joinPending on ERROR envelope too |
| Console logs create performance overhead | Very Low | console.log is negligible for internal playtest sessions |

---

## Open Questions Resolved

**Q1: What exact flows must work for a private internal playtest?**
Flows F-01 through F-10 listed above. Most critical: auth→club→table (F-01/F-02), play multiple hands (F-03), reconnect during hand (F-05), WS failed retry (F-08).

**Q2: What exact failure states must be handled in this phase?**
WS failed with retry, WS disconnected (visible banner), API errors on club/table fetch with error display. Silent failures are not acceptable.

**Q3: What reconnect/resync behavior is required for playtest readiness?**
Existing 3-attempt exponential backoff remains. Add: (a) Retry button on 'failed' state, (b) SYNC_REQUEST on foreground resume when already connected, (c) no auto-reconnect on foreground resume from 'failed' state.

**Q4: What minimal instrumentation is required so testers can report useful issues?**
Console.log at all lifecycle events listed in the instrumentation table above. Format includes component, event, and key identifiers. Testers can share Metro/Expo console output or screenshots.

**Q5: How should background/foreground transitions behave in this phase?**
- `connected` + foreground: send SYNC_REQUEST
- `reconnecting` + foreground: do nothing (let current retry complete)
- `failed` + foreground: do nothing (user presses Retry)
- `disconnected` + foreground: do nothing (session ended)

**Q6: What manual recovery tools, if any, are included now?**
One: "Retry Connection" button on WS 'failed' state. No pull-to-refresh on clubs list (no real API). No in-table manual refresh button (SYNC_REQUEST is automatic on foreground resume).

**Q7: What important playtest-readiness behaviors are explicitly deferred?**
Detox/Maestro E2E automation, real club list API, animated transitions, turn timer, chat, sound, landscape layout, side pot display, crash reporting service.

**Q8: What is the acceptable runtime/scope budget for tests in this phase?**
Minimum 15 new unit/component tests. Full suite must complete in under 30 seconds. No Detox tests in this phase. All tests must be deterministic.

---

## Definition of Done

- All 10 required flows (F-01 through F-10) demonstrably work on a device or simulator
- All 24 acceptance criteria satisfied
- All 71 existing tests still pass
- Minimum 15 new tests pass
- Instrumentation logs visible in Metro console during a test session
- Table config (blinds/stack) visible on club detail before entering
- Retry button functional on WS 'failed' state
- No stale game state visible after table exit
