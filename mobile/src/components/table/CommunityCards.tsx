import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';
import CardChip from './CardChip';

interface CommunityCardsProps {
  cards: CardDTO[];
  phase: string;
}

export default function CommunityCards({ cards }: CommunityCardsProps) {
  return (
    <View style={styles.container}>
      {cards.length === 0 ? (
        <Text style={styles.waiting}>Waiting for flop…</Text>
      ) : (
        <View style={styles.row}>
          {cards.map((card, i) => (
            <CardChip key={i} card={card} size="md" />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
    alignItems: 'center',
  },
  row: { flexDirection: 'row', gap: 8 },
  waiting: { color: '#64748B', fontSize: 14 },
});
