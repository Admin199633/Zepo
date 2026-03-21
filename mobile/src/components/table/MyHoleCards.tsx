import { StyleSheet, Text, View } from 'react-native';
import type { CardDTO } from '../../ws/types';
import CardChip from './CardChip';

interface MyHoleCardsProps {
  cards: CardDTO[];
}

export default function MyHoleCards({ cards }: MyHoleCardsProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>YOUR CARDS</Text>
      <View style={styles.row}>
        {cards.map((card, i) => (
          <CardChip key={i} card={card} size="md" />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  label: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    marginBottom: 8,
  },
  row: { flexDirection: 'row', gap: 8 },
});
