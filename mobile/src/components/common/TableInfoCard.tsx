import { StyleSheet, Text, View } from 'react-native';
import type { TableConfigDTO } from '../../api/types';

interface TableInfoCardProps {
  config: TableConfigDTO;
}

export default function TableInfoCard({ config }: TableInfoCardProps) {
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.label}>Blinds</Text>
        <Text style={styles.value}>
          {config.small_blind} / {config.big_blind}
        </Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Starting stack</Text>
        <Text style={styles.value}>{config.starting_stack}</Text>
      </View>
      <View style={styles.row}>
        <Text style={styles.label}>Max players</Text>
        <Text style={styles.value}>{config.max_players}</Text>
      </View>
      {config.house_rules.length > 0 && (
        <View style={styles.row}>
          <Text style={styles.label}>House rules</Text>
          <Text style={styles.value}>{config.house_rules.join(', ')}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 16,
    marginTop: 16,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  label: { color: '#94A3B8', fontSize: 14 },
  value: { color: '#F8FAFC', fontSize: 14, fontWeight: '600' },
});
