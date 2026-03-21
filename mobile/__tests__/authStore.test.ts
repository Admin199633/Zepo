import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../src/store/authStore';

// Reset store between tests
beforeEach(() => {
  useAuthStore.setState({ token: null, userId: null, isHydrated: false });
  jest.clearAllMocks();
});

// TC-01: initial state
test('TC-01: initial state is unauthenticated and not hydrated', () => {
  const { token, userId, isHydrated } = useAuthStore.getState();
  expect(token).toBeNull();
  expect(userId).toBeNull();
  expect(isHydrated).toBe(false);
});

// TC-02: login persists token and userId to AsyncStorage
test('TC-02: login stores token and userId in store and AsyncStorage', async () => {
  const { login } = useAuthStore.getState();
  await login('tok_abc', 'user_123');

  const { token, userId } = useAuthStore.getState();
  expect(token).toBe('tok_abc');
  expect(userId).toBe('user_123');
  expect(AsyncStorage.multiSet).toHaveBeenCalledWith(
    expect.arrayContaining([
      expect.arrayContaining(['@zepo/auth_token', 'tok_abc']),
      expect.arrayContaining(['@zepo/user_id', 'user_123']),
    ]),
  );
});

// TC-03: logout clears state and AsyncStorage
test('TC-03: logout clears token and userId', async () => {
  useAuthStore.setState({ token: 'tok_abc', userId: 'user_123' });
  const { logout } = useAuthStore.getState();
  await logout();

  const { token, userId } = useAuthStore.getState();
  expect(token).toBeNull();
  expect(userId).toBeNull();
  expect(AsyncStorage.multiRemove).toHaveBeenCalledWith(
    expect.arrayContaining(['@zepo/auth_token', '@zepo/user_id']),
  );
});

// TC-04: hydrate with stored token sets authenticated state
test('TC-04: hydrate with persisted token restores session', async () => {
  (AsyncStorage.multiGet as jest.Mock).mockResolvedValueOnce([
    ['@zepo/auth_token', 'tok_stored'],
    ['@zepo/user_id', 'user_stored'],
  ]);

  const { hydrate } = useAuthStore.getState();
  await hydrate();

  const { token, userId, isHydrated } = useAuthStore.getState();
  expect(token).toBe('tok_stored');
  expect(userId).toBe('user_stored');
  expect(isHydrated).toBe(true);
});

// TC-05: hydrate with no stored token still sets isHydrated = true
test('TC-05: hydrate with no storage sets isHydrated true, token null', async () => {
  (AsyncStorage.multiGet as jest.Mock).mockResolvedValueOnce([
    ['@zepo/auth_token', null],
    ['@zepo/user_id', null],
  ]);

  const { hydrate } = useAuthStore.getState();
  await hydrate();

  const { token, isHydrated } = useAuthStore.getState();
  expect(token).toBeNull();
  expect(isHydrated).toBe(true);
});

// TC-06: hydrate sets isHydrated even if AsyncStorage throws
test('TC-06: hydrate sets isHydrated even on AsyncStorage error', async () => {
  (AsyncStorage.multiGet as jest.Mock).mockRejectedValueOnce(new Error('storage error'));

  const { hydrate } = useAuthStore.getState();
  await hydrate();

  expect(useAuthStore.getState().isHydrated).toBe(true);
});

// TC-07: calling login twice overwrites the previous session
test('TC-07: second login call overwrites previous session', async () => {
  await useAuthStore.getState().login('old_tok', 'old_id');
  await useAuthStore.getState().login('new_tok', 'new_id');

  const { token, userId } = useAuthStore.getState();
  expect(token).toBe('new_tok');
  expect(userId).toBe('new_id');
});
