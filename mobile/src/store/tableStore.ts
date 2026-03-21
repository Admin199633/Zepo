import { AppState, type AppStateStatus } from 'react-native';
import { create } from 'zustand';
import { SocketClient } from '../ws/SocketClient';
import { TableLogger } from '../utils/logger';
import type {
  BackendStateSnapshotDTO,
  ConnectionStatus,
  HandEndedPayload,
  HandViewDTO,
  PlayerViewDTO,
  StateSnapshotDTO,
} from '../ws/types';

interface TableState {
  connectionStatus: ConnectionStatus;
  reconnectAttempt: number;
  gameState: StateSnapshotDTO | null;
  handResult: HandEndedPayload | null;
  joinPending: boolean;
  error: string | null;
  // Per-player last action label for the current hand (reset on new hand).
  // Key: user_id, Value: formatted label e.g. "Fold", "Check", "Call 5", "Raise 20", "All-in"
  lastActions: Record<string, string>;

  connect: (tableId: string, token: string) => void;
  disconnect: () => void;
  sendJoin: (role: 'player' | 'watcher') => void;
  sendSyncRequest: () => void;
  sendSitIn: () => void;
  sendSitOut: () => void;
  sendAction: (type: 'FOLD' | 'CHECK' | 'CALL' | 'RAISE', amount?: number) => void;
  clearHandResult: () => void;
  reset: () => void;
}

// Singleton socket client shared across table sessions
const socketClient = new SocketClient();

