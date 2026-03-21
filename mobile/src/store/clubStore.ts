import { create } from 'zustand';
import { getClub } from '../api/clubs';
import { extractErrorMessage } from '../api/client';
import { getClubTable } from '../api/tables';
import type { ClubDTO, TableInfoDTO } from '../api/types';
import { ClubLogger } from '../utils/logger';

interface ClubState {
  selectedClub: ClubDTO | null;
  tableInfo: TableInfoDTO | null;
  isLoadingClub: boolean;
  isLoadingTable: boolean;
  error: string | null;

  fetchClub: (clubId: string) => Promise<void>;
  fetchTableInfo: (tableId: string) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useClubStore = create<ClubState>((set) => ({
  selectedClub: null,
  tableInfo: null,
  isLoadingClub: false,
  isLoadingTable: false,
  error: null,

  fetchClub: async (clubId) => {
    ClubLogger.log('fetchClub:start', { clubId });
    set({ isLoadingClub: true, error: null });
    try {
      const club = await getClub(clubId);
      ClubLogger.log('fetchClub:success', { clubId });
      set({ selectedClub: club });
    } catch (err) {
      ClubLogger.error('fetchClub:error', { clubId, err });
      set({ error: extractErrorMessage(err) });
    } finally {
      set({ isLoadingClub: false });
    }
  },

  fetchTableInfo: async (clubId) => {
    ClubLogger.log('fetchTableInfo:start', { clubId });
    set({ isLoadingTable: true, error: null });
    try {
      const info = await getClubTable(clubId);
      ClubLogger.log('fetchTableInfo:success', { clubId });
      set({ tableInfo: info });
    } catch (err) {
      ClubLogger.error('fetchTableInfo:error', { clubId, err });
      set({ error: extractErrorMessage(err) });
    } finally {
      set({ isLoadingTable: false });
    }
  },

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      selectedClub: null,
      tableInfo: null,
      isLoadingClub: false,
      isLoadingTable: false,
      error: null,
    }),
}));
