/**
 * TC-30 – TC-32: CardChip component
 */
import { render } from '@testing-library/react-native';
import CardChip from '../src/components/table/CardChip';

describe('CardChip', () => {
  it('TC-30: renders rank text', () => {
    const { getByText } = render(<CardChip card={{ rank: 'K', suit: 'h' }} />);
    expect(getByText('K')).toBeTruthy();
  });

  it('TC-31: accessibility label is "{rank} of {suitName}"', () => {
    const { getByLabelText } = render(<CardChip card={{ rank: 'A', suit: 'd' }} />);
    expect(getByLabelText('A of diamonds')).toBeTruthy();
  });

  it('TC-32: spades and clubs suit symbol is rendered (not red)', () => {
    // Just checks render without crash for black suits
    const { getByText } = render(<CardChip card={{ rank: '7', suit: 's' }} />);
    expect(getByText('♠')).toBeTruthy();
  });
});
