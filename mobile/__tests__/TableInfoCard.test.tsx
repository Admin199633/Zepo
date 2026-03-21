/**
 * TableInfoCard component tests (TC-51 through TC-52).
 */

import { render } from '@testing-library/react-native';
import TableInfoCard from '../src/components/common/TableInfoCard';
import type { TableConfigDTO } from '../src/api/types';

const BASE_CONFIG: TableConfigDTO = {
  small_blind: 25,
  big_blind: 50,
  starting_stack: 2000,
  turn_timer_seconds: 30,
  max_players: 9,
  house_rules: [],
};

// TC-51: renders blinds, starting stack, and max players
test('TC-51: renders blinds, starting stack, and max players', () => {
  const { getByText } = render(<TableInfoCard config={BASE_CONFIG} />);

  expect(getByText('Blinds')).toBeTruthy();
  expect(getByText('25 / 50')).toBeTruthy();
  expect(getByText('Starting stack')).toBeTruthy();
  expect(getByText('2000')).toBeTruthy();
  expect(getByText('Max players')).toBeTruthy();
  expect(getByText('9')).toBeTruthy();
});

// TC-52: omits house_rules row when house_rules is empty
test('TC-52: house_rules row not shown when house_rules is empty', () => {
  const { queryByText } = render(<TableInfoCard config={BASE_CONFIG} />);
  expect(queryByText('House rules')).toBeNull();
});
