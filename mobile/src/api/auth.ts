import { apiClient } from './client';
import type { LoginBody, RegisterBody, TokenResponse } from './types';

export async function register(
  username: string,
  password: string,
  displayName: string,
): Promise<TokenResponse> {
  const body: RegisterBody = { username, password, display_name: displayName };
  const { data } = await apiClient.post<TokenResponse>('/auth/register', body);
  return data;
}

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const body: LoginBody = { username, password };
  const { data } = await apiClient.post<TokenResponse>('/auth/login', body);
  return data;
}
