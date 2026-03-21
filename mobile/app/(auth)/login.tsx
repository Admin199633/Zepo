import { useRouter } from 'expo-router';
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
import { requestOtp } from '../../src/api/auth';
import { extractErrorMessage } from '../../src/api/client';

export default function LoginScreen() {
  const router = useRouter();
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async () => {
    const trimmed = phone.trim();
    if (!trimmed) {
      setError('Please enter your phone number.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await requestOtp(trimmed);
      router.push({ pathname: '/(auth)/verify', params: { phone: trimmed } });
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
        <Text style={styles.title}>Zepo</Text>
        <Text style={styles.subtitle}>Enter your phone number to get started</Text>

        <TextInput
          style={styles.input}
          placeholder="+1 555 000 0000"
          keyboardType="phone-pad"
          autoComplete="tel"
          textContentType="telephoneNumber"
          value={phone}
          onChangeText={setPhone}
          editable={!loading}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleSend}
          disabled={loading}
        >
          <Text style={styles.buttonText}>{loading ? 'Sending…' : 'Send code'}</Text>
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
  title: { fontSize: 36, fontWeight: '800', color: '#F8FAFC', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#94A3B8', marginBottom: 32 },
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
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
