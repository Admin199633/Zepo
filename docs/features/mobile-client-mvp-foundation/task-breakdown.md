# Task Breakdown — mobile-client-mvp-foundation

> Agent: Senior Mobile Game Developer
> Date: 2026-03-19

---

## Overview

| Task | Description |
|------|-------------|
| T0 | Create `mobile/` project scaffold (package.json, app.json, tsconfig, config) |
| T1 | Navigation shell and root layout |
| T2 | Auth screens (Login, VerifyOTP) + authStore |
| T3 | Clubs screens (ClubsList, ClubDetail) + clubStore |
| T4 | WebSocket client (SocketClient) + WS types |
| T5 | Table screen + tableStore |
| T6 | Common components (Button, LoadingSpinner, ErrorDisplay, ConnectionBanner, PlayerList, RoleBadge) |
| T7 | Unit tests |

---

## T0 — Project Scaffold

**Files:**
- `mobile/package.json`
- `mobile/app.json`
- `mobile/tsconfig.json`
- `mobile/babel.config.js`
- `mobile/jest.config.js`
- `mobile/jest.setup.js`
- `mobile/src/config.ts`

Key dependencies:
```json
{
  "expo": "~52.0.0",
  "expo-router": "~4.0.0",
  "react": "18.3.2",
  "react-native": "0.76.5",
  "typescript": "~5.3.3",
  "zustand": "^5.0.0",
  "axios": "^1.7.0",
  "@react-native-async-storage/async-storage": "2.1.0",
  "expo-status-bar": "~2.0.0",
  "expo-constants": "~17.0.0"
}
```

Dev dependencies:
```json
{
  "@types/react": "~18.3.12",
  "@types/react-native": "~0.76.0",
  "jest": "^29.0.0",
  "@testing-library/react-native": "^13.0.0",
  "axios-mock-adapter": "^2.0.0",
  "jest-expo": "~52.0.0"
}
```

---

## T1 — Navigation Shell

**Files:**
- `mobile/app/_layout.tsx` — Root: hydrate auth, redirect to auth or app
- `mobile/app/+not-found.tsx` — 404 screen
- `mobile/app/(auth)/_layout.tsx` — Stack navigator for auth
- `mobile/app/(app)/_layout.tsx` — Stack navigator for app

Root layout logic:
```typescript
// On mount: authStore.hydrate() → check isHydrated + token → redirect
useEffect(() => {
  authStore.hydrate().then(() => {
    if (authStore.token) router.replace('/(app)/');
    else router.replace('/(auth)/login');
  });
}, []);
// Render nothing until hydrated (show splash or loading indicator)
```

---

## T2 — Auth Screens + Store

**Files:**
- `mobile/app/(auth)/login.tsx`
- `mobile/app/(auth)/verify.tsx`
- `mobile/src/store/authStore.ts`
- `mobile/src/api/auth.ts`

### `authStore.ts`

```typescript
import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';

const TOKEN_KEY = '@zepo/auth_token';
const USER_KEY = '@zepo/user_id';

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  userId: null,
  isHydrated: false,
  hydrate: async () => {
    const token = await AsyncStorage.getItem(TOKEN_KEY);
    const userId = await AsyncStorage.getItem(USER_KEY);
    set({ token, userId, isHydrated: true });
  },
  login: async (token, userId) => {
    await AsyncStorage.setItem(TOKEN_KEY, token);
    await AsyncStorage.setItem(USER_KEY, userId);
    set({ token, userId });
  },
  logout: async () => {
    await AsyncStorage.removeItem(TOKEN_KEY);
    await AsyncStorage.removeItem(USER_KEY);
    set({ token: null, userId: null });
  },
}));
```

### `auth.ts` API functions

```typescript
export async function requestOtp(phone: string): Promise<void>
export async function verifyOtp(phone: string, code: string, displayName?: string): Promise<TokenResponse>
```

---

## T3 — Clubs Screens + Store

**Files:**
- `mobile/app/(app)/index.tsx` (Clubs list)
- `mobile/app/(app)/clubs/[clubId].tsx` (Club detail)
- `mobile/src/store/clubStore.ts`
- `mobile/src/api/clubs.ts`
- `mobile/src/api/tables.ts`

