import { Redirect } from 'expo-router';

// OTP verification is no longer used. Redirect any stale deep-links to login.
export default function VerifyScreen() {
  return <Redirect href="/(auth)/login" />;
}
