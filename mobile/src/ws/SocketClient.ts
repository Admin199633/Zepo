import { WS_BASE_URL } from '../config';
import { SocketLogger } from '../utils/logger';
import type { ClientEnvelope, ClientMessageType, ConnectionStatus, ServerEnvelope } from './types';

const BACKOFF_DELAYS_MS = [1_000, 2_000, 4_000];

type StatusListener = (status: ConnectionStatus) => void;
type MessageListener = (envelope: ServerEnvelope) => void;

function makeRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export class SocketClient {
  private ws: WebSocket | null = null;
  private tableId: string | null = null;
  private token: string | null = null;

  private reconnectAttempt = 0;
  private shouldReconnect = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private statusListeners: Set<StatusListener> = new Set();
  private messageListeners: Set<MessageListener> = new Set();

  connect(tableId: string, token: string): void {
    SocketLogger.log('connect', { tableId });
    this.tableId = tableId;
    this.token = token;
    this.shouldReconnect = true;
    this.reconnectAttempt = 0;
    this._openSocket();
  }

  disconnect(): void {
    SocketLogger.log('disconnect', { voluntary: true });
    this.shouldReconnect = false;
    this._clearReconnectTimer();
    this._closeSocket();
    this._emitStatus('disconnected');
  }

  send(type: ClientMessageType, payload?: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const envelope: ClientEnvelope = {
      type,
      request_id: makeRequestId(),
      table_id: this.tableId ?? '',
      payload,
    };
    this.ws.send(JSON.stringify(envelope));
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  onMessage(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => this.messageListeners.delete(listener);
  }

  get currentReconnectAttempt(): number {
    return this.reconnectAttempt;
  }

  get maxReconnectAttempts(): number {
    return BACKOFF_DELAYS_MS.length;
  }

  private _openSocket(): void {
    if (!this.tableId || !this.token) return;

    SocketLogger.log('_openSocket', { attempt: this.reconnectAttempt, tableId: this.tableId });
    this._closeSocket();
    this._emitStatus(this.reconnectAttempt === 0 ? 'connecting' : 'reconnecting');

    const url = `${WS_BASE_URL}/ws/table/${this.tableId}?token=${encodeURIComponent(this.token)}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      SocketLogger.log('onopen', { tableId: this.tableId });
      this.reconnectAttempt = 0;
      this._emitStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data as string) as ServerEnvelope;
        this.messageListeners.forEach((l) => l(envelope));
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      SocketLogger.log('onclose', {
        shouldReconnect: this.shouldReconnect,
        attempt: this.reconnectAttempt,
      });
      this.ws = null;
      if (!this.shouldReconnect) return;
      this._scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose fires after onerror; reconnect is handled there
    };
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempt >= BACKOFF_DELAYS_MS.length) {
      SocketLogger.warn('max-attempts-reached', { maxAttempts: BACKOFF_DELAYS_MS.length });
      this._emitStatus('failed');
      return;
    }
    const delay = BACKOFF_DELAYS_MS[this.reconnectAttempt];
    this.reconnectAttempt += 1;
    this._emitStatus('reconnecting');
    this.reconnectTimer = setTimeout(() => {
      if (this.shouldReconnect) this._openSocket();
    }, delay);
  }

  private _closeSocket(): void {
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  private _clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private _emitStatus(status: ConnectionStatus): void {
    this.statusListeners.forEach((l) => l(status));
  }
}