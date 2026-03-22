import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  FlatList,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { createClub, getUserClubs, joinClub } from '../../src/api/clubs';
import { extractErrorMessage } from '../../src/api/client';
import type { ClubDTO } from '../../src/api/types';
import { useAuthStore } from '../../src/store/authStore';

export default function ClubsListScreen() {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const displayName = useAuthStore((s) => s.displayName);
  const isAdmin = displayName === 'Admin';
  const [clubs, setClubs] = useState<ClubDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteCode, setInviteCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [clubName, setClubName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createResult, setCreateResult] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  // Table config state
  const [cfgStack, setCfgStack] = useState('1000');
  const [cfgSB, setCfgSB] = useState('5');
  const [cfgBB, setCfgBB] = useState('10');
  const [cfgTimer, setCfgTimer] = useState('30');
  const [cfgMaxPlayers, setCfgMaxPlayers] = useState('9');
  const [cfgBonus27, setCfgBonus27] = useState(false);
  const [cfgBonus27Amount, setCfgBonus27Amount] = useState('50');
  const [cfgStraddle, setCfgStraddle] = useState(false);

  const loadClubs = () => {
    setLoading(true);
    getUserClubs()
      .then(setClubs)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadClubs(); }, []);

  const handleCreate = async () => {
    const name = clubName.trim();
    if (!name) return;
    setCreating(true);
    setCreateError(null);
    setCreateResult(null);
    try {
      const houseRules = [];
      if (cfgBonus27) houseRules.push({ rule_id: 'bonus_27', params: { bonus_amount: parseInt(cfgBonus27Amount, 10) || 50 } });
      if (cfgStraddle) houseRules.push({ rule_id: 'straddle' });
      const tableConfig = {
        starting_stack: parseInt(cfgStack, 10) || 1000,
        small_blind: parseInt(cfgSB, 10) || 5,
        big_blind: parseInt(cfgBB, 10) || 10,
        turn_timer_seconds: parseInt(cfgTimer, 10) || 30,
        max_players: parseInt(cfgMaxPlayers, 10) || 9,
        house_rules: houseRules,
      };
      const res = await createClub(name, tableConfig);
      setClubName('');
      setCreateResult(`Created! Invite code: ${res.invite_code}`);
      loadClubs();
    } catch (err) {
      setCreateError(extractErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = async () => {
    const code = inviteCode.trim();
    if (!code) return;
    setJoining(true);
    setJoinError(null);
    try {
      await joinClub(code);
      setInviteCode('');
      loadClubs();
    } catch (err) {
      setJoinError(extractErrorMessage(err));
    } finally {
      setJoining(false);
    }
  };

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
            Enter an invite code below to join a club.
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

      {/* Admin: create club */}
      {isAdmin && (
        <View style={styles.adminSection}>
          <Text style={styles.adminLabel}>Create Club</Text>
          <TextInput style={styles.joinInput} placeholder="Club name" placeholderTextColor="#64748B" value={clubName} onChangeText={setClubName} editable={!creating} />

          <Text style={styles.cfgLabel}>Table Config</Text>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>Starting stack</Text>
            <TextInput style={styles.cfgInput} keyboardType="number-pad" value={cfgStack} onChangeText={setCfgStack} editable={!creating} />
          </View>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>Small blind</Text>
            <TextInput style={styles.cfgInput} keyboardType="number-pad" value={cfgSB} onChangeText={setCfgSB} editable={!creating} />
          </View>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>Big blind</Text>
            <TextInput style={styles.cfgInput} keyboardType="number-pad" value={cfgBB} onChangeText={setCfgBB} editable={!creating} />
          </View>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>Turn timer (s)</Text>
            <TextInput style={styles.cfgInput} keyboardType="number-pad" value={cfgTimer} onChangeText={setCfgTimer} editable={!creating} />
          </View>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>Max players</Text>
            <TextInput style={styles.cfgInput} keyboardType="number-pad" value={cfgMaxPlayers} onChangeText={setCfgMaxPlayers} editable={!creating} />
          </View>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>Straddle rule</Text>
            <Switch value={cfgStraddle} onValueChange={setCfgStraddle} disabled={creating} />
          </View>
          <View style={styles.cfgRow}>
            <Text style={styles.cfgKey}>2-7 bonus rule</Text>
            <Switch value={cfgBonus27} onValueChange={setCfgBonus27} disabled={creating} />
          </View>
          {cfgBonus27 && (
            <View style={styles.cfgRow}>
              <Text style={styles.cfgKey}>  Bonus amount</Text>
              <TextInput style={styles.cfgInput} keyboardType="number-pad" value={cfgBonus27Amount} onChangeText={setCfgBonus27Amount} editable={!creating} />
            </View>
          )}

          <TouchableOpacity
            style={[styles.joinButton, styles.createButton, creating && styles.joinButtonDisabled, { margin: 16, marginTop: 8 }]}
            onPress={handleCreate}
            disabled={creating}
          >
            <Text style={styles.joinButtonText}>{creating ? '…' : 'Create Club'}</Text>
          </TouchableOpacity>
          {createResult ? <Text style={styles.createSuccess}>{createResult}</Text> : null}
          {createError ? <Text style={styles.joinError}>{createError}</Text> : null}
        </View>
      )}

      {/* Join club footer */}
      <View style={styles.joinRow}>
        <TextInput
          style={styles.joinInput}
          placeholder="Invite code"
          placeholderTextColor="#64748B"
          autoCapitalize="none"
          autoCorrect={false}
          value={inviteCode}
          onChangeText={setInviteCode}
          editable={!joining}
        />
        <TouchableOpacity
          style={[styles.joinButton, joining && styles.joinButtonDisabled]}
          onPress={handleJoin}
          disabled={joining}
        >
          <Text style={styles.joinButtonText}>{joining ? '…' : 'Join'}</Text>
        </TouchableOpacity>
      </View>
      {joinError ? <Text style={styles.joinError}>{joinError}</Text> : null}
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
  list: { padding: 16, paddingBottom: 0 },
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
  },
  cardName: { fontSize: 18, fontWeight: '700', color: '#F8FAFC' },
  cardSub: { fontSize: 13, color: '#64748B', marginTop: 4 },
  joinRow: {
    flexDirection: 'row',
    padding: 16,
    gap: 10,
  },
  joinInput: {
    flex: 1,
    backgroundColor: '#1E293B',
    color: '#F8FAFC',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
  },
  joinButton: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    paddingHorizontal: 20,
    justifyContent: 'center',
  },
  joinButtonDisabled: { opacity: 0.6 },
  joinButtonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  joinError: { color: '#F87171', fontSize: 13, paddingHorizontal: 16, paddingBottom: 12 },
  adminSection: { borderTopWidth: 1, borderTopColor: '#1E293B', paddingTop: 8 },
  adminLabel: { color: '#94A3B8', fontSize: 12, paddingHorizontal: 16, paddingBottom: 4 },
  cfgLabel: { color: '#64748B', fontSize: 11, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 2, textTransform: 'uppercase', letterSpacing: 1 },
  cfgRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 4 },
  cfgKey: { color: '#94A3B8', fontSize: 13 },
  cfgInput: { backgroundColor: '#1E293B', color: '#F8FAFC', borderRadius: 6, padding: 6, fontSize: 14, width: 80, textAlign: 'right' },
  createButton: { backgroundColor: '#16A34A' },
  createSuccess: { color: '#4ADE80', fontSize: 13, paddingHorizontal: 16, paddingBottom: 8 },
});
