/**
 * tableStore unit tests (TC-14 through TC-24).
 * Mocks react-native AppState and the SocketClient module.
 */

// Mock react-native BEFORE any imports
jest.mock('react-native', () => ({
  AppState: {
    addEventListener: jest.fn(() => ({ remove: jest.fn() })),
  },
}));

// Mock SocketClient — factory keeps state internally to avoid hoisting issues
jest.mock('../src/ws/SocketClient', () => {
  let _statusCb: ((s: string) => void) | null = null;
  let _messageCb: ((e: Record<string, unknown>) => void) | null = null;

  const instance = {
    connect: jest.fn(),
    disconnect: jest.fn(),
    send: jest.fn(),
    onStatus: jest.fn((cb: (s: string) => void) => {
      _statusCb = cb;
      return jest.fn();
    }),
    onMessage: jest.fn((cb: (e: Record<string, unknown>) => void) => {
      _messageCb = cb;
      return jest.fn();
    }),
    currentReconnectAttempt: 0,
    maxReconnectAttempts: 3,
    __emit_status: (s: string) => _statusCb?.(s),
    __emit_message: (e: Record<string, unknown>) => _messageCb?.(e),
  };

  return { SocketClient: jest.fn(() => instance), __instance: instance };
});

import { useTableStore } from '../src/store/tableStore';
import type { StateSnapshotDTO } from '../src/ws/types';

// Get the shared mock instance that the store module used at import time
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const { __instance: mock } = jest.requireMock('../src/ws/SocketClient') as any;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function emitStatus(status: string) {
  mock.__emit_status(status);
}

function emitMessage(type: string, payload: Record<string, unknown>) {
  mock.__emit_message({ type, payload });
}

// Backend-format snapshot (wire format from server)
const MOCK_BACKEND_SNAPSHOT = {
  table_id: 'tbl_1',
  club_id: 'club_1',
  phase: 'idle',
  hand_number: 0,
  players: {} as Record<string, unknown>,
  seat_map: {} as Record<string, string>,
  config: {},
  hand: null,
};

// Expected UI snapshot after transformation (token "dev_u1" → your_user_id "u1")
const MOCK_SNAPSHOT: StateSnapshotDTO = {
  table_id: 'tbl_1',
  your_user_id: 'u1',
  players: [],
  current_hand: null,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  useTableStore.getState().reset();
  jest.clearAllMocks();
});

// TC-14: initial state
test('TC-14: initial state is disconnected with no game state', () => {
  const { connectionStatus, gameState, error } = useTableStore.getState();
  expect(connectionStatus).toBe('disconnected');
  expect(gameState).toBeNull();
  expect(error).toBeNull();
});

// TC-15: connect() calls socketClient.connect
test('TC-15: connect() calls socketClient.connect with tableId and token', () => {
  useTableStore.getState().connect('tbl_1', 'tok_abc');
  expect(mock.connect).toHaveBeenCalledWith('tbl_1', 'tok_abc');
});

// TC-16: status listener updates connectionStatus in store
test('TC-16: status change from SocketClient updates store connectionStatus', () => {
  emitStatus('connected');
  expect(useTableStore.getState().connectionStatus).toBe('connected');
});

// TC-17: STATE_SNAPSHOT message sets gameState (backend format → UI format)
test('TC-17: STATE_SNAPSHOT sets gameState', () => {
  useTableStore.getState().connect('tbl_1', 'dev_u1');
  emitMessage('STATE_SNAPSHOT', MOCK_BACKEND_SNAPSHOT as unknown as Record<string, unknown>);
  expect(useTableStore.getState().gameState).toEqual(MOCK_SNAPSHOT);
  expect(useTableStore.getState().error).toBeNull();
});

// TC-18: ERROR message sets error
test('TC-18: ERROR message sets error string', () => {
  emitMessage('ERROR', { message: 'Not your turn' });
  expect(useTableStore.getState().error).toBe('Not your turn');
});

// TC-19: ERROR with no message field uses fallback
test('TC-19: ERROR with missing message uses fallback', () => {
  emitMessage('ERROR', {});
  expect(useTableStore.getState().error).toBe('An error occurred.');
});

// TC-20: disconnect() calls socketClient.disconnect and clears gameState
test('TC-20: disconnect() calls socketClient.disconnect and clears gameState', () => {
  emitMessage('STATE_SNAPSHOT', MOCK_SNAPSHOT as unknown as Record<string, unknown>);
  useTableStore.getState().disconnect();
  expect(mock.disconnect).toHaveBeenCalled();
  expect(useTableStore.getState().gameState).toBeNull();
});

// TC-21: sendJoin() sends JOIN_TABLE with role payload
test('TC-21: sendJoin sends JOIN_TABLE with role', () => {
  useTableStore.getState().sendJoin('player');
  expect(mock.send).toHaveBeenCalledWith('JOIN_TABLE', { role: 'player' });
});

// TC-22: sendSitOut() sends SIT_OUT
test('TC-22: sendSitOut sends SIT_OUT', () => {
  useTableStore.getState().sendSitOut();
  expect(mock.send).toHaveBeenCalledWith('SIT_OUT');
});

// TC-23: sendSitIn() sends SIT_IN
test('TC-23: sendSitIn sends SIT_IN', () => {
  useTableStore.getState().sendSitIn();
  expect(mock.send).toHaveBeenCalledWith('SIT_IN');
});

// TC-24: reset clears all state and disconnects
test('TC-24: reset clears state and calls socketClient.disconnect', () => {
  emitStatus('connected');
  emitMessage('STATE_SNAPSHOT', MOCK_SNAPSHOT as unknown as Record<string, unknown>);

  useTableStore.getState().reset();

  const { connectionStatus, gameState, joinPending, error } = useTableStore.getState();
  expect(connectionStatus).toBe('disconnected');
  expect(gameState).toBeNull();
  expect(joinPending).toBe(false);
  expect(error).toBeNull();
  expect(mock.disconnect).toHaveBeenCalled();
});
