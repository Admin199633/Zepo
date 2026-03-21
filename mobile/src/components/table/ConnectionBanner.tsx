import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { ConnectionStatus } from '../../ws/types';

interface ConnectionBannerProps {
  status: ConnectionStatus;
  attempt: number;
  maxAttempts: number;
  onRetry?: () => void;
}

export default function ConnectionBanner({ status, attempt, maxAttempts, onRetry }: ConnectionBannerProps) {
  if (status === 'connected') return null;

  let text: string;
  let bgColor: string;

  switch (status) {
    case 'connecting':
      text = 'Connecting…';
      bgColor = '#1D4ED8';
      break;
    case 'reconnecting':
      text = `Reconnecting… (${attempt}/${maxAttempts})`;
      bgColor = '#B45309';
      break;
    case 'failed':
      text = 'Connection lost. Tap Retry or restart the app.';
      bgColor = '#991B1B';
      break;
    default:
      text = 'Disconnected';
      bgColor = '#374151';
  }

  return (
    <View style={[styles.banner, { backgroundColor: bgColor }]}>
      {status === 'failed' ? (
        <View style={styles.failedContainer}>
          <Text style={styles.text}>{text}</Text>
          {onRetry !== undefined && (
            <TouchableOpacity
              style={styles.retryButton}
              onPress={onRetry}
              accessibilityLabel="Retry connection"
            >
              <Text style={styles.retryText}>Retry Connection</Text>
            </TouchableOpacity>
          )}
        </View>
      ) : (
        <Text style={styles.text}>{text}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: { paddingVertical: 8, paddingHorizontal: 16 },
  text: { color: '#fff', fontSize: 13, fontWeight: '600', textAlign: 'center' },
  failedContainer: { alignItems: 'center' },
  retryButton: {
    backgroundColor: '#EF4444',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 20,
    alignSelf: 'center',
    marginTop: 10,
  },
  retryText: { color: '#fff', fontSize: 13, fontWeight: '600' },
});
