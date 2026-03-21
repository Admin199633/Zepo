/**
 * tableStore joinPending tests (TC-35 through TC-40).
 */

jest.mock('react-native', () => ({
  AppState: {
    addEventListener: jest.fn(() => ({ remove: jest.fn() })),
  },
}));

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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const { __instance: mock } = jest.requireMock('../src/ws/SocketClient') as any;

function emitMessage(type: string, payload: Record<string, unknown>) {
  mock.__emit_message({ type, payload });
}

const MOCK_SNAPSHOT: StateSnapshotDTO = {
  table_id: 'tbl_1',
  your_user_id: 'u1',
  players: [],
  current_hand: null,
};

beforeEach(() => {
  useTableStore.getState().reset();
  jest.clearAllMocks();
});

// TC-35: joinPending is false in initial state
test('TC-35: joinPending is false in initial state', () => {
  expect(useTableStore.getState().joinPending).toBe(false);
});

// TC-36: joinPending is set to true when sendJoin is called (player)
test('TC-36: sendJoin(player) sets joinPending to true', () => {
  useTableStore.getState().sendJoin('player');
  expect(useTableStore.getState().joinPending).toBe(true);
});

// TC-37: joinPending is set to true when sendJoin is called (watcher)
test('TC-37: sendJoin(watcher) sets joinPending to true', () => {
  useTableStore.getState().sendJoin('watcher');
  expect(useTableStore.getState().joinPending).toBe(true);
});

// TC-38: joinPending is cleared to false when STATE_SNAPSHOT is received
test('TC-38: STATE_SNAPSHOT clears joinPending', () => {
  useTableStore.getState().sendJoin('player');
  expect(useTableStore.getState().joinPending).toBe(true);

  emitMessage('STATE_SNAPSHOT', MOCK_SNAPSHOT as unknown as Record<string, unknown>);
  expect(useTableStore.getState().joinPending).toBe(false);
});

// TC-39: joinPending is cleared by disconnect()
test('TC-39: disconnect() clears joinPending', () => {
  useTableStore.getState().sendJoin('player');
  expect(useTableStore.getState().joinPending).toBe(true);

  useTableStore.getState().disconnect();
  expect(useTableStore.getState().joinPending).toBe(false);
});

// TC-40: joinPending is cleared by reset()
test('TC-40: reset() clears joinPending', () => {
  useTableStore.getState().sendJoin('player');
  expect(useTableStore.getState().joinPending).toBe(true);

  useTableStore.getState().reset();
  expect(useTableStore.getState().joinPending).toBe(false);
});
