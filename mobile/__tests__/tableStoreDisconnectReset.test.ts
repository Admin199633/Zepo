/**
 * tableStore disconnect/reset tests (TC-41).
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

// TC-41: gameState is null after STATE_SNAPSHOT then disconnect
test('TC-41: gameState is null after receiving STATE_SNAPSHOT then calling disconnect()', () => {
  emitMessage('STATE_SNAPSHOT', MOCK_SNAPSHOT as unknown as Record<string, unknown>);
  expect(useTableStore.getState().gameState).not.toBeNull();

  useTableStore.getState().disconnect();
  expect(useTableStore.getState().gameState).toBeNull();
  expect(useTableStore.getState().handResult).toBeNull();
});
