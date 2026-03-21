/**
 * tableStore SYNC_REQUEST tests (TC-42 through TC-43).
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const { __instance: mock } = jest.requireMock('../src/ws/SocketClient') as any;

function emitStatus(status: string) {
  mock.__emit_status(status);
}

// Capture the AppState callback registered during store initialization.
// Must be done in beforeAll before jest.clearAllMocks() wipes mock.calls.
let appStateCallback: ((state: string) => void) | null = null;

beforeAll(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const AppStateMock = (jest.requireMock('react-native') as any).AppState;
  appStateCallback = AppStateMock.addEventListener.mock.calls[0]?.[1] ?? null;
});

beforeEach(() => {
  useTableStore.getState().reset();
  jest.clearAllMocks();
});

// TC-42: SYNC_REQUEST is sent when app returns to foreground while connected
test('TC-42: SYNC_REQUEST sent on foreground resume when status is connected', () => {
  useTableStore.getState().connect('tbl_1', 'tok_abc');
  emitStatus('connected');
  jest.clearAllMocks();

  // Simulate going background then coming back to foreground
  appStateCallback?.('background');
  appStateCallback?.('active');

  expect(mock.send).toHaveBeenCalledWith('SYNC_REQUEST');
});

// TC-43: no duplicate connect call is made when foreground resumes while connected
test('TC-43: no duplicate connect() on foreground resume when already connected', () => {
  useTableStore.getState().connect('tbl_1', 'tok_abc');
  emitStatus('connected');
  jest.clearAllMocks();

  appStateCallback?.('background');
  appStateCallback?.('active');

  expect(mock.connect).not.toHaveBeenCalled();
});
