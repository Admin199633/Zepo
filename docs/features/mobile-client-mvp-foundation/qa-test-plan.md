# QA Test Plan — mobile-client-mvp-foundation

> Agent: Senior QA Reviewer
> Date: 2026-03-19

---

## Regression Baseline

Backend: **297/297 tests must continue passing** after this feature. No backend files may be modified.

Mobile: `npx jest` in `mobile/` must pass all unit tests added in this feature.

---

## Unit Tests (Jest — `mobile/__tests__/`)

### Auth Store Tests — `authStore.test.ts`

| TC | Description | Assert |
|----|-------------|--------|
| TC-01 | Initial state: token=null, userId=null, isHydrated=false | Store initial values match |
| TC-02 | `login(token, userId)` stores values in state and AsyncStorage | State updated; AsyncStorage.setItem called with correct key |
| TC-03 | `logout()` clears token and userId from state and AsyncStorage | State null; AsyncStorage.removeItem called |
| TC-04 | `hydrate()` reads token from AsyncStorage and populates state | State populated; isHydrated=true |
| TC-05 | `hydrate()` with no stored token: state remains null, isHydrated=true | No error; correct null state |
| TC-06 | After `login()`, `hydrate()` restores token correctly | Simulated restart: hydrate reads what login stored |
| TC-07 | `logout()` after `login()` leaves state clean | State is null after logout |

### Club Store Tests — `clubStore.test.ts`

| TC | Description | Assert |
|----|-------------|--------|
| TC-08 | `fetchClub(clubId)` success: state.selectedClub populated, status='idle' | Club data in state |
| TC-09 | `fetchClub(clubId)` loading state: status='loading' during request | status='loading' before response |
| TC-10 | `fetchClub(clubId)` error: status='error', error message set | Correct error string |
| TC-11 | `fetchTableInfo(clubId)` success: tableInfo populated | TableInfoDTO in state |
| TC-12 | `fetchTableInfo(clubId)` error: error message set | Error handled |
| TC-13 | Store resets correctly between fetches | No stale data from previous call |

### Table Store Tests — `tableStore.test.ts`

| TC | Description | Assert |
|----|-------------|--------|
| TC-14 | `connect()` → SocketClient.connect called with correct url+token | connect called correctly |
| TC-15 | STATE_SNAPSHOT received → gameState populated in store | gameState has players, phase |
| TC-16 | PLAYER_STATUS event received → gameState.players updated | Player status updated in place |
| TC-17 | PLAYER_JOINED event received → new player added to gameState.players | New player in players dict |
| TC-18 | PLAYER_LEFT event received → player removed from gameState.players | Player removed |
| TC-19 | `disconnect()` → SocketClient.disconnect called, connectionStatus='disconnected' | Correct state after disconnect |
| TC-20 | `reset()` → all table state cleared | gameState=null, status='disconnected' |
| TC-21 | connectionStatus transitions: disconnected → connecting → connected | Correct sequence on connect |
| TC-22 | connectionStatus on WS close: 'reconnecting' (attempt 1 of 3) | Status='reconnecting', attempt=1 |
| TC-23 | After 3 failed reconnects: status='failed' | status='failed' |
| TC-24 | myRole set on connect() call | role stored correctly |

### SocketClient Tests — `SocketClient.test.ts`

| TC | Description | Assert |
|----|-------------|--------|
| TC-25 | `connect()` creates WebSocket with correct URL | WS constructor called with correct URL |
| TC-26 | `send()` serializes ClientEnvelope and calls ws.send | ws.send called with correct JSON |
| TC-27 | `send()` before connected: message queued or no-op | No error thrown |
| TC-28 | `onmessage` fires → onMessage callback called with parsed envelope | Callback called with ServerEnvelope |
| TC-29 | `onmessage` with invalid JSON: no crash, message ignored | No uncaught exception |
| TC-30 | `onclose` fires → shouldReconnect=true → reconnect scheduled | Timer set |
| TC-31 | `disconnect()` sets shouldReconnect=false → onclose does not schedule reconnect | No timer after explicit disconnect |
| TC-32 | Reconnect backoff: attempt 1=1s, attempt 2=2s, attempt 3=4s | setTimeout called with correct delays |
| TC-33 | After 3 failed reconnects: onStatusChange('failed') called | Callback called with 'failed' |
| TC-34 | On reconnect success: reconnectAttempts reset to 0 | Attempts counter reset |

---

## Manual / E2E Test Scenarios

These require the backend running locally (`uvicorn backend.main:app`).

### TC-M1: Full auth flow — new user

1. Launch app → Login screen appears
2. Enter valid phone → tap "Send Code"
3. Enter correct OTP → enter display name → tap Verify
4. Clubs list appears (empty state: guidance text visible)
5. Restart app → Clubs list appears immediately (no login screen)

**Assert**: Token stored; returning user bypasses login.

---

### TC-M2: Full auth flow — invalid OTP

1. Enter phone → "Send Code"
2. Enter wrong code → "Invalid code" error appears inline
3. Correct the code → success

---

### TC-M3: Clubs list — member flow

