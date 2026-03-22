import { StyleSheet, Text, View } from 'react-native';
import type { PlayerViewDTO } from '../../ws/types';

interface PlayerListProps {
  players: PlayerViewDTO[];
  myUserId: string;
  currentActorId: string | null;
  lastActions: Record<string, string>;
}

export default function PlayerList({ players, myUserId, currentActorId, lastActions }: PlayerListProps) {
  return (
    <View>
      <Text style={styles.sectionTitle}>Players</Text>
      {players.map((p) => {
        const isActor = p.user_id === currentActorId;
        const isMe = p.user_id === myUserId;
        const isDimmed = p.status === 'sit_out' || p.status === 'disconnected';
        const showCardBacks = p.status === 'playing' && p.user_id !== myUserId;
        const borderColor = isActor ? '#EAB308' : isMe ? '#2563EB' : 'transparent';
        const lastAction = lastActions[p.user_id] ?? null;

        return (
          <View
            key={p.user_id}
            style={[styles.row, { borderColor, borderWidth: 1, opacity: isDimmed ? 0.5 : 1 }]}
          >
            <View style={styles.left}>
              <View style={styles.nameRow}>
                <Text style={styles.name}>{p.display_name}</Text>
                {p.is_dealer && (
                  <View style={styles.dealerBadge}>
                    <Text style={styles.dealerText}>D</Text>
                  </View>
                )}
                {p.rebuy_count > 0 && (
                  <View style={styles.rebuyBadge}>
                    <Text style={styles.rebuyText}>
                      {p.rebuy_count === 1 ? 'rebuy' : `rebuy +${p.rebuy_count - 1}`}
                    </Text>
                  </View>
                )}
                {lastAction && (
                  <View style={[styles.actionBadge, actionBadgeStyle(lastAction)]}>
                    <Text style={styles.actionText}>{lastAction}</Text>
                  </View>
                )}
              </View>
              <Text style={styles.stack}>
                {p.stack} chips{p.current_bet > 0 ? ` · bet ${p.current_bet}` : ''}
              </Text>
            </View>
            <View style={styles.right}>
              {showCardBacks && (
                <View style={styles.cardBackRow}>
                  <View style={styles.cardBack} />
                  <View style={styles.cardBack} />
                </View>
              )}
              <View style={styles.statusBadge}>
                <Text style={[styles.statusText, statusColor(p.status)]}>{p.status}</Text>
              </View>
            </View>
          </View>
        );
      })}
    </View>
  );
}

function statusColor(status: string) {
  switch (status) {
    case 'playing': return { color: '#86EFAC' };
    case 'sit_out': return { color: '#94A3B8' };
    case 'disconnected': return { color: '#F87171' };
    default: return { color: '#94A3B8' };
  }
}

function actionBadgeStyle(label: string): object {
  if (label === 'Fold') return { backgroundColor: '#374151' };
  if (label === 'Check') return { backgroundColor: '#1D4ED8' };
  if (label.startsWith('Call')) return { backgroundColor: '#065F46' };
  if (label.startsWith('Raise')) return { backgroundColor: '#7C2D12' };
  if (label === 'All-in') return { backgroundColor: '#7C3AED' };
  return { backgroundColor: '#374151' };
}

const styles = StyleSheet.create({
  sectionTitle: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1,
    marginBottom: 8,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
  },
  left: { flex: 1 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  name: { color: '#F8FAFC', fontWeight: '600', fontSize: 15 },
  dealerBadge: {
    backgroundColor: '#B45309',
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  dealerText: { color: '#FEF3C7', fontWeight: '700', fontSize: 11 },
  rebuyBadge: {
    backgroundColor: '#1E3A5F',
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  rebuyText: { color: '#93C5FD', fontWeight: '600', fontSize: 11 },
  actionBadge: {
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  actionText: { color: '#F8FAFC', fontWeight: '600', fontSize: 11 },
  stack: { color: '#64748B', fontSize: 12, marginTop: 2 },
  right: { alignItems: 'flex-end', gap: 4 },
  cardBackRow: { flexDirection: 'row', gap: 4 },
  cardBack: {
    width: 18,
    height: 26,
    backgroundColor: '#1D4ED8',
    borderRadius: 3,
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  statusBadge: {},
  statusText: { fontSize: 11, fontWeight: '600' },
});
