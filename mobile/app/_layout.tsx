import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect } from 'react';
import { useAuthStore } from '../src/store/authStore';

export default function RootLayout() {
  const { isHydrated, token, hydrate } = useAuthStore();
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    hydrate();
  }, []);

  useEffect(() => {
    if (!isHydrated) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!token && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (token && inAuthGroup) {
      router.replace('/(app)');
    }
  }, [isHydrated, token, segments]);

  return <Stack screenOptions={{ headerShown: false }} />;
}
