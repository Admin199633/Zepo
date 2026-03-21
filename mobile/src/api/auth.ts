import { apiClient } from './client';
import type { OtpRequestBody, OtpVerifyBody, TokenResponse } from './types';

export async function requestOtp(phone: string): Promise<void> {
  console.log('Sending OTP request...', { phone });
  await apiClient.post<void>('/auth/request-otp', { phone_number: phone } satisfies OtpRequestBody);
}

export async function verifyOtp(
  phone: string,
  code: string,
  displayName?: string,
): Promise<TokenResponse> {
  const body: OtpVerifyBody = { phone_number: phone, code };
  if (displayName) body.display_name = displayName;
  const { data } = await apiClient.post<TokenResponse>('/auth/verify-otp', body);
  return data;
}
