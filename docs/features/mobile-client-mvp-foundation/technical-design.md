# Technical Design — mobile-client-mvp-foundation

> Agent: Senior Mobile Game Developer
> Date: 2026-03-19

---

## 1. Stack Decision

| Concern | Choice | Reason |
|---------|--------|--------|
| Platform | React Native via Expo SDK 52 | Cross-platform (iOS + Android), managed workflow, fast iteration, large ecosystem |
| Routing | Expo Router v3 (file-based) | File-based routing aligned with Next.js mental model; auth group / app group split is clean |
| Language | TypeScript (strict mode) | Type-safe DTOs from backend contracts, fewer runtime errors, better IDE support |
| State | Zustand | Minimal boilerplate, no Provider wrapping, slice-based, easy to test with `act()` |
| HTTP client | Axios | Interceptor support for token injection + 401 handling; familiar to TS developers |
| WS client | Native `WebSocket` API (React Native built-in) | No extra dependency; built-in exponential backoff is straightforward to implement |
| Persistence | `@react-native-async-storage/async-storage` | Standard token/session persistence for React Native |
| Testing | Jest + `@testing-library/react-native` | Standard for RN; test store slices and client logic |
| Linting | ESLint + Prettier | Standard |

**Not chosen**:
- Redux / Redux Toolkit: overkill for MVP foundation; Zustand is sufficient
- Socket.io: not needed; backend uses raw WebSocket
- GraphQL: backend is REST + WS; no benefit
- Flutter: team is JS/TS-oriented; Expo is faster to start
- Bare React Native: Expo managed workflow reduces setup friction

---

## 2. Directory Structure

```
mobile/
├── app.json                      # Expo config (name, slug, version)
├── package.json
├── tsconfig.json
├── babel.config.js
├── jest.config.js
├── jest.setup.js
├── app/                          # Expo Router file-based routes
│   ├── _layout.tsx               # Root: token check → redirect to auth or app
│   ├── +not-found.tsx            # 404 fallback
│   ├── (auth)/
│   │   ├── _layout.tsx           # Stack navigator for auth screens
│   │   ├── login.tsx             # S1: Phone number entry
│   │   └── verify.tsx            # S2: OTP + optional display_name
│   └── (app)/
│       ├── _layout.tsx           # Stack navigator for app screens
│       ├── index.tsx             # S3: Clubs list
│       ├── clubs/
│       │   └── [clubId].tsx      # S4: Club detail
│       └── table/
│           └── [tableId].tsx     # S5: Table screen
├── src/
│   ├── config.ts                 # BASE_URL, WS_URL (env-driven)
│   ├── api/
│   │   ├── client.ts             # Axios instance + token interceptor + 401 handler
│   │   ├── auth.ts               # requestOtp, verifyOtp
│   │   ├── clubs.ts              # getClub, getUserClubs, createClub, joinClub
│   │   ├── tables.ts             # getClubTable
│   │   └── types.ts              # All HTTP request/response DTOs (mirrors backend)
│   ├── ws/
│   │   ├── SocketClient.ts       # WebSocket wrapper: connect/disconnect/send/event handlers
│   │   └── types.ts              # WS message types (mirrors backend realtime/schemas.py)
│   ├── store/
│   │   ├── authStore.ts          # token, userId, login, logout
│   │   ├── clubStore.ts          # clubs[], selectedClub, loading/error
│   │   └── tableStore.ts         # gameState, connectionStatus, myRole
│   └── components/
│       ├── common/
│       │   ├── Button.tsx
│       │   ├── LoadingSpinner.tsx
│       │   └── ErrorDisplay.tsx
│       └── table/
│           ├── ConnectionBanner.tsx
│           ├── PlayerList.tsx
│           └── RoleBadge.tsx
└── __tests__/
    ├── authStore.test.ts
    ├── clubStore.test.ts
    ├── tableStore.test.ts
    └── SocketClient.test.ts
```

---

## 3. Navigation Architecture

### Root Layout (`app/_layout.tsx`)

On mount, reads token from AsyncStorage:
- Valid token → replace current route with `/(app)/`
- No token / expired → replace with `/(auth)/login`

On 401 anywhere → `authStore.logout()` → replace with `/(auth)/login`

### Auth group (`(auth)`)

Stack: `login` → `verify` (parameters: `phone` passed via route params)
After success → `router.replace('/(app)/')` — no back navigation to auth

### App group (`(app)`)

Stack: `index` → `clubs/[clubId]` → `table/[tableId]`
No tab bar in MVP. Pure stack navigation.

---

## 4. State Management

### `authStore` (Zustand slice)

```typescript
interface AuthState {
  token: string | null;
  userId: string | null;
  isHydrated: boolean;   // true once AsyncStorage read is complete
  login: (token: string, userId: string) => Promise<void>;  // persists to storage
  logout: () => Promise<void>;  // clears storage
  hydrate: () => Promise<void>; // reads from storage on startup
}
```

### `clubStore` (Zustand slice)

