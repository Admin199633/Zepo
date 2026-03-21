import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { configureApiClient } from '../api/client';
import { AuthLogger } from '../utils/logger';

const TOKEN_KEY = '@zepo/auth_token';
const USER_ID_KEY = '@zepo/user_id';

interface AuthState {
  token: string | null;
  userId: string | null;
  isHydrated: boolean;

  login: (token: string, userId: string) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => {
  // Wire the API client to always read current token from store
  configureApiClient(
    () => get().token,
    () => get().logout(),
  );

  return {
    token: null,
    userId: null,
    isHydrated: false,

    login: async (token, userId) => {
      AuthLogger.log('login', { userId });
      await AsyncStorage.multiSet([
        [TOKEN_KEY, token],
        [USER_ID_KEY, userId],
      ]);
      set({ token, userId });
    },

    logout: async () => {
      AuthLogger.log('logout');
      await AsyncStorage.multiRemove([TOKEN_KEY, USER_ID_KEY]);
      set({ token: null, userId: null });
    },

    hydrate: async () => {
      AuthLogger.log('hydrate:start');
      try {
        const [[, token], [, userId]] = await AsyncStorage.multiGet([
          TOKEN_KEY,
          USER_ID_KEY,
        ]);
        if (token && userId) {
          AuthLogger.log('hydrate:success', { userId });
          set({ token, userId });
        } else {
          AuthLogger.log('hydrate:no-session');
        }
      } catch (err) {
        AuthLogger.error('hydrate:error', err);
        // Storage error — start unauthenticated; user will see login screen
      } finally {
        set({ isHydrated: true });
      }
    },
  };
});
