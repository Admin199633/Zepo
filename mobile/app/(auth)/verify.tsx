import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { verifyOtp } from '../../src/api/auth';
import { extractErrorMessage } from '../../src/api/client';
import { useAuthStore } from '../../src/store/authStore';

export default function VerifyScreen() {
  const router = useRouter();
  const { phone } = useLocalSearchParams<{ phone: string }>();
  const login = useAuthStore((s) => s.login);

  const [code, setCode] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async () => {
    const trimmedCode = code.trim();
    if (!trimmedCode) {
      setError('Please enter the code.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await verifyOtp(
        phone ?? '',
        trimmedCode,
        displayName.trim() || undefined,
      );
      await login(response.token, response.user_id);
      router.replace('/(app)');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.container}>
        <Text style={styles.title}>Verify</Text>
        <Text style={styles.subtitle}>
          We sent a code to {phone}
        </Text>

        <TextInput
          style={styles.input}
          placeholder="6-digit code"
          keyboardType="number-pad"
          textContentType="oneTimeCode"
          value={code}
          onChangeText={setCode}
          maxLength={6}
          editable={!loading}
        />

        <TextInput
          style={styles.input}
          placeholder="Display name (optional)"
          autoCapitalize="words"
          textContentType="name"
          value={displayName}
          onChangeText={setDisplayName}
          editable={!loading}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleVerify}
          disabled={loading}
        >
          <Text style={styles.buttonText}>{loading ? 'Verifying…' : 'Continue'}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.back}
          onPress={() => router.back()}
          disabled={loading}
        >
          <Text style={styles.backText}>← Change number</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 32,
    backgroundColor: '#0F172A',
  },
  title: { fontSize: 32, fontWeight: '800', color: '#F8FAFC', marginBottom: 8 },
  subtitle: { fontSize: 15, color: '#94A3B8', marginBottom: 32 },
  input: {
    backgroundColor: '#1E293B',
    color: '#F8FAFC',
    borderRadius: 10,
    padding: 16,
    fontSize: 18,
    marginBottom: 12,
  },
  error: { color: '#F87171', marginBottom: 12, fontSize: 14 },
  button: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  back: { alignItems: 'center' },
  backText: { color: '#94A3B8', fontSize: 14 },
});