```typescript
interface ClubState {
  clubs: ClubDTO[];
  selectedClub: ClubDTO | null;
  tableInfo: TableInfoDTO | null;
  status: 'idle' | 'loading' | 'error';
  error: string | null;
  fetchClubs: () => Promise<void>;        // not implemented in MVP — no list endpoint
  fetchClub: (clubId: string) => Promise<void>;
  fetchTableInfo: (clubId: string) => Promise<void>;
}
```

Note: Backend has no `GET /clubs` endpoint (get all clubs for user). `fetchClubs` is stubbed. The clubs list screen is populated from the club response or via club_id known from previous navigation. This is a known gap — tracked in deferred items.

### `tableStore` (Zustand slice)

```typescript
type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed';

interface TableState {
  gameState: StateSnapshotDTO | null;
  connectionStatus: ConnectionStatus;
  reconnectAttempt: number;         // 0-3
  myRole: 'player' | 'spectator' | null;
  myUserId: string | null;
  connect: (tableId: string, token: string, role: 'player' | 'spectator') => void;
  disconnect: () => void;
  sendAction: (action: string, amount?: number) => void;
  requestSync: () => void;
  reset: () => void;
}
```

The store owns the `SocketClient` instance internally. No React component directly accesses the socket.

---

## 5. API Client Structure

### `src/config.ts`

```typescript
export const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
export const WS_BASE_URL = process.env.EXPO_PUBLIC_WS_URL ?? 'ws://localhost:8000';
```

### `src/api/client.ts`

- Single Axios instance with `baseURL = BASE_URL`
- Request interceptor: inject `Authorization: Bearer {token}` from `authStore`
- Response interceptor: on 401 → call `authStore.logout()` → navigate to login

### `src/api/types.ts` — typed mirrors of backend response models

```typescript
// POST /auth/request-otp → {}
export interface OtpRequestBody { phone_number: string; }

// POST /auth/verify-otp
export interface OtpVerifyBody { phone_number: string; code: string; display_name?: string; }
export interface TokenResponse { token: string; user_id: string; expires_at: number; }

// POST /clubs
export interface CreateClubBody { name: string; }
export interface CreateClubResponse { club_id: string; table_id: string; invite_code: string; }

// GET /clubs/{club_id}
export interface ClubDTO { club_id: string; name: string; owner_id: string; invite_code: string; member_count: number; }

// GET /clubs/{club_id}/table
export interface TableConfigDTO { starting_stack: number; small_blind: number; big_blind: number; turn_timer_seconds: number; max_players: number; house_rules: string[]; }
export interface TableInfoDTO { table_id: string; config: TableConfigDTO; recent_hands: RecentHandDTO[]; }
export interface RecentHandDTO { hand_id: string; hand_number: number; pot_total: number; winner_ids: string[]; phase_reached: string; timestamp: number; }

// Backend error shape
export interface ApiError { detail: { error: string; message: string; }; }
```

---

## 6. WebSocket Client Structure

### `src/ws/SocketClient.ts`

```typescript
class SocketClient {
  private ws: WebSocket | null = null;
  private tableId: string = '';
  private token: string = '';
  private onMessage: (env: ServerEnvelope) => void;
  private onStatusChange: (status: ConnectionStatus) => void;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 3;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  connect(tableId: string, token: string): void;
  disconnect(): void;
  send(type: ClientMessageType, payload?: Record<string, unknown>): void;
  private _createConnection(): void;
  private _scheduleReconnect(): void;
  private _clearReconnectTimer(): void;
}
```

**Reconnect strategy**:
- `onclose` fires → if `shouldReconnect && reconnectAttempts < maxReconnectAttempts`:
  - Attempt 1: after 1s
  - Attempt 2: after 2s
  - Attempt 3: after 4s
