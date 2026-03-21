# Sign-off: private-playtest-readiness

**Feature:** private-playtest-readiness
**Date:** 2026-03-19
**Status:** APPROVED — ready for implementation

---

## Agent Sign-offs

All 5 agents reviewed the full artifact set (feature-spec.md, player-feedback.md, ux-spec.md, technical-design.md, qa-test-plan.md, task-breakdown.md).

---

### 1. Product Manager Agent

**Status:** APPROVED

**What is approved:**
- Feature goal: bridge from "playable in dev flow" to "usable for real internal playtest session"
- All 10 required flows (F-01 through F-10) defined and testable
- All 24 acceptance criteria numbered and concrete
- 16 failure states enumerated with required UI response and recovery action per state
- Instrumentation: console.log with `[Zepo:Namespace]` prefix format; no remote reporting this phase
- All 8 design questions resolved explicitly in feature-spec.md
- Definition of Done includes a dry-run session requirement

**What is deferred (explicitly out of scope):**
- Remote crash/error reporting (Sentry, Firebase Crashlytics, etc.)
- Real club list API (stub stays)
- Push notifications
- Persistent reconnect across full app kill/cold-start
- Club management / admin controls
- Automated E2E tests (Detox/Maestro)
- Animations, turn timer, chat, sound, side pot display

**PM Constraints for implementation:**
- Do not add instrumentation that makes network calls
- The `log()` utility must never throw; swallow JSON serialization errors
- Do not change the reconnect attempt count (stays at 3)
- Scope is internal playtest only — no public launch prep work

---

### 2. Poker Player Reviewer Agent

**Status:** APPROVED

**What is approved:**
- Four blockers identified and all addressed in scope: loading state on "Enter Table", retry button on connection failure, club join confirmation (empty state guidance), defined background/foreground behavior
- Trust moments addressed: action bar loading state improvements (joinPending overlay), reconnect confirmation ("Back online" banner), state restoration after reconnect via SYNC_REQUEST
- Session continuity: gameState cleared on disconnect prevents stale boards; SYNC_REQUEST sends on reconnect to confirm server state
- Hole card guard: existing guard unchanged, confirmed safe
- Hand result overlay between hands: HAND_STARTED clears handResult (existing) — confirmed correct

**Specific player concerns confirmed addressed:**
- "Enter Table" loading state: ✅ connecting spinner + "Connecting to table…"
- "Failed" state retry button: ✅ "Retry Connection" button in ConnectionBanner
- Club join confirmation: ✅ empty state with invite code input and guidance copy
- Background/foreground: ✅ auto-reconnect on foreground resume + "Back online" banner
- Post-reconnect state confirmation: ✅ SYNC_REQUEST after JOIN on reconnect

**What player review accepts as deferred:**
- Turn notification while backgrounded (push notifications)
- Action button send-confirmation loading state (server-authoritative; server ERROR covers double-tap)
- Verbal-only workaround for table info (friends can ask host until T-14 ships)
- Sit-out confirmation timeout UX (annoying but not blocking)

---

### 3. Senior UI/UX Designer Agent

**Status:** APPROVED

**What is approved:**
- All screen-by-screen changes specified with exact colors, font sizes, and conditions (ux-spec.md §1.1–§1.3)
- Full state machine for ConnectionBanner (5 states) and Table Screen (10 states) documented
- Exact copy for all new user-facing strings (ux-spec.md §7)
- Loading state hierarchy: full-screen spinner for club detail, inline spinner for table info, scroll-area overlay for WS connecting and join-pending
- Empty state: invite-code input + "Join Club" primary action + stubbed "Create Club" secondary action
- Table Config Card: 3 stat rows (blinds, stack, max players), styled consistently with existing `#1E293B` surface cards
- Retry button: positioned inside ConnectionBanner (not a separate modal), only visible on `failed` status
- Sit-in confirmation: local `sitInPending` state with "Sending request…" text and 5s timeout
- "Back online" copy (changed from "Reconnected")
- "Refreshing…" resync pill for foreground return

