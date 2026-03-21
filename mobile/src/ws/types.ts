/**
 * WebSocket message types — typed mirrors of backend WS envelope models.
 * Source of truth: backend/api/ws_router.py, backend/events/
 */

// ---------------------------------------------------------------------------
// Connection status (client-side only)
// ---------------------------------------------------------------------------

export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'failed';

// ---------------------------------------------------------------------------
// Server → Client
// ---------------------------------------------------------------------------

export type ServerEventType =
  | 'STATE_SNAPSHOT'
  | 'PHASE_CHANGED'
  | 'CARDS_DEALT'
  | 'COMMUNITY_CARDS'
  | 'PLAYER_ACTED'
  | 'TURN_CHANGED'
  | 'POT_UPDATED'
  | 'PLAYER_STATUS'
  | 'HAND_RESULT'
  | 'BLINDS_POSTED'
  | 'BONUS_AWARDED'
  | 'CHAT_MESSAGE'
  | 'PLAYER_JOINED'
  | 'PLAYER_LEFT'
  | 'ERROR';

export interface ServerEnvelope {
  type: ServerEventType;
  payload: Record<string, unknown>;
}

export interface CardDTO {
  rank: string;
  suit: string;
}

export interface PlayerViewDTO {
  user_id: string;
  display_name: string;
  status: string; // 'waiting' | 'playing' | 'sit_out' | 'disconnected'
  stack: number;
  seat: number | null;
  is_dealer: boolean;
  hole_cards: CardDTO[] | null;
  current_bet: number;
  reserve_until: number | null;
}

export interface PotDTO {
  amount: number;
  eligible_player_ids: string[];
}

export interface HandViewDTO {
  hand_id: string;
  hand_number: number;
  phase: string;
  community_cards: CardDTO[];
  pots: PotDTO[];
  current_actor_id: string | null;
  turn_deadline: number | null;
  turn_seconds_remaining: number | null; // server-computed at send time; use for countdown
  min_raise: number;
  call_amount: number;   // player-specific: 0 means check is the right action
  max_raise: number;     // effective stack cap for raise slider
  live_pot: number;      // committed pots + current-street bets; updated after every action
}

export interface StateSnapshotDTO {
  table_id: string;
  players: PlayerViewDTO[];
  current_hand: HandViewDTO | null;
  your_user_id: string;
}

// ---------------------------------------------------------------------------
// Client → Server
// ---------------------------------------------------------------------------

export type ClientMessageType =
  | 'JOIN_TABLE'
  | 'LEAVE_TABLE'
  | 'ACTION'
  | 'SIT_OUT'
  | 'SIT_IN'
  | 'SYNC_REQUEST';

export interface ClientEnvelope {
  type: ClientMessageType;
  request_id: string;
  table_id: string;
  payload?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Backend wire format for STATE_SNAPSHOT (transformed before storing in UI state)
// ---------------------------------------------------------------------------

export interface BackendPlayerViewDTO {
  user_id: string;
  display_name: string;
  seat_index: number;
  stack: number;
  status: string;
  is_connected: boolean;
}

export interface BackendBettingStateDTO {
  current_bet: number;
  min_raise_to: number;
  bets_by_player: Record<string, number>;
}

export interface BackendHandViewDTO {
  hand_id: string;
  phase: string;
  hole_cards: Record<string, CardDTO[]>;
  community_cards: CardDTO[];
  pots: PotDTO[];
  betting: BackendBettingStateDTO;
  dealer_seat: number;
  small_blind_seat: number;
  big_blind_seat: number;
  current_turn_seat: number | null;
  turn_deadline: number | null;
  turn_seconds_remaining: number | null;
  winners: unknown[] | null;
}

export interface BackendStateSnapshotDTO {
  table_id: string;
  club_id: string;
  phase: string;
  hand_number: number;
  players: Record<string, BackendPlayerViewDTO>;
  seat_map: Record<string, string>; // "seat_index" → user_id
  config: Record<string, unknown>;
  hand: BackendHandViewDTO | null;
}

// ---------------------------------------------------------------------------
// HAND_ENDED payload (server → client)
// ---------------------------------------------------------------------------

export interface HandEndedWinner {
  user_id: string;
  amount: number;
  hand_description: string;
}

export interface HandEndedShowdownEntry {
  user_id: string;
  hole_cards: CardDTO[];
  hand_description: string;
}

export interface HandEndedPayload {
  hand_id: string;
  hand_number: number;
  winners: HandEndedWinner[];
  final_board: CardDTO[];
  showdown_hands: HandEndedShowdownEntry[];
  pot_total: number;   // total chips in play when hand ended
}
