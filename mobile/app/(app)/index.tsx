import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { getUserClubs } from '../../src/api/clubs';
import type { ClubDTO } from '../../src/api/types';
import { useAuthStore } from '../../src/store/authStore';

export default function ClubsListScreen() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const [clubs, setClubs] = useState<ClubDTO[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUserClubs()
      .then(setClubs)
      .catch(() => {
        // 401 is already handled by the Axios interceptor (triggers logout).
        // Swallow here to prevent an unhandled-rejection dev overlay.
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Clubs</Text>
        <TouchableOpacity onPress={logout}>
          <Text style={styles.logoutText}>Sign out</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}>
          <Text style={styles.muted}>Loading…</Text>
        </View>
      ) : clubs.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>No clubs yet</Text>
          <Text style={styles.emptyBody}>
            Ask a club owner to share their invite code, then enter it below to join.
            {'\n\n'}
            Once you're a member, your club will appear here.
          </Text>
        </View>
      ) : (
        <FlatList
          data={clubs}
          keyExtractor={(item) => item.club_id}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() =>
                router.push({
                  pathname: '/(app)/clubs/[clubId]',
                  params: { clubId: item.club_id },
                })
              }
            >
              <Text style={styles.cardName}>{item.name}</Text>
              <Text style={styles.cardSub}>{item.member_count} members</Text>
            </TouchableOpacity>
          )}
          contentContainerStyle={styles.list}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0F172A' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingTop: 56,
  },
  title: { fontSize: 28, fontWeight: '800', color: '#F8FAFC' },
  logoutText: { color: '#94A3B8', fontSize: 14 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  muted: { color: '#64748B', fontSize: 16 },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#F8FAFC',
    marginBottom: 12,
  },
  emptyBody: {
    color: '#94A3B8',
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
  list: { padding: 16 },
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
  },
  cardName: { fontSize: 18, fontWeight: '700', color: '#F8FAFC' },
  cardSub: { fontSize: 13, color: '#64748B', marginTop: 4 },
});