**UX constraints for implementation:**
- Do NOT add any animations or spring transitions
- Do NOT add a toast library — all feedback uses inline banners consistent with existing pattern
- Do NOT change the auth screens
- Do NOT change the existing hand gameplay UI components
- The `onRetry` prop on ConnectionBanner must be optional to preserve backward compatibility

**What is out of scope (§8 of ux-spec.md):**
18 explicit exclusions including circular seat layout, animations, chat, hand history, notifications, landscape layout, theme switching, SYNC_REQUEST manual tap button.

---

### 4. Senior Mobile Game Developer Agent

**Status:** APPROVED

**What is approved:**
- 21-task implementation plan (T-01 through T-21) in recommended execution order
- `joinPending: boolean` field in `tableStore.ts` — minimal, additive, does not break existing store contract
- `gameState: null` on `disconnect()` — correct fix for stale state; `handResult: null` included
- `sendSyncRequest()` action — one-line, clean, no store state required
- AppState handler fix: `failed` → no auto-connect; `connected` → send SYNC_REQUEST
- Logger utility: pure `console` wrapper, zero dependencies, zero overhead
- Error boundary: class component at `(app)` layout level — correct placement, correct recovery behavior
- `TableInfoCard` as a pure display component — accepts `TableConfigDTO`, no store access
- Connection is preserved: `SocketClient.ts` reconnect logic (backoff, attempts, shouldReconnect flag) is untouched

**Engineering constraints for implementation:**
- SocketClient internals must not change — instrumentation via `SocketLogger` calls only
- `SYNC_REQUEST` message type is already defined in `types.ts` — do NOT redefine
- Do NOT add any state to `tableStore` beyond what is in the task list
- `TableInfoCard` must NOT access any store directly
- `AppErrorBoundary` must use `componentDidCatch` for logging — not a hook
- `npx tsc --noEmit` must pass at every intermediate step

**What does not change per engineering review:**
- Backend contracts (no changes to WS schemas or REST endpoints)
- SocketClient reconnect logic
- Hand gameplay components (ActionBar, RaisePanel, HandResultOverlay, CommunityCards, MyHoleCards)
- Hole card guard
- Auth flow logic

---

### 5. Senior QA Reviewer Agent

**Status:** APPROVED

**What is approved:**
- 18 new unit/component tests (TC-35 through TC-52) covering all hardened behaviors
- 8 manual E2E scenarios (TC-M1 through TC-M8) covering all required flows
- Regression risk analysis: TC-24 and TC-14 (tableStore initial state) require updating; all other existing tests unaffected
- Pre-implementation gate: `npx tsc --noEmit` before running Jest when TableState interface changes
- Test runtime budget: ~89 total tests, ~10 seconds full suite
- Playtest readiness checklist: 12 code checks + 7 test checks + 7 manual checks + 3 operational checks
- Acceptance gate tests identified: TC-41 (gameState clear), TC-42 (SYNC_REQUEST), TC-48 (retry button) will FAIL against existing code — these are the correct gates

**QA constraints for implementation:**
- TC-24 must be updated (not deleted) to add `joinPending: false` assertion
- All new store tests must use the same SocketClient mock factory pattern as `tableStore.test.ts`
- Retry button must have `accessibilityLabel="Retry connection"` for TC-49 to work
- `npx jest --no-coverage` must be run after each task group (T-01–T-09, T-10–T-15, T-16–T-21)

---

## Summary of All Design Question Resolutions

