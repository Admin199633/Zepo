/**
 * TC-14 – TC-18: ActionBar component
 */
import { render, fireEvent } from '@testing-library/react-native';
import ActionBar from '../src/components/table/ActionBar';

const defaultProps = {
  callAmount: 0,
  minRaise: 10,
  myStack: 200,
  onFold: jest.fn(),
  onCheck: jest.fn(),
  onCall: jest.fn(),
  onRaise: jest.fn(),
};

beforeEach(() => jest.clearAllMocks());

describe('ActionBar', () => {
  it('TC-14: shows "Check" when callAmount is 0', () => {
    const { getByLabelText } = render(<ActionBar {...defaultProps} callAmount={0} />);
    expect(getByLabelText('Check')).toBeTruthy();
  });

  it('TC-15: shows "Call N" when callAmount > 0', () => {
    const { getByLabelText } = render(<ActionBar {...defaultProps} callAmount={50} />);
    expect(getByLabelText('Call 50')).toBeTruthy();
  });

  it('TC-16: onFold called when Fold pressed', () => {
    const onFold = jest.fn();
    const { getByLabelText } = render(<ActionBar {...defaultProps} onFold={onFold} />);
    fireEvent.press(getByLabelText('Fold'));
    expect(onFold).toHaveBeenCalledTimes(1);
  });

  it('TC-17: onCheck called when Check pressed (callAmount=0)', () => {
    const onCheck = jest.fn();
    const { getByLabelText } = render(<ActionBar {...defaultProps} callAmount={0} onCheck={onCheck} />);
    fireEvent.press(getByLabelText('Check'));
    expect(onCheck).toHaveBeenCalledTimes(1);
  });

  it('TC-18: Raise button opens RaisePanel', () => {
    const { getByLabelText, queryByTestId } = render(<ActionBar {...defaultProps} />);
    expect(queryByTestId('raise-slider')).toBeNull();
    fireEvent.press(getByLabelText('Raise'));
    expect(queryByTestId('raise-slider')).toBeTruthy();
  });
});
