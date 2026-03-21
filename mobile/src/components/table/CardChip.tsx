import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';

const SUIT_SYMBOLS: Record<string, string> = {
  s: '♠',
  h: '♥',
  d: '♦',
  c: '♣',
};

const SUIT_COLORS: Record<string, string> = {
  s: '#F8FAFC',
  h: '#EF4444',
  d: '#EF4444',
  c: '#F8FAFC',
};

const SUIT_NAMES: Record<string, string> = {
  s: 'spades',
  h: 'hearts',
  d: 'diamonds',
  c: 'clubs',
};

interface CardChipProps {
  card: CardDTO;
  size?: 'sm' | 'md';
}

export default function CardChip({ card, size = 'md' }: CardChipProps) {
  const width = size === 'sm' ? 32 : 44;
  const height = size === 'sm' ? 44 : 60;
  // Backend sends uppercase suit letters (S, H, D, C); normalize for lookup.
  const suitKey = card.suit.toLowerCase();
  const suitSymbol = SUIT_SYMBOLS[suitKey] ?? card.suit;
  const suitColor = SUIT_COLORS[suitKey] ?? '#F8FAFC';
  const suitName = SUIT_NAMES[suitKey] ?? card.suit;

  return (
    <View
      style={[styles.card, { width, height }]}
      accessibilityLabel={`${card.rank} of ${suitName}`}
      accessibilityRole="text"
    >
      <Text style={styles.rank}>{card.rank}</Text>
      <Text style={[styles.suit, { color: suitColor }]}>{suitSymbol}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
    justifyContent: 'center',
  },
  rank: { color: '#F8FAFC', fontWeight: '700', fontSize: 14 },
  suit: { fontSize: 12 },
});