### `clubStore.ts`

```typescript
export const useClubStore = create<ClubState>((set) => ({
  selectedClub: null,
  tableInfo: null,
  status: 'idle',
  error: null,
  fetchClub: async (clubId) => {
    set({ status: 'loading', error: null });
    try {
      const club = await getClub(clubId);
      set({ selectedClub: club, status: 'idle' });
    } catch (e) {
      set({ status: 'error', error: extractErrorMessage(e) });
    }
  },
  fetchTableInfo: async (clubId) => {
    try {
      const info = await getClubTable(clubId);
      set({ tableInfo: info });
    } catch (e) {
      set({ error: extractErrorMessage(e) });
    }
  },
}));
```

**Clubs list screen**: Since there is no `GET /clubs` endpoint, the clubs list screen will show:
- An empty state with guidance if no club ID is cached
- Navigates to club via deep-link or a hardcoded test club ID in dev
- NOTE: This is the known gap tracked in technical design. The screen is built but shows empty state + guidance text in MVP.

---

## T4 — WebSocket Client

**Files:**
- `mobile/src/ws/SocketClient.ts`
- `mobile/src/ws/types.ts`

### `SocketClient.ts`

```typescript
export class SocketClient {
  private ws: WebSocket | null = null;
  private tableId = '';
  private token = '';
  private shouldReconnect = false;
  private reconnectAttempts = 0;
  private readonly MAX_ATTEMPTS = 3;
  private readonly BACKOFF_MS = [1000, 2000, 4000];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private onMessage: (env: ServerEnvelope) => void;
  private onStatusChange: (status: ConnectionStatus) => void;

  constructor(
    onMessage: (env: ServerEnvelope) => void,
    onStatusChange: (status: ConnectionStatus) => void,
  ) {
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
  }

  connect(tableId: string, token: string): void {
    this.tableId = tableId;
    this.token = token;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    this._createConnection();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this._clearReconnectTimer();
    this.ws?.close();
    this.ws = null;
  }

  send(type: ClientMessageType, payload: Record<string, unknown> = {}): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return;
    const env: ClientEnvelope = {
      type,
      request_id: crypto.randomUUID(),
      table_id: this.tableId,
      payload,
    };
    this.ws.send(JSON.stringify(env));
  }

  private _createConnection(): void {
    const url = `${WS_BASE_URL}/ws/table/${this.tableId}?token=${this.token}`;
    this.onStatusChange('connecting');
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onStatusChange('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const env = JSON.parse(event.data) as ServerEnvelope;
        this.onMessage(env);
      } catch {
        // Malformed JSON — silently ignore
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      if (this.shouldReconnect && this.reconnectAttempts < this.MAX_ATTEMPTS) {
        this._scheduleReconnect();
      } else if (this.shouldReconnect) {
        this.onStatusChange('failed');
      } else {
        this.onStatusChange('disconnected');
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror — let it handle reconnect logic
    };
  }

  private _scheduleReconnect(): void {
    const delay = this.BACKOFF_MS[this.reconnectAttempts] ?? 4000;
    this.reconnectAttempts++;
    this.onStatusChange('reconnecting');
    this.reconnectTimer = setTimeout(() => {
      this._createConnection();
    }, delay);
  }

  private _clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
```

---

## T5 — Table Screen + tableStore

**Files:**
- `mobile/app/(app)/table/[tableId].tsx`
- `mobile/src/store/tableStore.ts`

### `tableStore.ts`

