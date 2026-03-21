import { useEffect } from 'react';
import { Modal, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { HandEndedPayload, PlayerViewDTO } from '../../ws/types';
import CardChip from './CardChip';

interface HandResultOverlayProps {
  result: HandEndedPayload;
  players: PlayerViewDTO[];
  onDismiss: () => void;
}

export default function HandResultOverlay({ result, players, onDismiss }: HandResultOverlayProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const getName = (userId: string): string =>
    players.find((p) => p.user_id === userId)?.display_name ?? userId;

  return (
    <Modal visible transparent animationType="fade">
      <TouchableOpacity
        style={styles.backdrop}
        activeOpacity={1}
        onPress={onDismiss}
        accessibilityLabel="Hand result, tap to dismiss"
        accessibilityRole="button"
      >
        <View style={styles.card}>
          <Text style={styles.title}>Hand #{result.hand_number} Complete</Text>

          {result.winners.map((w, i) => (
            <View key={i} style={styles.winnerBlock}>
              <Text style={styles.winnerLine}>
                {getName(w.user_id)}{' '}
                <Text style={styles.wins}>wins </Text>
                <Text style={styles.amount}>{w.amount} chips</Text>
              </Text>
              {Boolean(w.hand_description) && (
                <Text style={styles.desc}>{w.hand_description}</Text>
              )}
            </View>
          ))}

          {result.final_board.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>Final Board</Text>
              <View style={styles.cardRow}>
                {result.final_board.map((card, i) => (
                  <CardChip key={i} card={card} size="sm" />
                ))}
              </View>
            </View>
          )}

          {result.showdown_hands.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>Showdown</Text>
              {result.showdown_hands.map((entry, i) => (
                <View key={i} style={styles.showdownEntry}>
                  <Text style={styles.showdownName}>{getName(entry.user_id)}</Text>
                  <View style={styles.cardRow}>
                    {entry.hole_cards.map((card, j) => (
                      <CardChip key={j} card={card} size="sm" />
                    ))}
                  </View>
                  {Boolean(entry.hand_description) && (
                    <Text style={styles.desc}>{entry.hand_description}</Text>
                  )}
                </View>
              ))}
            </View>
          )}

          <Text style={styles.hint}>Tap to dismiss</Text>
        </View>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 16,
    padding: 24,
    width: '85%',
    maxWidth: 340,
  },
  title: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 18,
    textAlign: 'center',
    marginBottom: 16,
  },
  winnerBlock: { marginBottom: 10 },
  winnerLine: { color: '#F8FAFC', fontSize: 15 },
  wins: { color: '#F8FAFC' },
  amount: { color: '#86EFAC', fontWeight: '700' },
  desc: { color: '#94A3B8', fontSize: 13, fontStyle: 'italic', marginTop: 2 },
  section: { marginTop: 14 },
  sectionLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  cardRow: { flexDirection: 'row', gap: 6 },
  showdownEntry: { marginBottom: 10 },
  showdownName: { color: '#F8FAFC', fontSize: 13, marginBottom: 4 },
  hint: { color: '#64748B', fontSize: 12, textAlign: 'center', marginTop: 16 },
});
