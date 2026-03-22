import { apiClient } from './client';
import type {
  ClubDTO,
  CreateClubBody,
  CreateClubResponse,
  JoinClubBody,
  JoinClubResponse,
  TableConfigInput,
} from './types';

export async function getClub(clubId: string): Promise<ClubDTO> {
  const { data } = await apiClient.get<ClubDTO>(`/clubs/${clubId}`);
  return data;
}

export async function getUserClubs(): Promise<ClubDTO[]> {
  const { data } = await apiClient.get<ClubDTO[]>('/clubs/mine');
  return data;
}

export async function createClub(name: string, tableConfig?: TableConfigInput): Promise<CreateClubResponse> {
  const body: CreateClubBody = { name };
  if (tableConfig) body.table_config = tableConfig;
  const { data } = await apiClient.post<CreateClubResponse>('/clubs', body);
  return data;
}

export async function joinClub(inviteCode: string): Promise<JoinClubResponse> {
  const { data } = await apiClient.post<JoinClubResponse>('/clubs/join', {
    invite_code: inviteCode,
  } satisfies JoinClubBody);
  return data;
}
