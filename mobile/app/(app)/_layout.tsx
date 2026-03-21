import { Stack } from 'expo-router';
import AppErrorBoundary from '../../src/components/common/AppErrorBoundary';

export default function AppLayout() {
  return (
    <AppErrorBoundary>
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: '#0F172A' },
          headerTintColor: '#F8FAFC',
          headerTitleStyle: { fontWeight: '700' },
        }}
      />
    </AppErrorBoundary>
  );
}
