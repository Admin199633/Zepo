import { apiClient } from './client';
import type { TableInfoDTO } from './types';

export async function getClubTable(clubId: string): Promise<TableInfoDTO> {
  const { data } = await apiClient.get<TableInfoDTO>(`/clubs/${clubId}/table`);
  return data;
}