**Precondition**: club created via backend, user is a member.

1. Login → clubs list shows club row
2. Tap club → club detail screen with name, member count, table info
3. Tap "Go to Table" → role choice modal appears

---

### TC-M4: Table entry — join as player

1. Navigate to table → role choice modal → tap "Join as Player"
2. WS connects → "Connecting..." banner appears briefly
3. JOIN_TABLE{role:player} sent → STATE_SNAPSHOT received
4. Player list populates; own status visible; role badge shows "Playing"
5. Leave table → WS closes

---

### TC-M5: Table entry — join as spectator

1. Navigate to table → role choice modal → tap "Watch as Spectator"
2. WS connects, JOIN_TABLE{role:spectator} sent
3. STATE_SNAPSHOT received → player list visible
4. Role badge shows "Watching"; no action buttons

---

### TC-M6: Reconnect behavior

1. Join table as player (WS connected)
2. Disable network on device
3. Connection banner: "Reconnecting... (1/3)" → "Reconnecting... (2/3)" → "Reconnecting... (3/3)"
4. Re-enable network within 60s
5. WS reconnects → banner hides → STATE_SNAPSHOT re-received

---

### TC-M7: Manual reconnect (after 3 failures)

1. Join table → disable network
2. All 3 reconnect attempts fail
3. Banner shows "Connection lost. Tap to retry."
4. Re-enable network → tap "Retry"
5. WS reconnects → normal table screen

---

### TC-M8: Background / foreground

1. Join table as player → WS connected
2. Press home button → app backgrounds
3. Wait 5s → return to app
4. App reconnects to table automatically
5. STATE_SNAPSHOT received → table state correct

---

### TC-M9: Token expiry (simulated)

1. Login → navigate to clubs
2. Backend token manually invalidated (restart backend with different JWT_SECRET)
3. Tap any API action → 401 received
4. App navigates to login screen; previous token cleared

---

### TC-M10: SIT_OUT after reconnect

1. Join as player → disconnect device for >60s
2. Reconnect to app → WS reconnects
3. STATE_SNAPSHOT shows own status = "sit_out"
4. "You were away too long. You're sitting out." banner visible
5. Tap "Rejoin" → SIT_IN sent → status transitions to "waiting"

---

## Failure Cases

| FC | Scenario | Expected |
|----|----------|---------|
| FC-01 | Backend unreachable on login | Error message under "Send Code" button |
| FC-02 | Invalid phone format | Inline validation error before submit |
| FC-03 | OTP requested, code not entered within 5min | Code expired error on verify |
| FC-04 | Club not found (deleted between navigation) | 404 error on club detail screen with retry |
| FC-05 | Table full when joining as player | "Join as Player" disabled, "Table is full" shown |
| FC-06 | WS connect rejected (bad token) | Banner: "Authentication failed. Please log in again." → logout |
| FC-07 | WS receives unknown message type | Silently ignored; no crash; dev console log |
| FC-08 | WS receives malformed JSON | Silently ignored; no crash |
| FC-09 | App killed while on table screen | On restart, authStore rehydrates, navigates to clubs list (not table — table is session-bound) |
| FC-10 | Double-tap "Join as Player" | Second tap no-op (button disabled after first tap) |

---

## Edge Cases

| EC | Scenario |
|----|----------|
| EC-01 | User navigates away from table screen (back button) mid-hand → WS closes, no error |
| EC-02 | User receives STATE_SNAPSHOT with 0 players → empty player list, no crash |
| EC-03 | PLAYER_STATUS event arrives before STATE_SNAPSHOT → silently ignored (gameState is null) |
| EC-04 | Two rapid reconnect sequences → only one active WS connection at a time |
| EC-05 | Phone rotated on login screen → text field contents preserved |

---

## Race Conditions

| RC | Scenario |
|----|----------|
| RC-01 | `connect()` called twice (e.g., React strict mode double-effect) → second call should find existing connection or replace it cleanly |
| RC-02 | Network reconnects during backoff delay → timer cleared, new connection made |
| RC-03 | `disconnect()` called while reconnect timer is pending → timer cleared, no reconnect |
| RC-04 | App background triggers disconnect; WS onclose fires after disconnect() called → shouldReconnect=false prevents double reconnect |

---

## What This Feature Proves

| ✓ | Proves |
|---|--------|
| ✓ | Auth flow with OTP works end-to-end |
| ✓ | Token persistence and rehydration works |
| ✓ | Club data can be fetched and displayed |
| ✓ | WS connection can be established and maintained |
| ✓ | STATE_SNAPSHOT can be received and rendered |
| ✓ | Reconnect behavior (auto + manual) works |
| ✓ | Player vs spectator role is tracked correctly |

## What This Feature Does NOT Prove

| ✗ | Does Not Prove |
|---|---------------|
| ✗ | Gameplay UI is correct (not built) |
| ✗ | All game actions are usable from mobile |
| ✗ | Chat works end-to-end on mobile |
| ✗ | Push notification delivery |
| ✗ | Multi-device session conflict behavior |
| ✗ | App performance under sustained play (many hands) |
