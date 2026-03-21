import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Button from '../common/Button';
import RaisePanel from './RaisePanel';

interface ActionBarProps {
  callAmount: number;
  minRaise: number;
  maxRaise: number;  // effective stack cap for raise slider (from server)
  myStack: number;
  onFold: () => void;
  onCheck: () => void;
  onCall: () => void;
  onRaise: (amount: number) => void;
}

export default function ActionBar({
  callAmount,
  minRaise,
  maxRaise,
  myStack,
  onFold,
  onCheck,
  onCall,
  onRaise,
}: ActionBarProps) {
  const insets = useSafeAreaInsets();
  const [raiseOpen, setRaiseOpen] = useState(false);

  const handleAction = (fn: () => void) => {
    setRaiseOpen(false);
    fn();
  };

  // Defensively cap raise at player's own stack in case server sends a stale/zero value.
  const effectiveMaxRaise = maxRaise > 0 ? maxRaise : myStack;

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8 }]}>
      {raiseOpen && (
        <RaisePanel
          minRaise={minRaise}
          maxRaise={effectiveMaxRaise}
          onConfirm={(amount) => {
            setRaiseOpen(false);
            onRaise(amount);
          }}
          onCancel={() => setRaiseOpen(false)}
        />
      )}
      <View style={styles.buttons}>
        <Button
          label="Fold"
          variant="secondary"
          style={styles.btn}
          onPress={() => handleAction(onFold)}
          accessibilityLabel="Fold"
          accessibilityRole="button"
        />
        <Button
          label={callAmount > 0 ? `Call ${callAmount}` : 'Check'}
          style={styles.btn}
          onPress={() => handleAction(callAmount > 0 ? onCall : onCheck)}
          accessibilityLabel={callAmount > 0 ? `Call ${callAmount}` : 'Check'}
          accessibilityRole="button"
        />
        <Button
          label="Raise"
          style={[styles.btn, styles.raiseBtn]}
          onPress={() => setRaiseOpen((v) => !v)}
          accessibilityLabel="Raise"
          accessibilityRole="button"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#0F172A',
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  buttons: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1 },
  raiseBtn: { backgroundColor: '#7C3AED' },
});
