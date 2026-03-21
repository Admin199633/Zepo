/**
 * TC-25 – TC-29: HandResultOverlay component
 */
import { render, fireEvent, act } from '@testing-library/react-native';
import HandResultOverlay from '../src/components/table/HandResultOverlay';

jest.useFakeTimers();

const baseResult = {
  hand_id: 'h1',
  hand_number: 3,
  winners: [{ user_id: 'u1', amount: 150, hand_description: 'Two Pair' }],
  final_board: [
    { rank: 'A', suit: 's' },
    { rank: 'K', suit: 'h' },
    { rank: 'Q', suit: 'd' },
  ],
  showdown_hands: [
    {
      user_id: 'u1',
      hole_cards: [{ rank: 'A', suit: 'h' }, { rank: 'K', suit: 's' }],
      hand_description: 'Two Pair',
    },
  ],
};

const players = [{ user_id: 'u1', display_name: 'Alice' } as any];

describe('HandResultOverlay', () => {
  afterEach(() => jest.clearAllTimers());

  it('TC-25: renders hand number', () => {
    const { getByText } = render(
      <HandResultOverlay result={baseResult} players={players} onDismiss={jest.fn()} />
    );
    expect(getByText('Hand #3 Complete')).toBeTruthy();
  });

  it('TC-26: renders winner name and amount', () => {
    const { getAllByText, getByText } = render(
      <HandResultOverlay result={baseResult} players={players} onDismiss={jest.fn()} />
    );
    // Alice appears in winner line and showdown section
    expect(getAllByText(/Alice/).length).toBeGreaterThanOrEqual(1);
    expect(getByText(/150 chips/)).toBeTruthy();
  });

  it('TC-27: auto-dismisses after 4 seconds', () => {
    const onDismiss = jest.fn();
    render(<HandResultOverlay result={baseResult} players={players} onDismiss={onDismiss} />);
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => { jest.advanceTimersByTime(4000); });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('TC-28: tap-to-dismiss calls onDismiss', () => {
    const onDismiss = jest.fn();
    const { getByLabelText } = render(
      <HandResultOverlay result={baseResult} players={players} onDismiss={onDismiss} />
    );
    fireEvent.press(getByLabelText('Hand result, tap to dismiss'));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('TC-29: renders showdown hand cards', () => {
    const { getAllByRole } = render(
      <HandResultOverlay result={baseResult} players={players} onDismiss={jest.fn()} />
    );
    // CardChip components have accessibilityRole="text"
    const cards = getAllByRole('text');
    // final_board (3 cards) + showdown hole cards (2) = 5 chips
    expect(cards.length).toBeGreaterThanOrEqual(5);
  });
});