- After 3 failures: `onStatusChange('failed')` → user sees manual retry button
- On successful reconnect: send JOIN_TABLE again (backend's `_do_reconnect` handles it)
- `disconnect()` sets `shouldReconnect = false` before closing — prevents auto-reconnect on voluntary leave

**WS URL construction**:
```
${WS_BASE_URL}/ws/table/${tableId}?token=${token}
```

---

## 7. WS Message Types (`src/ws/types.ts`)

Typed mirrors of `backend/realtime/schemas.py`:

```typescript
// Server → Client
export type ServerEventType =
  | 'STATE_SNAPSHOT' | 'PHASE_CHANGED' | 'CARDS_DEALT' | 'COMMUNITY_CARDS'
  | 'PLAYER_ACTED' | 'TURN_CHANGED' | 'POT_UPDATED' | 'PLAYER_STATUS'
  | 'HAND_RESULT' | 'BLINDS_POSTED' | 'BONUS_AWARDED' | 'CHAT_MESSAGE'
  | 'PLAYER_JOINED' | 'PLAYER_LEFT' | 'ERROR';

export interface ServerEnvelope<T = Record<string, unknown>> {
  v: number;
  seq: number;
  table_id: string;
  type: ServerEventType;
  payload: T;
  ts: number;
}

// Client → Server
export type ClientMessageType =
  | 'ACTION' | 'CHAT' | 'JOIN_TABLE' | 'LEAVE_TABLE' | 'SYNC_REQUEST' | 'SIT_OUT' | 'SIT_IN';

export interface ClientEnvelope {
  type: ClientMessageType;
  request_id: string;
  table_id: string;
  payload: Record<string, unknown>;
}

// Key payload types (for tableStore to process)
export interface PlayerViewDTO {
  user_id: string;
  display_name: string;
  seat_index: number;
  stack: number;
  status: string;
  is_connected: boolean;
}

export interface StateSnapshotDTO {
  table_id: string;
  club_id: string;
  phase: string;
  hand_number: number;
  players: Record<string, PlayerViewDTO>;
  seat_map: Record<string, string>;
  config: TableConfigDTO;
  hand: HandViewDTO | null;
}
```

---

## 8. Auth Token Handling

**Storage**: `@react-native-async-storage/async-storage` with key `@zepo/auth_token`

**Hydration**: On app start, `authStore.hydrate()` reads token + userId from storage. `isHydrated` flag prevents root layout from rendering until this completes (avoids flash of login screen for returning users).

**Expiry check**: Token payload is NOT decoded client-side. Instead, on API 401 response → clear token and redirect to login. This is simpler and correct for MVP.

**Injection**: Axios request interceptor reads `authStore.getState().token` synchronously and injects as Bearer header.

---

## 9. Reconnect Handling on Mobile

**Background/foreground transitions**:
- On app `AppState.change` to "background": call `socketClient.disconnect()` (voluntary — no auto-reconnect)
- On app `AppState.change` to "active" from "background": call `tableStore.connect(...)` if still on table screen

This prevents battery drain from background WS activity. iOS background time is limited, so voluntary disconnect is the correct choice.

**Implementation**: `useEffect` in `TableScreen` listens to `AppState` events.

---

## 10. Integration with Backend Contracts

Backend contract assumptions (must not change during this feature):
- Auth: `POST /auth/request-otp` returns `{}`, `POST /auth/verify-otp` returns `{token, user_id, expires_at}`
- Clubs: `GET /clubs/{id}` returns `{club_id, name, owner_id, invite_code, member_count}`
- Tables: `GET /clubs/{id}/table` returns `{table_id, config, recent_hands}`
- WS: connect with `?token=`, first message `JOIN_TABLE{role}`, first response `STATE_SNAPSHOT`
- Error shape: `{detail: {error: "CODE", message: "Human readable"}}`

The API client normalizes error messages using a helper:
```typescript
function extractErrorMessage(err: unknown): string {
  const apiErr = (err as AxiosError<ApiError>)?.response?.data;
  return apiErr?.detail?.message ?? 'Something went wrong.';
}
```

---

## 11. MVP-Safe Error Handling Strategy

- 4xx errors: shown inline under the relevant action (field errors, join failures)
- 5xx errors: shown as toast / modal "Something went wrong. Please try again."
- Network unreachable: shown as persistent banner
- WS connection failure: reconnect banner (see Connection Banner in UX spec)
- WS parse error: silently ignored (unrecognized message types logged in dev)

No crash on bad server response. All JSON parsing wrapped in try/catch.

---

## 12. Testing Strategy

**Unit tests** (Jest — `mobile/__tests__/`):
- `authStore.test.ts`: login, logout, hydrate, token persistence mock
- `clubStore.test.ts`: fetch club, fetch table info, loading/error states
- `tableStore.test.ts`: connect/disconnect, STATE_SNAPSHOT ingestion, status transitions
- `SocketClient.test.ts`: connect, send, receive message, reconnect backoff logic

**What is NOT tested by Jest**:
- Actual WS connection to live backend (E2E only)
- Screen rendering (sufficient for MVP; component tests deferred)
- Navigation (integration test for later)

**Mock strategy**:
- Axios: mocked via `jest.mock('axios')` or `axios-mock-adapter`
- WebSocket: global `WebSocket` class mocked with a test double
- AsyncStorage: mocked via `@react-native-async-storage/async-storage/jest/async-storage-mock`

---

## 13. MVP-Known Gaps (Not Bugs — Designed Deferrals)

| Gap | Impact | Deferred to |
|-----|--------|-------------|
| No `GET /clubs` (all clubs for user) endpoint | Clubs list shows only club navigated to via invite or deep link | Next backend feature |
| Join by invite code UI | New player onboarding requires out-of-band invite handling | Post-MVP |
| Create club from app | Club creation requires API call; deferred from app | Post-MVP |
| Gameplay UI (cards, betting controls) | Table screen is a placeholder | Table UI feature |
| Chat UI | WS message type CHAT_MESSAGE received but not displayed | Post-MVP |
| Token decode / expiry proactive check | Auth relies on 401 response; no proactive expiry check | Future hardening |
