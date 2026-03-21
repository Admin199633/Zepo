/**
 * TC-01 – TC-05: tableStore handResult / HAND_ENDED / HAND_STARTED
 */
import { act } from '@testing-library/react-native';

// Mock react-native AppState before imports
jest.mock('react-native', () => ({
  AppState: {
    addEventListener: jest.fn(() => ({ remove: jest.fn() })),
  },
}));

jest.mock('../src/ws/SocketClient', () => {
  let _statusCb: ((s: string) => void) | null = null;
  let _messageCb: ((e: { type: string; payload: unknown }) => void) | null = null;
  const instance = {
    connect: jest.fn(),
    disconnect: jest.fn(),
    send: jest.fn(),
    onStatus: jest.fn((cb: (s: string) => void) => {
      _statusCb = cb;
      return jest.fn();
    }),
    onMessage: jest.fn((cb: (e: { type: string; payload: unknown }) => void) => {
      _messageCb = cb;
      return jest.fn();
    }),
    currentReconnectAttempt: 0,
    maxReconnectAttempts: 3,
    __emit_status: (s: string) => _statusCb?.(s),
    __emit_message: (e: { type: string; payload: unknown }) => _messageCb?.(e),
  };
  return { SocketClient: jest.fn(() => instance), __instance: instance };
});

import { useTableStore } from '../src/store/tableStore';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const { __instance: mock } = jest.requireMock('../src/ws/SocketClient') as any;

const HAND_ENDED_PAYLOAD = {
  hand_id: 'h1',
  hand_number: 5,
  winners: [{ user_id: 'u1', amount: 200, hand_description: 'Full House' }],
  final_board: [
    { rank: 'A', suit: 's' },
    { rank: 'K', suit: 'h' },
    { rank: 'Q', suit: 'd' },
    { rank: 'J', suit: 'c' },
    { rank: 'T', suit: 's' },
  ],
  showdown_hands: [
    {
      user_id: 'u1',
      hole_cards: [{ rank: 'A', suit: 'h' }, { rank: 'A', suit: 'd' }],
      hand_description: 'Full House',
    },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  useTableStore.setState({
    handResult: null,
    gameState: null,
    connectionStatus: 'disconnected',
    error: null,
    reconnectAttempt: 0,
  });
});

describe('tableStore – handResult', () => {
  it('TC-01: handResult is null initially', () => {
    expect(useTableStore.getState().handResult).toBeNull();
  });

  it('TC-02: HAND_RESULT sets handResult', () => {
    useTableStore.getState().connect('t1', 'tok');
    act(() => {
      mock.__emit_message({
        type: 'HAND_RESULT',
        payload: {
          winners: [{ user_id: 'u1', amount: 200, hand: 'Full House' }],
          pot_total: 200,
          showdown_cards: {},
        },
      });
    });
    expect(useTableStore.getState().handResult).toMatchObject({
      winners: [{ user_id: 'u1', amount: 200 }],
    });
  });

  it('TC-03: PHASE_CHANGED pre_flop clears handResult', () => {
    useTableStore.setState({ handResult: HAND_ENDED_PAYLOAD as any });
    useTableStore.getState().connect('t1', 'tok');
    act(() => {
      mock.__emit_message({ type: 'PHASE_CHANGED', payload: { phase: 'pre_flop' } });
    });
    expect(useTableStore.getState().handResult).toBeNull();
  });

  it('TC-04: clearHandResult sets handResult to null', () => {
    useTableStore.setState({ handResult: HAND_ENDED_PAYLOAD as any });
    act(() => {
      useTableStore.getState().clearHandResult();
    });
    expect(useTableStore.getState().handResult).toBeNull();
  });

  it('TC-05: HAND_RESULT handResult has required shape', () => {
    useTableStore.getState().connect('t1', 'tok');
    act(() => {
      mock.__emit_message({
        type: 'HAND_RESULT',
        payload: {
          winners: [{ user_id: 'u1', amount: 200, hand: 'Full House' }],
          pot_total: 200,
          showdown_cards: {},
        },
      });
    });
    const result = useTableStore.getState().handResult!;
    expect(result).toHaveProperty('hand_id');
    expect(result).toHaveProperty('winners');
    expect(result).toHaveProperty('final_board');
    expect(result).toHaveProperty('showdown_hands');
  });
});
