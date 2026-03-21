/**
 * TC-36: CommunityCards component
 */
import { render } from '@testing-library/react-native';
import CommunityCards from '../src/components/table/CommunityCards';

describe('CommunityCards', () => {
  it('TC-36: shows "Waiting for flop…" when cards array is empty', () => {
    const { getByText } = render(<CommunityCards cards={[]} phase="preflop" />);
    expect(getByText('Waiting for flop…')).toBeTruthy();
  });

  it('renders cards when provided', () => {
    const cards = [
      { rank: 'A', suit: 's' },
      { rank: 'K', suit: 'h' },
      { rank: 'Q', suit: 'd' },
    ];
    const { getAllByRole, queryByText } = render(<CommunityCards cards={cards} phase="flop" />);
    expect(queryByText('Waiting for flop…')).toBeNull();
    const chips = getAllByRole('text');
    // Each CardChip has a View (accessibilityRole="text") + 2 Text children
    expect(chips.length).toBeGreaterThanOrEqual(3);
  });
});