export const useTableStore = create<TableState>((set, get) => {
  // Register persistent listeners
  socketClient.onStatus((status) => {
    set({
      connectionStatus: status,
      reconnectAttempt: socketClient.currentReconnectAttempt,
    });
  });

  socketClient.onMessage((envelope) => {
    if (envelope.type === 'STATE_SNAPSHOT') {
      const raw = envelope.payload as unknown as BackendStateSnapshotDTO;
      // Extract our user_id from the dev token format "dev_{user_id}"
      const yourUserId = savedToken
        ? savedToken.startsWith('dev_')
          ? savedToken.slice(4)
          : savedToken
        : '';

      // Transform players dict → array
      const players: PlayerViewDTO[] = Object.values(raw.players).map((p) => ({
        user_id: p.user_id,
        display_name: p.display_name,
        status: p.status,
        stack: p.stack,
        seat: p.seat_index,
        is_dealer: raw.hand != null && raw.hand.dealer_seat === p.seat_index,
        hole_cards: raw.hand?.hole_cards[p.user_id] ?? null,
        current_bet: raw.hand?.betting.bets_by_player[p.user_id] ?? 0,
        reserve_until: null,
      }));

      // Transform hand
      let currentHand: HandViewDTO | null = null;
      if (raw.hand) {
        const h = raw.hand;
        const currentActorId =
          h.current_turn_seat != null
            ? raw.seat_map[String(h.current_turn_seat)] ?? null
            : null;

        // call_amount is player-specific: how much this player owes to stay in.
        // Using raw current_bet directly would show wrong value for BB (who already posted).
        const myBetThisRound = h.betting.bets_by_player[yourUserId] ?? 0;
        const callAmount = Math.max(0, h.betting.current_bet - myBetThisRound);

        // max_raise: effective stack cap = min(my total, max any active opponent can match).
        // Prevents the slider from showing uncontestable raise amounts.
        const myRawPlayer = raw.players[yourUserId];
        const myLegalMax = (myRawPlayer?.stack ?? 0) + myBetThisRound;
        const activeOpponents = Object.values(raw.players).filter(
          (p) => p.user_id !== yourUserId && p.status === 'active'
        );
        let maxRaise = myLegalMax;
        if (activeOpponents.length > 0) {
          const maxOpponentTotal = Math.max(
            ...activeOpponents.map(
              (p) => (h.betting.bets_by_player[p.user_id] ?? 0) + p.stack
            )
          );
          maxRaise = Math.min(myLegalMax, maxOpponentTotal);
        }

        // live_pot: committed pots + current-street bets — updates after every action
        const livePot =
          h.pots.reduce((s, p) => s + p.amount, 0) +
          Object.values(h.betting.bets_by_player).reduce((s, b) => s + b, 0);

        currentHand = {
          hand_id: h.hand_id,
          hand_number: raw.hand_number,
          phase: h.phase,
          community_cards: h.community_cards,
          pots: h.pots,
          current_actor_id: currentActorId,
          turn_deadline: h.turn_deadline,
          turn_seconds_remaining: h.turn_seconds_remaining ?? null,
          min_raise: h.betting.min_raise_to,
          call_amount: callAmount,
          max_raise: maxRaise,
          live_pot: livePot,
        };
      }

      const snap: StateSnapshotDTO = {
        table_id: raw.table_id,
        players,
        current_hand: currentHand,
        your_user_id: yourUserId,
      };
      TableLogger.log('STATE_SNAPSHOT', { hand: snap.current_hand?.hand_number ?? null });
      set({ gameState: snap, joinPending: false, error: null });
    } else if (envelope.type === 'HAND_RESULT') {
      const raw = envelope.payload as {
        hand_id?: string;
        hand_number?: number;
        winners?: Array<{ user_id: string; amount: number; hand_description: string }>;
        final_board?: Array<{ rank: string; suit: string }>;
        showdown_hands?: Array<{
          user_id: string;
          hole_cards: Array<{ rank: string; suit: string }>;
          hand_description: string;
        }>;
        pot_total?: number;
      };
      TableLogger.log('HAND_RESULT');
      const result: HandEndedPayload = {
        hand_id: raw.hand_id ?? '',
        hand_number: raw.hand_number ?? 0,
        winners: (raw.winners ?? []).map((w) => ({
          user_id: w.user_id,
          amount: w.amount,
          hand_description: w.hand_description,
        })),
        final_board: raw.final_board ?? [],
        showdown_hands: (raw.showdown_hands ?? []).map((s) => ({
          user_id: s.user_id,
          hole_cards: s.hole_cards,
          hand_description: s.hand_description,
        })),
        pot_total: raw.pot_total ?? 0,
      };
      set({ handResult: result });
    } else if (envelope.type === 'PLAYER_ACTED') {
      // Keep call_amount and min_raise current so ActionBar always shows correct options.
      // Also track the last action label for each player's row in PlayerList.
      const newCurrentBet = envelope.payload['new_current_bet'] as number | undefined;
      const newMinRaise = envelope.payload['min_raise_to'] as number | undefined;
      const actingUserId = (envelope.payload['user_id'] as string | undefined) ?? '';
      const action = (envelope.payload['action'] as string | undefined) ?? '';
      const amount = (envelope.payload['amount'] as number | undefined) ?? 0;

      // Build human-readable action label.
      // - call: show chips added ("Call 5")
      // - raise: show the new total bet level ("Raise 20"), not the increment
      // - all_in: flat label (amount is ambiguous context-dependent)
      let actionLabel = '';
      switch (action) {
        case 'fold':   actionLabel = 'Fold'; break;
        case 'check':  actionLabel = 'Check'; break;
        case 'call':   actionLabel = `Call ${amount}`; break;
        case 'raise':  actionLabel = `Raise ${newCurrentBet ?? amount}`; break;
        case 'all_in': actionLabel = 'All-in'; break;
      }

      const potTotal = envelope.payload['pot_total'] as number | undefined;
      const current = get().gameState;
      const updates: Partial<TableState> = {};

      if (actingUserId && actionLabel) {
        updates.lastActions = { ...get().lastActions, [actingUserId]: actionLabel };
      }

      if (current?.current_hand && newCurrentBet !== undefined) {
        updates.gameState = {
          ...current,
          current_hand: {
            ...current.current_hand,
            call_amount: newCurrentBet,
            min_raise: newMinRaise ?? current.current_hand.min_raise,
            ...(potTotal !== undefined ? { live_pot: potTotal } : {}),
          },
        };
      }

      if (Object.keys(updates).length > 0) {
        set(updates);
      }
    } else if (envelope.type === 'TURN_CHANGED') {
      // TURN_CHANGED now carries player-specific call_amount, min_raise_to, and max_raise.
      // These are the authoritative values for the acting player's current action options.
      const actorId = envelope.payload['user_id'] as string | undefined ?? null;
      const deadline = envelope.payload['deadline'] as number | undefined ?? null;
      const secsRemaining = envelope.payload['seconds_remaining'] as number | undefined ?? null;
      const callAmount = (envelope.payload['call_amount'] as number | undefined) ?? 0;
      const minRaiseTo = envelope.payload['min_raise_to'] as number | undefined;
      const maxRaise = envelope.payload['max_raise'] as number | undefined;
      const current = get().gameState;
      if (current?.current_hand) {
        TableLogger.log('TURN_CHANGED', { actorId, secsRemaining, callAmount });
        set({
          gameState: {
            ...current,
            current_hand: {
              ...current.current_hand,
              current_actor_id: actorId,
              turn_deadline: deadline,
              turn_seconds_remaining: secsRemaining,
              call_amount: callAmount,
              min_raise: minRaiseTo ?? current.current_hand.min_raise,
              max_raise: maxRaise ?? current.current_hand.max_raise,
            },
          },
        });
      }
    } else if (envelope.type === 'PHASE_CHANGED') {
      const phase = envelope.payload['phase'] as string | undefined;
      const phasePotTotal = envelope.payload['pot_total'] as number | undefined;
      const current = get().gameState;
      if (current?.current_hand) {
        // Update phase and clear per-turn state so no stale action bar or timer shows.
        // Also reset call_amount to 0 — a new betting street always starts with no pending bet.
        set({
          gameState: {
            ...current,
            current_hand: {
              ...current.current_hand,
              phase: phase ?? current.current_hand.phase,
              current_actor_id: null,
              turn_deadline: null,
              turn_seconds_remaining: null,
              call_amount: 0,
              ...(phasePotTotal !== undefined ? { live_pot: phasePotTotal } : {}),
            },
          },
        });
      }
      if (phase === 'PRE_FLOP') {
        TableLogger.log('PHASE_CHANGED:new_hand');
        // New hand: clear previous hand result and all per-player action labels.
        set({ handResult: null, lastActions: {} });
        // Fetch full hand state — STATE_SNAPSHOT on join predates the hand start
        socketClient.send('SYNC_REQUEST');
      }
    } else if (envelope.type === 'CARDS_DEALT') {
      // Private event — only sent to the player whose cards these are
      const yourCards = envelope.payload['your_cards'] as Array<{ rank: string; suit: string }> | undefined;
      const current = get().gameState;
      if (current && yourCards) {
        const players = current.players.map((p) =>
          p.user_id === current.your_user_id ? { ...p, hole_cards: yourCards } : p
        );
        set({ gameState: { ...current, players } });
      }
    } else if (envelope.type === 'COMMUNITY_CARDS') {
      // Backend sends only the NEW cards for the current street (delta, not full board).
      // Accumulate: append new cards to preserve flop cards through turn and river.
      const newCards = envelope.payload['cards'] as Array<{ rank: string; suit: string }> | undefined;
      const streetPhase = envelope.payload['phase'] as string | undefined;
      const current = get().gameState;
      if (current?.current_hand && newCards) {
        const accumulated = [...current.current_hand.community_cards, ...newCards];
        TableLogger.log('COMMUNITY_CARDS', { street: streetPhase, newCount: newCards.length, total: accumulated.length });
        set({
          gameState: {
            ...current,
            current_hand: {
              ...current.current_hand,
              community_cards: accumulated,
              // Also update phase from the community cards event (belt-and-suspenders with PHASE_CHANGED)
              phase: streetPhase ?? current.current_hand.phase,
            },
          },
        });
      }
    } else if (envelope.type === 'ERROR') {
      const msg =
        (envelope.payload['message'] as string | undefined) ?? 'An error occurred.';
      TableLogger.error('ERROR', { message: msg });
      set({ error: msg });
    }
  });

  // Re-connect / disconnect when app moves to background/foreground
  let savedTableId: string | null = null;
  let savedToken: string | null = null;

  AppState.addEventListener('change', (nextState: AppStateStatus) => {
    if (nextState === 'active' && savedTableId && savedToken) {
      const { connectionStatus } = get();
      if (connectionStatus === 'disconnected') {
        socketClient.connect(savedTableId, savedToken);
      } else if (connectionStatus === 'connected') {
        TableLogger.log('foreground:sendSyncRequest');
        socketClient.send('SYNC_REQUEST');
      }
    } else if (nextState === 'background') {
      socketClient.disconnect();
    }
  });

  return {
    connectionStatus: 'disconnected',
    reconnectAttempt: 0,
    gameState: null,
    handResult: null,
    joinPending: false,
    error: null,
    lastActions: {},

    connect: (tableId, token) => {
      TableLogger.log('connect', { tableId });
      savedTableId = tableId;
      savedToken = token;
      socketClient.connect(tableId, token);
    },

    disconnect: () => {
      TableLogger.log('disconnect');
      savedTableId = null;
      savedToken = null;
      socketClient.disconnect();
      set({ gameState: null, handResult: null, joinPending: false, lastActions: {} });
    },

    sendJoin: (role) => {
      TableLogger.log('sendJoin', { role });
      set({ joinPending: true });
      const wsRole = role === 'watcher' ? 'spectator' : 'player';
      socketClient.send('JOIN_TABLE', { role: wsRole });
    },

    sendSyncRequest: () => {
      TableLogger.log('sendSyncRequest');
      socketClient.send('SYNC_REQUEST');
    },

    sendSitIn: () => {
      socketClient.send('SIT_IN');
    },

    sendSitOut: () => {
      socketClient.send('SIT_OUT');
    },

    sendAction: (type, amount) => {
      TableLogger.log('sendAction', { type, amount });
      socketClient.send('ACTION', {
        action: type.toLowerCase(),
        amount: amount ?? 0,
      });
    },

    clearHandResult: () => set({ handResult: null }),

    reset: () => {
      TableLogger.log('reset');
      socketClient.disconnect();
      savedTableId = null;
      savedToken = null;
      set({
        connectionStatus: 'disconnected',
        reconnectAttempt: 0,
        gameState: null,
        handResult: null,
        joinPending: false,
        error: null,
        lastActions: {},
      });
    },
  };
});
