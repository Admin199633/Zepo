import { StyleSheet, Text, View } from 'react-native';

interface RoleBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { label: string; bg: string; color: string }> = {
  waiting: { label: 'Waiting', bg: '#1E293B', color: '#94A3B8' },
  playing: { label: 'Playing', bg: '#166534', color: '#86EFAC' },
  sit_out: { label: 'Sitting Out', bg: '#78350F', color: '#FDE68A' },
  disconnected: { label: 'Disconnected', bg: '#1F2937', color: '#6B7280' },
  watcher: { label: 'Watching', bg: '#1E3A5F', color: '#93C5FD' },
};

export default function RoleBadge({ status }: RoleBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    bg: '#1E293B',
    color: '#94A3B8',
  };

  return (
    <View style={[styles.badge, { backgroundColor: config.bg }]}>
      <Text style={[styles.label, { color: config.color }]}>{config.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  label: { fontSize: 12, fontWeight: '600' },
});
