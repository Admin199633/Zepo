/**
 * SocketClient unit tests (TC-25 through TC-34).
 * Uses a fake WebSocket implementation to avoid native dependencies.
 */

import { SocketClient } from '../src/ws/SocketClient';

// ---------------------------------------------------------------------------
// Fake WebSocket
// ---------------------------------------------------------------------------

type FakeHandler = ((event: { data?: string }) => void) | null;

class FakeWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  readyState: number;
  url: string;

  onopen: FakeHandler = null;
  onmessage: FakeHandler = null;
  onclose: FakeHandler = null;
  onerror: FakeHandler = null;

  constructor(url: string) {
    this.url = url;
    this.readyState = FakeWebSocket.CONNECTING;
    FakeWebSocket._instances.push(this);
  }

  send = jest.fn();
  close = jest.fn(() => {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({});
  });

  // Test helpers
  simulateOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.({});
  }
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  simulateClose() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({});
  }

  static _instances: FakeWebSocket[] = [];
  static latest(): FakeWebSocket {
    return FakeWebSocket._instances[FakeWebSocket._instances.length - 1];
  }
  static reset() {
    FakeWebSocket._instances = [];
  }
}

// Install global fake WebSocket
(global as Record<string, unknown>).WebSocket = FakeWebSocket as unknown as typeof WebSocket;

beforeEach(() => {
  FakeWebSocket.reset();
  jest.useFakeTimers();
});
afterEach(() => {
  jest.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// TC-25: connect() opens a WebSocket URL containing tableId and token
test('TC-25: connect() opens WebSocket with correct URL', () => {
  const client = new SocketClient();
  client.connect('tbl_1', 'mytoken');

  const ws = FakeWebSocket.latest();
  expect(ws.url).toContain('tbl_1');
  expect(ws.url).toContain('mytoken');
});

// TC-26: status transitions to 'connecting' then 'connected' on open
test('TC-26: status goes connecting → connected on open', () => {
  const statuses: string[] = [];
  const client = new SocketClient();
  client.onStatus((s) => statuses.push(s));

  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();

  expect(statuses).toEqual(['connecting', 'connected']);
});

// TC-27: onMessage listener receives parsed SERVER envelope
test('TC-27: onMessage receives parsed envelope', () => {
  const messages: unknown[] = [];
  const client = new SocketClient();
  client.onMessage((e) => messages.push(e));

  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();
  FakeWebSocket.latest().simulateMessage({ type: 'STATE_SNAPSHOT', payload: { table_id: 'tbl_1' } });

  expect(messages).toHaveLength(1);
  expect((messages[0] as { type: string }).type).toBe('STATE_SNAPSHOT');
});

// TC-28: send() sends serialized ClientEnvelope
test('TC-28: send() serializes and sends envelope', () => {
  const client = new SocketClient();
  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();

  client.send('JOIN', { role: 'player' });

  const ws = FakeWebSocket.latest();
  expect(ws.send).toHaveBeenCalledTimes(1);
  const envelope = JSON.parse((ws.send.mock.calls[0] as string[])[0]);
  expect(envelope.type).toBe('JOIN');
  expect(envelope.payload.role).toBe('player');
  expect(typeof envelope.request_id).toBe('string');
});

// TC-29: send() does nothing when not connected
test('TC-29: send() is a no-op when not connected', () => {
  const client = new SocketClient();
  client.send('PING');
  // No crash, no WebSocket created
  expect(FakeWebSocket._instances).toHaveLength(0);
});

// TC-30: voluntary disconnect() prevents reconnect
test('TC-30: disconnect() prevents reconnect after close', () => {
  const statuses: string[] = [];
  const client = new SocketClient();
  client.onStatus((s) => statuses.push(s));

  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();
  client.disconnect();

  // No reconnecting status emitted
  expect(statuses).not.toContain('reconnecting');
  expect(statuses.at(-1)).toBe('disconnected');
});

// TC-31: unexpected close triggers reconnect with backoff
test('TC-31: unexpected close schedules reconnect', () => {
  const statuses: string[] = [];
  const client = new SocketClient();
  client.onStatus((s) => statuses.push(s));

  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();
  FakeWebSocket.latest().simulateClose();

  // After close, reconnecting status emitted
  expect(statuses).toContain('reconnecting');
  expect(FakeWebSocket._instances).toHaveLength(1); // not opened yet

  jest.advanceTimersByTime(1_100);
  expect(FakeWebSocket._instances).toHaveLength(2); // new WS opened
});

// TC-32: reconnect attempt counter increments
test('TC-32: reconnect attempt counter increments', () => {
  const client = new SocketClient();

  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();
  expect(client.currentReconnectAttempt).toBe(0);

  // Simulate close → schedule → open again → close again (no open this time)
  FakeWebSocket.latest().simulateClose();
  expect(client.currentReconnectAttempt).toBe(1);
});

// TC-33: after max attempts, status becomes 'failed'
test('TC-33: status becomes failed after exhausting all attempts', () => {
  const statuses: string[] = [];
  const client = new SocketClient();
  client.onStatus((s) => statuses.push(s));

  // Initial connect succeeds, then immediately closes
  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();  // reset attempt to 0
  FakeWebSocket.latest().simulateClose(); // attempt 0→1, delay 1s

  jest.advanceTimersByTime(1_100); // retry 1 fires (opens new WS)
  FakeWebSocket.latest().simulateClose(); // attempt 1→2, delay 2s

  jest.advanceTimersByTime(2_100); // retry 2 fires
  FakeWebSocket.latest().simulateClose(); // attempt 2→3, delay 4s

  jest.advanceTimersByTime(4_100); // retry 3 fires
  FakeWebSocket.latest().simulateClose(); // attempt 3 >= 3 → 'failed'

  expect(statuses).toContain('failed');
});

// TC-34: onStatus and onMessage return unsubscribe functions
test('TC-34: listener unsubscribe removes listener', () => {
  const messages: unknown[] = [];
  const client = new SocketClient();
  const unsub = client.onMessage((e) => messages.push(e));

  client.connect('tbl_1', 'tok');
  FakeWebSocket.latest().simulateOpen();
  FakeWebSocket.latest().simulateMessage({ type: 'PONG', payload: {} });

  unsub();

  FakeWebSocket.latest().simulateMessage({ type: 'PONG', payload: {} });
  expect(messages).toHaveLength(1); // second message not received
});
