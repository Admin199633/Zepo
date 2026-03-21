/**
 * Runtime configuration.
 * Set EXPO_PUBLIC_API_URL and EXPO_PUBLIC_WS_URL in .env for your dev/prod backend.
 */

export const BASE_URL: string =
  (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export const WS_BASE_URL: string =
  (process.env.EXPO_PUBLIC_WS_URL ?? 'ws://localhost:8000').replace(/\/$/, '');
