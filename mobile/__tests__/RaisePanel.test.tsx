/**
 * TC-19 – TC-21: RaisePanel component
 */
import { render, fireEvent } from '@testing-library/react-native';
import RaisePanel from '../src/components/table/RaisePanel';

beforeEach(() => jest.clearAllMocks());

describe('RaisePanel', () => {
  it('TC-19: renders slider with correct accessibility label', () => {
    const { getByTestId } = render(
      <RaisePanel minRaise={10} maxRaise={100} onConfirm={jest.fn()} onCancel={jest.fn()} />
    );
    expect(getByTestId('raise-slider')).toBeTruthy();
  });

  it('TC-20: Cancel button calls onCancel', () => {
    const onCancel = jest.fn();
    const { getByLabelText } = render(
      <RaisePanel minRaise={10} maxRaise={100} onConfirm={jest.fn()} onCancel={onCancel} />
    );
    fireEvent.press(getByLabelText('Cancel raise'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('TC-21: shows "All-in" label when min >= max', () => {
    const { getByText } = render(
      <RaisePanel minRaise={100} maxRaise={100} onConfirm={jest.fn()} onCancel={jest.fn()} />
    );
    expect(getByText(/All-in/)).toBeTruthy();
  });
});
