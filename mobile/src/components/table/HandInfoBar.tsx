import { StyleSheet, Text, View } from 'react-native';

const PHASE_LABELS: Record<string, string> = {
  PRE_FLOP: 'Pre-Flop',
  FLOP: 'Flop',
  TURN: 'Turn',
  RIVER: 'River',
  SHOWDOWN: 'Showdown',
};

const PHASE_COLORS: Record<string, string> = {
  PRE_FLOP: '#94A3B8',
  FLOP: '#60A5FA',
  TURN: '#34D399',
  RIVER: '#F59E0B',
  SHOWDOWN: '#A78BFA',
};

interface HandInfoBarProps {
  handNumber: number;
  phase: string;
  totalPot: number;
}

export default function HandInfoBar({ handNumber, phase, totalPot }: HandInfoBarProps) {
  const label = PHASE_LABELS[phase] ?? phase;
  const color = PHASE_COLORS[phase] ?? '#94A3B8';

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        <Text style={styles.handNumber}>Hand #{handNumber}</Text>
        <Text style={[styles.phase, { color }]}>{label}</Text>
      </View>
      <Text style={styles.pot}>Pot: {totalPot}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  handNumber: { color: '#F8FAFC', fontWeight: '700', fontSize: 16 },
  phase: { fontWeight: '600', fontSize: 15 },
  pot: { color: '#94A3B8', fontSize: 13 },
});
