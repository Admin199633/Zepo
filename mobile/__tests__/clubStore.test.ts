import { useClubStore } from '../src/store/clubStore';

jest.mock('../src/api/clubs', () => ({
  getClub: jest.fn(),
}));

jest.mock('../src/api/tables', () => ({
  getClubTable: jest.fn(),
}));

// Provide a stable extractErrorMessage mock for dynamic import inside store
jest.mock('../src/api/client', () => ({
  extractErrorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'Unknown error',
  configureApiClient: jest.fn(),
  apiClient: { get: jest.fn(), post: jest.fn() },
}));

const { getClub } = jest.requireMock('../src/api/clubs') as {
  getClub: jest.Mock;
};
const { getClubTable } = jest.requireMock('../src/api/tables') as {
  getClubTable: jest.Mock;
};

const MOCK_CLUB = {
  club_id: 'club_1',
  name: 'Test Club',
  owner_id: 'owner_1',
  invite_code: 'ABCD',
  member_count: 3,
};

const MOCK_TABLE = {
  table_id: 'tbl_1',
  config: {
    starting_stack: 1000,
    small_blind: 5,
    big_blind: 10,
    turn_timer_seconds: 30,
    max_players: 8,
    house_rules: [],
  },
  recent_hands: [],
};

beforeEach(() => {
  useClubStore.getState().reset();
  jest.clearAllMocks();
});

// TC-08: fetchClub sets selectedClub on success
test('TC-08: fetchClub populates selectedClub', async () => {
  getClub.mockResolvedValueOnce(MOCK_CLUB);
  await useClubStore.getState().fetchClub('club_1');

  expect(useClubStore.getState().selectedClub).toEqual(MOCK_CLUB);
  expect(useClubStore.getState().isLoadingClub).toBe(false);
  expect(useClubStore.getState().error).toBeNull();
});

// TC-09: fetchClub sets error on failure
test('TC-09: fetchClub sets error on API failure', async () => {
  getClub.mockRejectedValueOnce(new Error('Not found'));
  await useClubStore.getState().fetchClub('bad_id');

  expect(useClubStore.getState().selectedClub).toBeNull();
  expect(useClubStore.getState().error).toBe('Not found');
  expect(useClubStore.getState().isLoadingClub).toBe(false);
});

// TC-10: isLoadingClub is true during fetchClub
test('TC-10: isLoadingClub true during fetchClub', () => {
  let resolveClub!: (v: unknown) => void;
  getClub.mockReturnValueOnce(new Promise((r) => { resolveClub = r; }));

  useClubStore.getState().fetchClub('club_1');
  expect(useClubStore.getState().isLoadingClub).toBe(true);
  resolveClub(MOCK_CLUB);
});

// TC-11: fetchTableInfo sets tableInfo on success
test('TC-11: fetchTableInfo populates tableInfo', async () => {
  getClubTable.mockResolvedValueOnce(MOCK_TABLE);
  await useClubStore.getState().fetchTableInfo('tbl_1');

  expect(useClubStore.getState().tableInfo).toEqual(MOCK_TABLE);
  expect(useClubStore.getState().isLoadingTable).toBe(false);
});

// TC-12: fetchTableInfo sets error on failure
test('TC-12: fetchTableInfo sets error on failure', async () => {
  getClubTable.mockRejectedValueOnce(new Error('Table missing'));
  await useClubStore.getState().fetchTableInfo('bad_tbl');

  expect(useClubStore.getState().error).toBe('Table missing');
});

// TC-13: reset clears all state
test('TC-13: reset clears all fields', async () => {
  getClub.mockResolvedValueOnce(MOCK_CLUB);
  await useClubStore.getState().fetchClub('club_1');
  useClubStore.getState().reset();

  const state = useClubStore.getState();
  expect(state.selectedClub).toBeNull();
  expect(state.tableInfo).toBeNull();
  expect(state.error).toBeNull();
  expect(state.isLoadingClub).toBe(false);
  expect(state.isLoadingTable).toBe(false);
});
