# Sign-off — mobile-client-mvp-foundation

> Gate: Implementation Gate
> Status: APPROVED — READY FOR IMPLEMENTATION

---

## Feature Summary

Build the first real mobile client (React Native + Expo) that connects to the existing backend for MVP product flows: auth, clubs, table entry, and live WebSocket session with reconnect handling.

---

## PM Approval

- [x] Feature goal defined: mobile MVP foundation — auth, clubs, table entry, WS connection
- [x] 12 acceptance criteria defined (AC-01 through AC-12)
- [x] Scope tight: gameplay UI, chat, stats, notifications, monetization explicitly deferred
- [x] 5 screens defined (Login, VerifyOTP, ClubsList, ClubDetail, TableScreen)
- [x] Known backend gap documented: no `GET /clubs` endpoint (empty clubs list in MVP)
- [x] 5 risks documented with mitigations
- [x] All 8 design questions resolved
- Approved by: Product Manager Agent
- Date: 2026-03-19

---

## Player Feedback Approval

- [x] OTP login flow: correct and natural for friend-group use
- [x] Clubs as organizing unit: correct framing
- [x] Blinds + player count visible before joining: confirmed
- [x] Explicit player vs spectator choice: confirmed
- [x] Reconnect with banner (not kick): confirmed
- [x] Player list visible immediately after join: confirmed
- [x] Empty clubs list guidance text: **mandatory** — must not be blank
- [x] Role badge always visible on table screen: **mandatory**
- [x] Token bypass on restart: **mandatory** — returning users skip login
- Approved by: Poker Player Reviewer Agent
- Date: 2026-03-19
- Notes:
  - "Join by invite" and "Create club" from app are deferred — acceptable for dev/founder phase
  - SIT_OUT banner designed into table screen from day one (even with placeholder table UI)

---

## UX Approval

- [x] 5 screens defined with layout and states
- [x] Navigation structure: Auth group + App group (Expo Router file-based)
- [x] All loading, error, empty states defined per screen
- [x] Connection status banner spec: Connecting / Reconnecting (N/3) / Connection lost + retry
- [x] Role badge spec: Playing / Watching / Sitting Out
- [x] SIT_OUT state with "Tap to rejoin" inline banner
- [x] OTP display_name flow: conditional for new users
- [x] Minimum tap target: 44pt, safe area, keyboard behavior spec'd
- Approved by: Senior UI/UX Designer Agent
- Date: 2026-03-19
- Notes:
  - Dark mode deferred; system default only
  - No tab bar in MVP; pure stack navigation

---

## Technical Design Approval

- [x] Stack: Expo SDK 52 + React Native + Expo Router v3 + TypeScript — justified
- [x] State: Zustand slices (auth, club, table) — designed
- [x] HTTP: Axios with token interceptor + 401 handler
- [x] WS: Native WebSocket with exponential backoff (1s/2s/4s, 3 attempts)
- [x] Token persistence: AsyncStorage, hydrated on startup
- [x] Reconnect on foreground: AppState change listener in TableScreen
- [x] All backend DTOs typed in `src/api/types.ts` and `src/ws/types.ts`
- [x] SocketClient owns reconnect logic; tableStore owns game state
- [x] MVP-safe error handling: 4xx inline, 5xx toast, WS banner
- [x] 13 MVP-known gaps documented
- [x] Testing strategy: Jest unit tests for stores and SocketClient
- Approved by: Senior Mobile Game Developer Agent
- Date: 2026-03-19
- Notes:
  - `GET /clubs` endpoint does not exist; clubs list shows empty state + guidance in MVP
  - `crypto.randomUUID()` used for request_id — available in RN 0.76+

---

## QA Approval

- [x] 34 unit tests (TC-01 through TC-34) covering all stores and SocketClient
- [x] 10 manual E2E test scenarios (TC-M1 through TC-M10)
- [x] 10 failure cases documented
- [x] 5 edge cases, 4 race conditions documented
- [x] What this feature proves vs does not prove: explicit
- [x] Backend regression: 297/297 tests must pass — no backend changes
- [x] Mobile Jest: `npx jest` in `mobile/` must pass all new unit tests
- Approved by: Senior QA Reviewer Agent
- Date: 2026-03-19

---

## What Is Approved for Implementation

**Implement now:**
- T0: `mobile/` project scaffold (package.json, app.json, tsconfig, config)
- T1: Navigation shell and root layout (auth group + app group)
- T2: Auth screens + authStore + auth API client
- T3: Clubs screens + clubStore + clubs/tables API client
- T4: SocketClient + WS types
- T5: Table screen + tableStore
- T6: Common components (Button, LoadingSpinner, ErrorDisplay, ConnectionBanner, PlayerList, RoleBadge)
- T7: Unit tests (authStore, clubStore, tableStore, SocketClient)

**Must NOT change during implementation:**
- Any backend source file
- Any backend test file
- `tests/` directory contents
- `simulation/` directory contents

**Deferred:**
- Gameplay UI (cards, betting controls, pot display)
- Chat UI
- Player stats / leaderboard
- Create club from app
- Join club by invite code from app
- Settings screen
- Hand history viewer
- Push notifications
- Dark mode
- Animation polish

---

## Final Decision

- [x] **APPROVED — ready to implement**
- [x] **ALL GATES CLEARED — proceed with coding**
- [ ] **BLOCKED — do not implement**

Decision by: PM Agent + Player Reviewer Agent + UX Designer Agent + Senior Mobile Game Developer Agent + QA Reviewer Agent
Date: 2026-03-19

**GO — proceed with implementation.**

---

## Implementation Status

**COMPLETE — 2026-03-19**

All 8 task groups (T0–T7) implemented:

| Task | Files | Status |
|------|-------|--------|
| T0: Scaffold | package.json, app.json, tsconfig.json, babel.config.js, jest.config.js, jest.setup.js, src/config.ts | ✅ |
| T1: Navigation | app/_layout.tsx, app/+not-found.tsx, app/(auth)/_layout.tsx, app/(app)/_layout.tsx | ✅ |
| T2: Auth | app/(auth)/login.tsx, app/(auth)/verify.tsx, src/api/auth.ts, src/api/client.ts, src/api/types.ts, src/store/authStore.ts | ✅ |
| T3: Clubs | app/(app)/index.tsx, app/(app)/clubs/[clubId].tsx, src/api/clubs.ts, src/api/tables.ts, src/store/clubStore.ts | ✅ |
| T4: WebSocket | src/ws/types.ts, src/ws/SocketClient.ts | ✅ |
| T5: Table | app/(app)/table/[tableId].tsx, src/store/tableStore.ts | ✅ |
| T6: Components | src/components/common/Button.tsx, LoadingSpinner.tsx, ErrorDisplay.tsx, src/components/table/ConnectionBanner.tsx, PlayerList.tsx, RoleBadge.tsx | ✅ |
| T7: Tests | __tests__/authStore.test.ts (TC-01–07), __tests__/clubStore.test.ts (TC-08–13), __tests__/tableStore.test.ts (TC-14–24), __tests__/SocketClient.test.ts (TC-25–34) | ✅ |

**Mandatory items from player feedback — all implemented:**
- Empty clubs list guidance text: ✅ (index.tsx shows "Ask a club owner to share their invite code…")
- Role badge always visible: ✅ (RoleBadge always renders on TableScreen header and PlayerList)
- Token bypass on restart: ✅ (authStore.hydrate() reads AsyncStorage before navigation decision)

**Test results: 34/34 mobile unit tests pass (`node node_modules/jest/bin/jest.js` in `mobile/`).**

**Backend regression: 0 backend files modified.**