| Question | Answer |
|----------|--------|
| Q1: Flows that must work | F-01 through F-10 (auth→club→table, play/spectator, reconnect, background, WS failure, API errors) |
| Q2: Failure states required | 16 failure states (FS1–FS16) enumerated in feature-spec.md §6 |
| Q3: Reconnect/resync behavior | Existing 3-attempt backoff kept; add Retry button on failed; SYNC_REQUEST on foreground+connected; no auto-reconnect from failed |
| Q4: Instrumentation | console.log with `[Zepo:Namespace]` prefix; 4 namespaces; log points at all lifecycle transitions |
| Q5: Background/foreground behavior | disconnected → auto-reconnect; failed → do nothing (user presses Retry); reconnecting → do nothing; connected → send SYNC_REQUEST |
| Q6: Manual recovery tools | "Retry Connection" button on failed state; auto SYNC_REQUEST on foreground resume; no in-table manual sync button |
| Q7: Deferred behaviors | Remote logging, real clubs API, push notifications, app-kill recovery, animations, turn timer, chat, Detox tests |
| Q8: Test scope budget | Min 18 new unit/component tests; full suite ≤30s; manual E2E ~1h 45min; no Detox tests this phase |

---

## What Must NOT Change During Implementation

1. SocketClient reconnect logic (backoff array `[1000, 2000, 4000]`, max 3 attempts, `shouldReconnect` flag)
2. All existing WebSocket message types and DTO shapes in `src/ws/types.ts`
3. All REST API endpoint contracts in `src/api/`
4. Hand gameplay components: ActionBar, RaisePanel, HandResultOverlay, CommunityCards, MyHoleCards, CardChip, HandInfoBar
5. Hole card guard in `TableScreen`
6. Auth flow screens (`/(auth)/login`, `/(auth)/verify`)
7. Existing test assertions TC-01 through TC-34 (except TC-24 which gets additional assertions, not replacement)
8. The 3-attempt reconnect maximum

---

## Go/No-Go

**Decision: GO**

All 5 agents approve. Implementation may begin with T-01 and proceed per the task breakdown. The feature is bounded, practical, and sufficient for a first internal private playtest build.

---

## Implementation Status

**Status:** COMPLETE — 2026-03-19

### Files Created
- `src/utils/logger.ts` — namespaced logger factory (T-01)
- `src/components/common/TableInfoCard.tsx` — pure display component for TableConfigDTO (T-11)
- `src/components/common/AppErrorBoundary.tsx` — class-based error boundary (T-12)
- `__tests__/tableStoreJoinPending.test.ts` — TC-35 through TC-40 (T-17)
- `__tests__/tableStoreDisconnectReset.test.ts` — TC-41 (T-18)
- `__tests__/tableStoreSyncRequest.test.ts` — TC-42 through TC-43 (T-19)
- `__tests__/ConnectionBanner.test.tsx` — TC-44 through TC-50 (T-20)
- `__tests__/TableInfoCard.test.tsx` — TC-51 through TC-52 (T-21)

### Files Modified
- `src/store/authStore.ts` — AuthLogger instrumentation (T-02)
- `src/store/clubStore.ts` — ClubLogger instrumentation (T-03)
- `src/ws/SocketClient.ts` — SocketLogger instrumentation (T-04)
- `src/store/tableStore.ts` — joinPending, sendSyncRequest, gameState clearing, AppState fix, TableLogger (T-05–T-09)
- `src/components/table/ConnectionBanner.tsx` — onRetry prop (T-10)
- `app/(app)/_layout.tsx` — AppErrorBoundary wrapper (T-13)
- `app/(app)/clubs/[clubId].tsx` — tableId param, TableInfoCard, error retry (T-14)
- `app/(app)/table/[tableId].tsx` — joinPending overlay, onRetry, sendSyncRequest in reconnect, "Back online" copy (T-15)
- `__tests__/tableStore.test.ts` — TC-24 updated with joinPending assertion, TC-20 updated with gameState assertion (T-16)

### Test Results
- **89/89 tests passing** (18 new + 71 prior)
- `npx tsc --noEmit` — 0 errors in source files (pre-existing test file tsc issues unchanged)
