/**
 * TC-33 – TC-35: HandInfoBar component
 */
import { render } from '@testing-library/react-native';
import HandInfoBar from '../src/components/table/HandInfoBar';

describe('HandInfoBar', () => {
  it('TC-33: renders hand number', () => {
    const { getByText } = render(<HandInfoBar handNumber={7} phase="flop" totalPot={300} />);
    expect(getByText('Hand #7')).toBeTruthy();
  });

  it('TC-34: renders phase label (human-readable)', () => {
    const { getByText } = render(<HandInfoBar handNumber={1} phase="river" totalPot={0} />);
    expect(getByText('River')).toBeTruthy();
  });

  it('TC-35: renders pot amount', () => {
    const { getByText } = render(<HandInfoBar handNumber={1} phase="preflop" totalPot={250} />);
    expect(getByText('Pot: 250')).toBeTruthy();
  });
});
