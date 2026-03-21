/**
 * Axios base client with token injection and 401 handling.
 */
import axios, { AxiosError } from 'axios';
import { BASE_URL } from '../config';
import type { ApiErrorResponse } from './types';

console.log('API BASE URL:', BASE_URL);

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
});

// Lazy import to avoid circular deps at module init time
let _getToken: (() => string | null) | null = null;
let _onUnauthorized: (() => void) | null = null;

export function configureApiClient(
  getToken: () => string | null,
  onUnauthorized: () => void,
): void {
  _getToken = getToken;
  _onUnauthorized = onUnauthorized;
}

// Inject Bearer token on every request
apiClient.interceptors.request.use((config) => {
  const token = _getToken?.();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 globally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      _onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

/**
 * Extract a human-readable error message from an API error.
 */
export function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = (err as AxiosError<ApiErrorResponse>).response?.data;
    if (data?.detail?.message) return data.detail.message;
    if (data?.detail?.error) return data.detail.error;
    if (err.message === 'Network Error') return 'No internet connection.';
  }
  if (err instanceof Error) return err.message;
  return 'Something went wrong. Please try again.';
}
