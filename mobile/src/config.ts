/**
 * Runtime configuration.
 * Set EXPO_PUBLIC_API_URL and EXPO_PUBLIC_WS_URL in .env for your dev/prod backend.
 */

export const BASE_URL: string =
  (process.env.EXPO_PUBLIC_API_URL ?? 'https://zepo.onrender.com').replace(/\/$/, '');

export const WS_BASE_URL: string =
  (process.env.EXPO_PUBLIC_WS_URL ?? 'wss://zepo.onrender.com').replace(/\/$/, '');
