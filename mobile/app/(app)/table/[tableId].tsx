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
    actionFeed,
    handHistory,
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
  const [reportOpen, setReportOpen] = useState(false);
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

  // Session stats for Report modal — computed from hand history
  const lastHand = handHistory.length > 0 ? handHistory[handHistory.length - 1] : null;
  const playerSessionStats = (gameState?.players ?? []).map((p) => {
    const played = handHistory.filter((h) => h.player_ids.includes(p.user_id)).length;
    const won = handHistory.filter((h) => h.winner_ids.includes(p.user_id)).length;
    const profit = handHistory.reduce((sum, h) => {
      const before = h.stacks_before?.[p.user_id];
      const after = h.stacks_after?.[p.user_id];
      return before !== undefined && after !== undefined ? sum + (after - before) : sum;
    }, 0);
    const biggestWin = handHistory.reduce((best, h) => {
      const before = h.stacks_before?.[p.user_id];
      const after = h.stacks_after?.[p.user_id];
      const delta = before !== undefined && after !== undefined ? after - before : 0;
      return delta > best ? delta : best;
    }, 0);
    return { ...p, handsPlayed: played, handsWon: won, profit, biggestWin };
  });

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
        {joined && (
          <TouchableOpacity style={styles.reportBtn} onPress={() => setReportOpen(true)}>
            <Text style={styles.reportBtnText}>Report</Text>
          </TouchableOpacity>
        )}
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

      {/* Report modal */}
      <Modal visible={reportOpen} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, styles.reportCard]}>
            <View style={styles.reportHeader}>
              <Text style={styles.modalTitle}>Table Report</Text>
              <TouchableOpacity onPress={() => setReportOpen(false)}>
                <Text style={styles.reportClose}>✕</Text>
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.reportScroll} showsVerticalScrollIndicator={false}>
              {/* Player stats */}
              <Text style={styles.reportSection}>Players</Text>
              {playerSessionStats.map((p) => (
                <View key={p.user_id} style={styles.reportPlayerCard}>
                  <View style={styles.reportRow}>
                    <Text style={styles.reportName} numberOfLines={1}>{p.display_name}</Text>
                    <Text style={styles.reportStat}>{p.stack} chips</Text>
                  </View>
                  {handHistory.length > 0 && (
                    <View style={styles.reportStatRow}>
                      <Text style={styles.reportStatLabel}>{p.handsWon}/{p.handsPlayed} hands</Text>
                      <Text style={[styles.reportStatLabel, p.profit >= 0 ? styles.reportProfit : styles.reportLoss]}>
                        {p.profit >= 0 ? '+' : ''}{p.profit}
                      </Text>
                      {p.biggestWin > 0 && (
                        <Text style={styles.reportStatLabel}>best +{p.biggestWin}</Text>
                      )}
                    </View>
                  )}
                </View>
              ))}

              {/* Pot breakdown */}
              <Text style={styles.reportSection}>Pot</Text>
              {gameState?.current_hand ? (
                <>
                  <Text style={styles.reportPot}>Total: {gameState.current_hand.live_pot}</Text>
                  {gameState.players.filter((p) => p.current_bet > 0).map((p) => (
                    <View key={p.user_id} style={styles.reportHistoryRow}>
                      <Text style={styles.reportHistoryNum} numberOfLines={1}>{p.display_name}</Text>
                      <Text style={styles.reportHistoryDetail}>{p.current_bet} in</Text>
                    </View>
                  ))}
                </>
              ) : lastHand ? (
                <>
                  <Text style={styles.reportPot}>Hand #{lastHand.hand_number} · {lastHand.pot_total} total</Text>
                  {lastHand.player_ids.map((uid) => {
                    const before = lastHand.stacks_before?.[uid] ?? 0;
                    const after = lastHand.stacks_after?.[uid] ?? 0;
                    const delta = after - before;
                    const name = gameState?.players.find((p) => p.user_id === uid)?.display_name ?? uid.slice(0, 8);
                    return (
                      <View key={uid} style={styles.reportHistoryRow}>
                        <Text style={styles.reportHistoryNum} numberOfLines={1}>{name}</Text>
                        <Text style={[styles.reportHistoryDetail, delta >= 0 ? styles.reportProfit : styles.reportLoss]}>
                          {delta >= 0 ? '+' : ''}{delta}
                        </Text>
                      </View>
                    );
                  })}
                </>
              ) : (
                <Text style={styles.reportHistoryDetail}>No hand data yet</Text>
              )}

              {/* Hand history */}
              {handHistory.length > 0 && (
                <>
                  <Text style={styles.reportSection}>Recent Hands</Text>
                  {[...handHistory].reverse().slice(0, 5).map((h) => (
                    <View key={h.hand_number} style={[styles.reportHistoryRow, { flexDirection: 'column', alignItems: 'flex-start', gap: 2 }]}>
                      <Text style={styles.reportHistoryDetail}>
                        #{h.hand_number} · pot {h.pot_total} · {h.winner_names.join(', ')}
                      </Text>
                      {(h.community_cards?.length ?? 0) > 0 && (
                        <Text style={styles.reportHistoryNum}>
                          {h.community_cards.map((c) => c.rank + c.suit.slice(0, 1).toLowerCase()).join(' ')}
                        </Text>
                      )}
                    </View>
                  ))}
                </>
              )}

              {/* Action feed */}
              {actionFeed.length > 0 && (
                <>
                  <Text style={styles.reportSection}>Recent Actions</Text>
                  {[...actionFeed].reverse().map((entry, i) => (
                    <Text key={i} style={[styles.reportFeedEntry, entry.type === 'action' ? styles.reportFeedAction : styles.reportFeedSystem]}>
                      {entry.text}
                    </Text>
                  ))}
                </>
              )}
            </ScrollView>
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
  // Report button
  reportBtn: { backgroundColor: '#1E293B', borderRadius: 8, paddingVertical: 5, paddingHorizontal: 12, marginRight: 8 },
  reportBtnText: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },
  // Report modal
  reportCard: { width: '92%', maxHeight: '80%', padding: 20 },
  reportHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  reportClose: { color: '#64748B', fontSize: 20, paddingLeft: 16 },
  reportScroll: { flexGrow: 0 },
  reportSection: { color: '#64748B', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1, marginTop: 16, marginBottom: 6 },
  reportRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#1E293B', gap: 8 },
  reportName: { flex: 1, color: '#F8FAFC', fontSize: 14 },
  reportStat: { color: '#94A3B8', fontSize: 13, minWidth: 60, textAlign: 'right' },
  reportPot: { color: '#F8FAFC', fontSize: 15, fontWeight: '600', paddingVertical: 4 },
  reportHistoryRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 4, gap: 8 },
  reportHistoryNum: { color: '#64748B', fontSize: 12, minWidth: 36 },
  reportHistoryDetail: { color: '#CBD5E1', fontSize: 13, flex: 1 },
  reportFeedEntry: { fontSize: 13, paddingVertical: 3, borderBottomWidth: 1, borderBottomColor: '#1E293B' },
  reportFeedAction: { color: '#CBD5E1' },
  reportFeedSystem: { color: '#64748B', fontStyle: 'italic' },
  reportProfit: { color: '#4ADE80' },
  reportLoss: { color: '#F87171' },
  reportPlayerCard: { marginBottom: 2 },
  reportStatRow: { flexDirection: 'row', gap: 12, paddingBottom: 6, paddingLeft: 2 },
  reportStatLabel: { color: '#64748B', fontSize: 12 },
});