```typescript
import { create } from 'zustand';
import { SocketClient } from '../ws/SocketClient';

export const useTableStore = create<TableState>((set, get) => {
  let client: SocketClient | null = null;

  const handleMessage = (env: ServerEnvelope) => {
    const state = get();
    if (env.type === 'STATE_SNAPSHOT') {
      set({ gameState: env.payload as StateSnapshotDTO });
    } else if (env.type === 'PLAYER_STATUS' && state.gameState) {
      const p = env.payload as { user_id: string; status: string; stack: number; };
      set({
        gameState: {
          ...state.gameState,
          players: {
            ...state.gameState.players,
            [p.user_id]: { ...state.gameState.players[p.user_id], status: p.status, stack: p.stack },
          },
        },
      });
    } else if (env.type === 'PLAYER_JOINED' && state.gameState) {
      const p = env.payload as PlayerViewDTO & { role: string };
      if (p.role === 'player') {
        set({
          gameState: {
            ...state.gameState,
            players: {
              ...state.gameState.players,
              [p.user_id]: { user_id: p.user_id, display_name: p.display_name, seat_index: p.seat_index, stack: p.stack, status: 'active', is_connected: true },
            },
          },
        });
      }
    } else if (env.type === 'PLAYER_LEFT' && state.gameState) {
      const { user_id } = env.payload as { user_id: string };
      const { [user_id]: _, ...rest } = state.gameState.players;
      set({ gameState: { ...state.gameState, players: rest } });
    }
    // PHASE_CHANGED, HAND_RESULT etc. handled when gameplay UI is built
  };

  const handleStatusChange = (status: ConnectionStatus) => {
    set({ connectionStatus: status, reconnectAttempt: status === 'reconnecting' ? get().reconnectAttempt + 1 : 0 });
  };

  return {
    gameState: null,
    connectionStatus: 'disconnected',
    reconnectAttempt: 0,
    myRole: null,
    myUserId: null,

    connect: (tableId, token, role) => {
      set({ myRole: role, myUserId: null, gameState: null, connectionStatus: 'connecting', reconnectAttempt: 0 });
      client = new SocketClient(handleMessage, handleStatusChange);
      client.connect(tableId, token);
      // Send JOIN_TABLE after connection is established (onopen triggers handleStatusChange('connected'))
      // We observe connectionStatus change and send JOIN_TABLE in useEffect on the screen
    },

    disconnect: () => {
      client?.disconnect();
      client = null;
      set({ connectionStatus: 'disconnected', gameState: null, myRole: null });
    },

    sendJoin: (tableId, role) => {
      client?.send('JOIN_TABLE', { role });
    },

    sendAction: (action, amount = 0) => {
      client?.send('ACTION', { action, amount });
    },

    requestSync: () => {
      client?.send('SYNC_REQUEST');
    },

    sendSitIn: () => {
      client?.send('SIT_IN');
    },

    reset: () => {
      client?.disconnect();
      client = null;
      set({ gameState: null, connectionStatus: 'disconnected', myRole: null, myUserId: null, reconnectAttempt: 0 });
    },
  };
});
```

### `table/[tableId].tsx` Screen Logic

```typescript
// Key behaviors:
// 1. Mount: show role choice modal
// 2. On role choice: tableStore.connect(tableId, token, role)
// 3. Watch connectionStatus: when 'connected' → send JOIN_TABLE
// 4. Watch connectionStatus: show ConnectionBanner
// 5. Watch gameState: render PlayerList when available
// 6. Unmount: tableStore.disconnect()
// 7. AppState 'background': tableStore.disconnect()
// 8. AppState 'active': if still on screen, reconnect
```

---

## T6 — Common Components

**Files:**
- `mobile/src/components/common/Button.tsx` — Accessible button with loading state
- `mobile/src/components/common/LoadingSpinner.tsx` — ActivityIndicator wrapper
- `mobile/src/components/common/ErrorDisplay.tsx` — Inline error text with optional retry
- `mobile/src/components/table/ConnectionBanner.tsx` — Top banner for WS status
- `mobile/src/components/table/PlayerList.tsx` — Flat list of PlayerViewDTO
- `mobile/src/components/table/RoleBadge.tsx` — "Playing" / "Watching" / "Sitting Out" badge

---

## T7 — Unit Tests

**Files:**
- `mobile/__tests__/authStore.test.ts`
- `mobile/__tests__/clubStore.test.ts`
- `mobile/__tests__/tableStore.test.ts`
- `mobile/__tests__/SocketClient.test.ts`

Test each store slice with mocked axios and mocked WebSocket. Use `act()` from `@testing-library/react-native` for async state updates.

---

## Build & Run Commands

```bash
# Install
cd mobile
npm install

# Run (requires Expo Go app on device or simulator)
npx expo start

# Run tests
npx jest

# Run tests with coverage
npx jest --coverage

# TypeScript check
npx tsc --noEmit

# Lint
npx eslint src/ app/ __tests__/
```
