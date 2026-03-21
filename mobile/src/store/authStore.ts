import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { configureApiClient } from '../api/client';
import { AuthLogger } from '../utils/logger';

const TOKEN_KEY        = '@zepo/auth_token';
const USER_ID_KEY      = '@zepo/user_id';
const DISPLAY_NAME_KEY = '@zepo/display_name';

interface AuthState {
  token: string | null;
  userId: string | null;
  displayName: string | null;
  isHydrated: boolean;

  login: (token: string, userId: string, displayName: string) => Promise<void>;
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
    displayName: null,
    isHydrated: false,

    login: async (token, userId, displayName) => {
      AuthLogger.log('login', { userId, displayName });
      await AsyncStorage.multiSet([
        [TOKEN_KEY,        token],
        [USER_ID_KEY,      userId],
        [DISPLAY_NAME_KEY, displayName],
      ]);
      set({ token, userId, displayName });
    },

    logout: async () => {
      AuthLogger.log('logout');
      await AsyncStorage.multiRemove([TOKEN_KEY, USER_ID_KEY, DISPLAY_NAME_KEY]);
      set({ token: null, userId: null, displayName: null });
    },

    hydrate: async () => {
      AuthLogger.log('hydrate:start');
      try {
        const [[, token], [, userId], [, displayName]] = await AsyncStorage.multiGet([
          TOKEN_KEY,
          USER_ID_KEY,
          DISPLAY_NAME_KEY,
        ]);
        if (token && userId) {
          AuthLogger.log('hydrate:success', { userId });
          set({ token, userId, displayName: displayName ?? null });
        } else {
          AuthLogger.log('hydrate:no-session');
        }
      } catch (err) {
        AuthLogger.error('hydrate:error', err);
      } finally {
        set({ isHydrated: true });
      }
    },
  };
});
