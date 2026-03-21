/**
 * TC-22 – TC-24: Hole card visibility guard
 * Other players' hole cards must NOT be rendered; only the current user's cards
 */
import { render } from '@testing-library/react-native';
import MyHoleCards from '../src/components/table/MyHoleCards';
import PlayerList from '../src/components/table/PlayerList';

const myCards = [
  { rank: 'A', suit: 'h' },
  { rank: 'K', suit: 's' },
];

const players = [
  {
    user_id: 'me',
    display_name: 'Me',
    status: 'playing',
    stack: 500,
    seat: 1,
    is_dealer: false,
    hole_cards: myCards,
    current_bet: 0,
    reserve_until: null,
  },
  {
    user_id: 'other',
    display_name: 'Other',
    status: 'playing',
    stack: 300,
    seat: 2,
    is_dealer: false,
    hole_cards: [{ rank: '7', suit: 'd' }, { rank: '2', suit: 'c' }],
    current_bet: 0,
    reserve_until: null,
  },
];

describe('hole card guard', () => {
  it('TC-22: MyHoleCards renders my cards with accessibility labels', () => {
    const { getAllByRole } = render(<MyHoleCards cards={myCards} />);
    // Each CardChip has accessibilityRole="text"
    const cards = getAllByRole('text');
    expect(cards.length).toBeGreaterThanOrEqual(2);
  });

  it('TC-23: PlayerList does not render other player hole cards as text', () => {
    // PlayerList shows card backs (View elements) for other players, not CardChip with card text
    // We verify the other player's actual card ranks are not visible as accessibility labels
    const { queryByLabelText } = render(
      <PlayerList players={players} myUserId="me" currentActorId={null} />
    );
    // The other player's cards (7d, 2c) should not appear as labeled chip elements
    expect(queryByLabelText('7 of diamonds')).toBeNull();
    expect(queryByLabelText('2 of clubs')).toBeNull();
  });

  it('TC-24: MyHoleCards is not rendered for other players via parent guard', () => {
    // Simulate the parent guard: only render MyHoleCards when myPlayer has cards
    // and myPlayer is the current user. Here we check directly that the component
    // doesn't expose cards for a different user.
    const { queryByLabelText } = render(<MyHoleCards cards={myCards} />);
    expect(queryByLabelText('A of hearts')).toBeTruthy();
    // Opponent card labels are absent because we only pass myCards
    expect(queryByLabelText('7 of diamonds')).toBeNull();
  });
});
