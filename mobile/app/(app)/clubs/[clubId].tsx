import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import TableInfoCard from '../../../src/components/common/TableInfoCard';
import { useClubStore } from '../../../src/store/clubStore';

export default function ClubDetailScreen() {
  const { clubId, tableId } = useLocalSearchParams<{ clubId: string; tableId?: string }>();
  const router = useRouter();
  const {
    selectedClub,
    tableInfo,
    isLoadingClub,
    isLoadingTable,
    error,
    fetchClub,
    fetchTableInfo,
    clearError,
  } = useClubStore();

  useEffect(() => {
    if (clubId) fetchClub(clubId);
  }, [clubId]);

  useEffect(() => {
    if (selectedClub && clubId) {
      fetchTableInfo(clubId);
    }
  }, [selectedClub, clubId]);

  const handleEnterTable = (tid: string) => {
    router.push({
      pathname: '/(app)/table/[tableId]',
      params: { tableId: tid },
    });
  };

  if (isLoadingClub) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#2563EB" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => { clearError(); if (clubId) fetchClub(clubId); }}>
          <Text style={styles.retryText}>Try again</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!selectedClub) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.name}>{selectedClub.name}</Text>
      <Text style={styles.meta}>{selectedClub.member_count} members</Text>
      <Text style={styles.inviteLabel}>Invite code</Text>
      <Text style={styles.inviteCode}>{selectedClub.invite_code}</Text>

      {isLoadingTable ? (
        <View style={styles.tableInfoPlaceholder}>
          <ActivityIndicator color="#2563EB" />
        </View>
      ) : tableInfo ? (
        <>
          <TableInfoCard config={tableInfo.config} />
          <TouchableOpacity
            style={styles.button}
            onPress={() => handleEnterTable(tableInfo.table_id)}
          >
            <Text style={styles.buttonText}>Enter table</Text>
          </TouchableOpacity>
        </>
      ) : (
        <Text style={styles.muted}>Table info unavailable</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0F172A', padding: 24 },
  center: { flex: 1, backgroundColor: '#0F172A', alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 26, fontWeight: '800', color: '#F8FAFC', marginTop: 16, marginBottom: 4 },
  meta: { color: '#64748B', marginBottom: 24 },
  inviteLabel: { color: '#94A3B8', fontSize: 12, fontWeight: '600', letterSpacing: 1 },
  inviteCode: {
    fontSize: 22,
    fontWeight: '700',
    color: '#38BDF8',
    letterSpacing: 4,
    marginTop: 4,
    marginBottom: 32,
  },
  tableInfoPlaceholder: {
    height: 96,
    alignItems: 'center',
    justifyContent: 'center',
  },
  button: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    marginTop: 16,
  },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  muted: { color: '#64748B', fontSize: 14 },
  errorText: { color: '#F87171', fontSize: 15, marginBottom: 16 },
  retryButton: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 24,
  },
  retryText: { color: '#fff', fontWeight: '600', fontSize: 14 },
});
