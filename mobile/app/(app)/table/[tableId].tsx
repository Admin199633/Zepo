import { useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Keyboard,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import ActionBar from '../../../src/components/table/ActionBar';
import ConnectionBanner from '../../../src/components/table/ConnectionBanner';
import CommunityCards from '../../../src/components/table/CommunityCards';
import HandInfoBar from '../../../src/components/table/HandInfoBar';
import HandResultOverlay from '../../../src/components/table/HandResultOverlay';
import MyHoleCards from '../../../src/components/table/MyHoleCards';
import PlayerList from '../../../src/components/table/PlayerList';
import RoleBadge from '../../../src/components/table/RoleBadge';
import { useAuthStore } from '../../../src/store/authStore';
import { useTableStore } from '../../../src/store/tableStore';
import type { ConnectionStatus } from '../../../src/ws/types';

const ACTION_BAR_HEIGHT = 80;

export default function TableScreen() {
  const { tableId } = useLocalSearchParams<{ tableId: string }>();
  const { token, userId } = useAuthStore();
  const {
    connectionStatus,
    reconnectAttempt,
    gameState,
    handResult,
    joinPending,
    lastActions,
    sendJoin,
    sendSyncRequest,
    sendAction,
    sendRebuy,
    sendChat,
    chatMessages,
    connect,
    disconnect,
    clearHandResult,
  } = useTableStore();

  const insets = useSafeAreaInsets();
  const [roleModalVisible, setRoleModalVisible] = useState(false);
  const [joined, setJoined] = useState(false);
  const [joinedRole, setJoinedRole] = useState<'player' | 'watcher' | null>(null);
  const [showReconnectedBanner, setShowReconnectedBanner] = useState(false);
  const [secsLeft, setSecsLeft] = useState<number | null>(null);
  const [rebuyModalVisible, setRebuyModalVisible] = useState(false);
  const [rebuyInput, setRebuyInput] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const prevStatusRef = useRef<ConnectionStatus>('disconnected');

  // Connect when screen is focused, disconnect when it loses focus.
  // useFocusEffect is not affected by React 18 StrictMode's double-invoke,
  // which would otherwise call disconnect() on the cleanup of the first run.
  useFocusEffect(
    useCallback(() => {
      if (tableId && token) {
        connect(tableId, token);
      }
      return () => {
        disconnect();
      };
    }, [tableId, token])
  );

  // Show role picker once connected (first time only)
  useEffect(() => {
    if (connectionStatus === 'connected' && !joined) {
      setRoleModalVisible(true);
    }
  }, [connectionStatus]);

  // Re-send JOIN on reconnect, show green banner
  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = connectionStatus;

    if (
      connectionStatus === 'connected' &&
      (prev === 'reconnecting' || prev === 'connecting') &&
      joinedRole !== null
    ) {
      sendJoin(joinedRole);
      sendSyncRequest();
      setShowReconnectedBanner(true);
      const bannerTimer = setTimeout(() => setShowReconnectedBanner(false), 2000);
      return () => clearTimeout(bannerTimer);
    }
  }, [connectionStatus]);

  // Countdown timer — counts down from server-provided seconds_remaining using
  // client-side elapsed time. This eliminates clock-skew between server and phone.
  // Re-runs whenever turn_deadline changes (unique per turn, even if secs value repeats).
  const turnDeadline = gameState?.current_hand?.turn_deadline ?? null;
  const turnSecsRemaining = gameState?.current_hand?.turn_seconds_remaining ?? null;
  useEffect(() => {
    if (turnDeadline == null || turnSecsRemaining == null) {
      setSecsLeft(null);
      return;
    }
    const startMs = Date.now();
    const initialSecs = turnSecsRemaining;
    const tick = () => {
      const elapsed = (Date.now() - startMs) / 1000;
      setSecsLeft(Math.max(0, Math.round(initialSecs - elapsed)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [turnDeadline]); // turnDeadline is unique per turn — correct re-trigger key

  const handleRoleSelect = (role: 'player' | 'watcher') => {
    setRoleModalVisible(false);
    setJoined(true);
    setJoinedRole(role);
    sendJoin(role);
  };

  // Derived state
  const myPlayer = gameState?.players.find((p) => p.user_id === gameState.your_user_id) ?? null;
  const myStatus = myPlayer?.status ?? null;
  const isMyTurn = gameState?.current_hand?.current_actor_id === gameState?.your_user_id;
  const isPlaying = myStatus === 'active' || myStatus === 'all_in';
  const handInProgress = gameState?.current_hand != null;
  const canAct = Boolean(isMyTurn && isPlaying && handInProgress && connectionStatus === 'connected');
  const isSeated = myPlayer !== null && joinedRole === 'player';
  const canRebuy = isSeated && !handInProgress && connectionStatus === 'connected';
  const maxRebuyAmount = myPlayer ? myPlayer.original_buy_in >> 1 : 0;
  const totalPot = gameState?.current_hand?.live_pot ?? 0;
  const showMyCards = (myPlayer?.hole_cards?.length ?? 0) > 0;
  const scrollPaddingBottom = canAct ? ACTION_BAR_HEIGHT + insets.bottom + 16 : 16;

  return (
    <View style={styles.container}>
      {/* Reconnected flash banner */}
      {showReconnectedBanner && (
        <View style={styles.reconnectedBanner}>
          <Text style={styles.reconnectedText}>Back online</Text>
        </View>
      )}

      <ConnectionBanner
        status={connectionStatus}
        attempt={reconnectAttempt}
        maxAttempts={3}
        onRetry={() => connect(tableId!, token!)}
      />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.tableId} numberOfLines={1}>
          Table {tableId}
        </Text>
        {myStatus && <RoleBadge status={myStatus} />}
      </View>

      {/* Sit-out banner */}
      {myStatus === 'sit_out' && (
        <TouchableOpacity
          style={styles.sitInBanner}
          onPress={() => useTableStore.getState().sendSitIn()}
        >
          <Text style={styles.sitInText}>You are sitting out — Tap to rejoin</Text>
        </TouchableOpacity>
      )}

      {/* Rebuy button — between hands only */}
      {canRebuy && (
        <TouchableOpacity
          style={styles.rebuyBanner}
          onPress={() => { setRebuyInput(String(maxRebuyAmount)); setRebuyModalVisible(true); }}
        >
          <Text style={styles.rebuyBannerText}>Rebuy (max {maxRebuyAmount})</Text>
        </TouchableOpacity>
      )}

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.scrollContent, { paddingBottom: scrollPaddingBottom }]}
      >
        {gameState ? (
          <>
            {gameState.current_hand ? (
              <>
                <HandInfoBar
                  handNumber={gameState.current_hand.hand_number}
                  phase={gameState.current_hand.phase}
                  totalPot={totalPot}
                />
                <CommunityCards
                  cards={gameState.current_hand.community_cards}
                  phase={gameState.current_hand.phase}
                />
                {secsLeft != null && (
                  <View style={[styles.timerBadge, secsLeft <= 5 && styles.timerBadgeUrgent]}>
                    <Text style={styles.timerText}>{secsLeft}s</Text>
                  </View>
                )}
              </>
            ) : (
              <View style={styles.center}>
                <Text style={styles.muted}>Waiting for next hand…</Text>
              </View>
            )}

            {showMyCards && myPlayer?.hole_cards && (
              <MyHoleCards cards={myPlayer.hole_cards} />
            )}

            <PlayerList
              players={gameState.players}
              myUserId={gameState.your_user_id}
              currentActorId={gameState.current_hand?.current_actor_id ?? null}
              lastActions={lastActions}
            />
          </>
        ) : (
          <View style={styles.center}>
            {joined && connectionStatus === 'connected' ? (
              <>
                <ActivityIndicator color="#2563EB" />
                <Text style={[styles.muted, { marginTop: 12 }]}>Joining table…</Text>
              </>
            ) : (
              <Text style={styles.muted}>
                {connectionStatus === 'connected' ? 'Waiting for game state…' : 'Connecting…'}
              </Text>
            )}
          </View>
        )}
      </ScrollView>

      {/* Sticky action bar */}
      {canAct && gameState?.current_hand && (
        <ActionBar
          callAmount={gameState.current_hand.call_amount}
          minRaise={gameState.current_hand.min_raise}
          maxRaise={gameState.current_hand.max_raise}
          myStack={myPlayer?.stack ?? 0}
          onFold={() => sendAction('FOLD')}
          onCheck={() => sendAction('CHECK')}
          onCall={() => sendAction('CALL')}
          onRaise={(amount) => sendAction('RAISE', amount)}
        />
      )}

      {/* Hand result overlay */}
      {handResult && gameState && (
        <HandResultOverlay
          result={handResult}
          players={gameState.players}
          onDismiss={clearHandResult}
        />
      )}

      {/* Chat panel */}
      {joined && (
        <View style={styles.chatContainer}>
          <TouchableOpacity style={styles.chatToggle} onPress={() => setChatOpen((o) => !o)}>
            <Text style={styles.chatToggleText}>
              {chatOpen ? '▼ Chat' : `▲ Chat${chatMessages.length > 0 ? ` (${chatMessages.length})` : ''}`}
            </Text>
          </TouchableOpacity>
          {chatOpen && (
            <>
              <FlatList
                data={chatMessages}
                keyExtractor={(m) => m.message_id}
                style={styles.chatList}
                contentContainerStyle={{ padding: 8 }}
                renderItem={({ item }) => (
                  <View style={styles.chatRow}>
                    <Text style={styles.chatName}>{item.display_name}: </Text>
                    <Text style={styles.chatMsg}>{item.message}</Text>
                  </View>
                )}
                inverted={false}
              />
              <View style={styles.chatInputRow}>
                <TextInput
                  style={styles.chatInput}
                  placeholder="Message…"
                  placeholderTextColor="#64748B"
                  value={chatInput}
                  onChangeText={setChatInput}
                  maxLength={500}
                  returnKeyType="send"
                  onSubmitEditing={() => {
                    sendChat(chatInput);
                    setChatInput('');
                    Keyboard.dismiss();
                  }}
                />
                <TouchableOpacity
                  style={styles.chatSendBtn}
                  onPress={() => { sendChat(chatInput); setChatInput(''); Keyboard.dismiss(); }}
                >
                  <Text style={styles.chatSendText}>Send</Text>
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>
      )}

      {/* Rebuy modal */}
      <Modal visible={rebuyModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Rebuy</Text>
            <Text style={[styles.muted, { marginBottom: 12, textAlign: 'center' }]}>
              Max {maxRebuyAmount} chips
            </Text>
            <TextInput
              style={styles.rebuyInput}
              keyboardType="number-pad"
              value={rebuyInput}
              onChangeText={setRebuyInput}
              maxLength={8}
            />
            <TouchableOpacity
              style={styles.modalButton}
              onPress={() => {
                const amount = parseInt(rebuyInput, 10);
                if (!isNaN(amount) && amount > 0 && amount <= maxRebuyAmount) {
                  sendRebuy(amount);
                }
                setRebuyModalVisible(false);
              }}
            >
              <Text style={styles.modalButtonText}>Confirm</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modalButton, styles.modalButtonSecondary]}
              onPress={() => setRebuyModalVisible(false)}
            >
              <Text style={[styles.modalButtonText, styles.modalButtonTextSecondary]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Role selection modal */}
      <Modal visible={roleModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>How do you want to join?</Text>
            <TouchableOpacity
              style={styles.modalButton}
              onPress={() => handleRoleSelect('player')}
            >
              <Text style={styles.modalButtonText}>Play</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modalButton, styles.modalButtonSecondary]}
              onPress={() => handleRoleSelect('watcher')}
            >
              <Text style={[styles.modalButtonText, styles.modalButtonTextSecondary]}>
                Watch
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0F172A' },
  reconnectedBanner: { backgroundColor: '#166534', paddingVertical: 6, paddingHorizontal: 16 },
  reconnectedText: { color: '#86EFAC', fontWeight: '600', textAlign: 'center', fontSize: 13 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  tableId: { color: '#94A3B8', fontSize: 13, flex: 1 },
  sitInBanner: { backgroundColor: '#7C3AED', paddingVertical: 10, paddingHorizontal: 16 },
  sitInText: { color: '#fff', fontWeight: '600', textAlign: 'center' },
  rebuyBanner: { backgroundColor: '#1E3A5F', paddingVertical: 10, paddingHorizontal: 16, borderTopWidth: 1, borderTopColor: '#3B82F6' },
  rebuyBannerText: { color: '#93C5FD', fontWeight: '600', textAlign: 'center' },
  rebuyInput: {
    backgroundColor: '#0F172A',
    color: '#F8FAFC',
    borderRadius: 8,
    padding: 12,
    fontSize: 18,
    width: '100%',
    marginBottom: 12,
    textAlign: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  chatContainer: { borderTopWidth: 1, borderTopColor: '#1E293B', backgroundColor: '#0F172A' },
  chatToggle: { paddingHorizontal: 16, paddingVertical: 8 },
  chatToggleText: { color: '#64748B', fontSize: 13, fontWeight: '600' },
  chatList: { maxHeight: 140 },
  chatRow: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 4 },
  chatName: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },
  chatMsg: { color: '#CBD5E1', fontSize: 12, flexShrink: 1 },
  chatInputRow: { flexDirection: 'row', padding: 8, gap: 8 },
  chatInput: { flex: 1, backgroundColor: '#1E293B', color: '#F8FAFC', borderRadius: 8, padding: 10, fontSize: 14 },
  chatSendBtn: { backgroundColor: '#2563EB', borderRadius: 8, paddingHorizontal: 14, justifyContent: 'center' },
  chatSendText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  scroll: { flex: 1 },
  scrollContent: { padding: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  muted: { color: '#64748B', fontSize: 15 },
  // Turn timer
  timerBadge: {
    alignSelf: 'center',
    backgroundColor: '#1E293B',
    borderRadius: 20,
    paddingVertical: 6,
    paddingHorizontal: 18,
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  timerBadgeUrgent: { backgroundColor: '#7F1D1D', borderColor: '#EF4444' },
  timerText: { color: '#F8FAFC', fontWeight: '700', fontSize: 18 },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 28,
    width: '80%',
    alignItems: 'center',
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: '#F8FAFC', marginBottom: 20 },
  modalButton: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    paddingVertical: 14,
    paddingHorizontal: 32,
    width: '100%',
    alignItems: 'center',
    marginBottom: 10,
  },
  modalButtonSecondary: { backgroundColor: 'transparent', borderWidth: 1, borderColor: '#334155' },
  modalButtonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  modalButtonTextSecondary: { color: '#94A3B8' },
});
