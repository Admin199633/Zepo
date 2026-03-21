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
import { login, register } from '../../src/api/auth';
import { extractErrorMessage } from '../../src/api/client';
import { useAuthStore } from '../../src/store/authStore';

export default function LoginScreen() {
  const router = useRouter();
  const loginStore = useAuthStore((s) => s.login);

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const u = username.trim();
    const p = password.trim();
    if (!u || !p) {
      setError('Username and password are required.');
      return;
    }
    if (mode === 'register' && !displayName.trim()) {
      setError('Display name is required.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response =
        mode === 'register'
          ? await register(u, p, displayName.trim())
          : await login(u, p);
      await loginStore(response.token, response.user_id);
      router.replace('/(app)');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const isRegister = mode === 'register';

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.container}>
        <Text style={styles.title}>Zepo</Text>
        <Text style={styles.subtitle}>
          {isRegister ? 'Create an account' : 'Sign in to play'}
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Username"
          autoCapitalize="none"
          autoCorrect={false}
          value={username}
          onChangeText={setUsername}
          editable={!loading}
        />

        {isRegister && (
          <TextInput
            style={styles.input}
            placeholder="Display name"
            autoCapitalize="words"
            value={displayName}
            onChangeText={setDisplayName}
            editable={!loading}
          />
        )}

        <TextInput
          style={styles.input}
          placeholder="Password"
          secureTextEntry
          textContentType={isRegister ? 'newPassword' : 'password'}
          value={password}
          onChangeText={setPassword}
          editable={!loading}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.buttonText}>
            {loading ? '…' : isRegister ? 'Register' : 'Sign in'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.toggle}
          onPress={() => { setMode(isRegister ? 'login' : 'register'); setError(null); }}
          disabled={loading}
        >
          <Text style={styles.toggleText}>
            {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
          </Text>
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
    marginBottom: 16,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  toggle: { alignItems: 'center' },
  toggleText: { color: '#94A3B8', fontSize: 14 },
});
