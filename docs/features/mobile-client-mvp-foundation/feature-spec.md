# Feature Spec — mobile-client-mvp-foundation

> Agent: Product Manager
> Date: 2026-03-19

---

## Feature Goal

Build the first real mobile client foundation so the product has a working app that connects to the existing backend. This is not a polished product. It is the foundational layer: auth, clubs, table entry, and a live WebSocket connection.

After this feature the product moves from "backend is ready and testable via simulation" to "a real app exists that a developer or founder can install on a phone and use with the live backend."

---

## Problem Statement

The backend is production-ready:
- Auth (OTP + token) is working
- Club and table management is working
- WebSocket realtime session is working with full reconnect behavior
- Persistence layer (SQLite) is working

There is no client. No one can actually use the product. This feature changes that.

---

## Scope

### In Scope

1. **App foundation** — Expo + React Native project, TypeScript, file-based routing, buildable on iOS and Android
2. **Auth flow** — phone number entry → OTP → token stored in device storage → used for all subsequent requests
3. **Clubs list** — authenticated home screen showing clubs the user belongs to; empty state; create club action
4. **Club detail** — name, member count, invite code visible to admin; entry point to the table
5. **Table entry flow** — load table config, show current player count, offer "Join as Player" or "Watch as Spectator" CTA
6. **Table screen** — placeholder game area + live WebSocket connected + STATE_SNAPSHOT received + players list visible + own status visible; NOT a full gameplay UI
7. **WebSocket client** — connect, send JOIN_TABLE, handle incoming events, auto-reconnect on disconnect
8. **Error / reconnect UX** — connection lost banner, reconnect in progress state, connection restored state
9. **State management** — auth state, clubs state, table/game state (from STATE_SNAPSHOT)
10. **API client** — typed HTTP client for all existing backend endpoints

### Out of Scope

- Actual gameplay UI (cards, betting controls, pot display, action buttons)
- Chat
- Player stats / leaderboard
- Admin tools (config editing, member management)
- Push notifications
- Voice/video
- Tournament system
- Animation polish, custom fonts, branded design system
- Monetization, in-app purchases
- Settings screen (deferred)
- Hand history viewer (deferred)
- Join club by invite code UI (deferred — text-based invite sharing is acceptable for MVP)
- Create club from app (the API exists; deferred from MVP foundation scope)

---

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | App installs and launches with `npx expo start` on both iOS simulator and Android emulator |
| AC-02 | Auth flow: phone number → OTP code → token stored → user lands on clubs list |
| AC-03 | Clubs list screen: shows all clubs for the current user; shows empty state if none |
| AC-04 | Club detail screen: shows club name, member count, and table entry CTA |
| AC-05 | Table screen: loads table config via HTTP before joining; shows blinds, max players |
| AC-06 | Table entry: "Join as Player" sends JOIN_TABLE{role:player}; "Watch" sends JOIN_TABLE{role:spectator} |
| AC-07 | WebSocket connects with token; disconnects cleanly on screen exit |
| AC-08 | STATE_SNAPSHOT received → players list rendered in table screen |
| AC-09 | Connection lost → banner shown → automatic reconnect attempt → success/failure feedback |
| AC-10 | Token persisted across app restarts; user bypasses login if token is valid |
| AC-11 | All API errors shown as human-readable messages (not raw error codes) |
| AC-12 | `npx jest` in the `mobile/` directory runs and passes for store + client unit tests |

---

## Dependencies

- `backend/api/auth_router.py` — `POST /auth/request-otp`, `POST /auth/verify-otp`
- `backend/api/clubs_router.py` — `POST /clubs`, `GET /clubs/{club_id}`, `POST /clubs/{club_id}/join`
- `backend/api/tables_router.py` — `GET /clubs/{club_id}/table`
- `backend/realtime/ws_router.py` — `WS /ws/table/{table_id}?token={token}`
- `backend/realtime/schemas.py` — all message type contracts

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| WebSocket reconnect race on mobile (background/foreground) | High | Implement reconnect with backoff; cancel on unmount |
| Token expiry not handled | Medium | Decode token expiry; redirect to login on 401 |
| Backend URL hardcoded in dev build | Low | Use `mobile/src/config.ts` with env-based URL |
| Expo Router navigation edge cases | Low | Limit nav depth; test all screen transitions |
| Jest test environment issues with Zustand | Low | Use `zustand/middleware` and reset stores in test teardown |

---

## Open Questions — Resolved

| # | Question | Answer |
|---|----------|--------|
| 1 | What mobile stack? | Expo SDK 52 + React Native + Expo Router v3 + TypeScript |
| 2 | What screens in MVP? | Login, VerifyOTP, ClubsList, ClubDetail, TableScreen (5 screens) |
| 3 | Navigation structure? | Stack: Auth group (unauthenticated) + App group (authenticated) |
| 4 | How does auth work? | OTP → bearer token → AsyncStorage → injected into API/WS headers |
| 5 | Player vs spectator? | Explicit choice presented on Table entry screen |
| 6 | Min table info before joining? | Blinds, max players, current player count, phase |
| 7 | Reconnect behavior? | Automatic reconnect with exponential backoff (3 attempts), then manual retry |
| 8 | What is deferred? | Gameplay UI, chat, stats, create club, join by invite, settings |
