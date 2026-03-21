/**
 * ConnectionBanner component tests (TC-44 through TC-50).
 */

import { render, fireEvent } from '@testing-library/react-native';
import ConnectionBanner from '../src/components/table/ConnectionBanner';

// TC-44: renders nothing when status is connected
test('TC-44: renders nothing when status is connected', () => {
  const { toJSON } = render(
    <ConnectionBanner status="connected" attempt={0} maxAttempts={3} />,
  );
  expect(toJSON()).toBeNull();
});

// TC-45: renders "Connecting…" text when status is connecting
test('TC-45: shows connecting text when status is connecting', () => {
  const { getByText } = render(
    <ConnectionBanner status="connecting" attempt={0} maxAttempts={3} />,
  );
  expect(getByText('Connecting…')).toBeTruthy();
});

// TC-46: renders attempt count when status is reconnecting
test('TC-46: shows reconnecting text with attempt count', () => {
  const { getByText } = render(
    <ConnectionBanner status="reconnecting" attempt={2} maxAttempts={3} />,
  );
  expect(getByText('Reconnecting… (2/3)')).toBeTruthy();
});

// TC-47: renders error text when status is failed
test('TC-47: shows failed error text when status is failed', () => {
  const { getByText } = render(
    <ConnectionBanner status="failed" attempt={3} maxAttempts={3} />,
  );
  expect(getByText(/Connection lost/)).toBeTruthy();
});

// TC-48: retry button is visible when status is failed and onRetry is provided
test('TC-48: retry button visible when status is failed and onRetry provided', () => {
  const onRetry = jest.fn();
  const { getByLabelText } = render(
    <ConnectionBanner status="failed" attempt={3} maxAttempts={3} onRetry={onRetry} />,
  );
  expect(getByLabelText('Retry connection')).toBeTruthy();
});

// TC-49: tapping retry button calls onRetry
test('TC-49: tapping retry button calls onRetry callback', () => {
  const onRetry = jest.fn();
  const { getByLabelText } = render(
    <ConnectionBanner status="failed" attempt={3} maxAttempts={3} onRetry={onRetry} />,
  );
  fireEvent.press(getByLabelText('Retry connection'));
  expect(onRetry).toHaveBeenCalledTimes(1);
});

// TC-50: retry button is NOT visible when status is reconnecting
test('TC-50: retry button absent when status is reconnecting', () => {
  const onRetry = jest.fn();
  const { queryByLabelText } = render(
    <ConnectionBanner status="reconnecting" attempt={1} maxAttempts={3} onRetry={onRetry} />,
  );
  expect(queryByLabelText('Retry connection')).toBeNull();
});
