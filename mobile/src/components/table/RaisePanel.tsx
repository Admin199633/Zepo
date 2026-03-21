import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Slider from '@react-native-community/slider';
import Button from '../common/Button';

interface RaisePanelProps {
  minRaise: number;
  maxRaise: number;
  onConfirm: (amount: number) => void;
  onCancel: () => void;
}

export default function RaisePanel({ minRaise, maxRaise, onConfirm, onCancel }: RaisePanelProps) {
  const effectiveMin = Math.min(minRaise, maxRaise);
  const effectiveMax = maxRaise;
  const isAllIn = effectiveMin >= effectiveMax;
  const [value, setValue] = useState(effectiveMin);

  return (
    <View style={styles.container}>
      <Text style={styles.label}>
        {isAllIn ? `All-in: ${value}` : `Raise to: ${value}`}
      </Text>
      <Slider
        style={styles.slider}
        minimumValue={effectiveMin}
        maximumValue={isAllIn ? effectiveMax + 0.001 : effectiveMax}
        step={1}
        value={value}
        onValueChange={(v: number) => setValue(Math.round(v))}
        minimumTrackTintColor="#2563EB"
        maximumTrackTintColor="#334155"
        thumbTintColor="#7C3AED"
        disabled={isAllIn}
        accessibilityLabel={`Raise amount slider, current value ${value}`}
        testID="raise-slider"
      />
      <View style={styles.buttons}>
        <Button
          label="Cancel"
          variant="secondary"
          style={styles.cancelBtn}
          onPress={onCancel}
          accessibilityLabel="Cancel raise"
          accessibilityRole="button"
        />
        <Button
          label="Confirm Raise"
          style={styles.confirmBtn}
          onPress={() => onConfirm(value)}
          accessibilityLabel={`Confirm raise ${value}`}
          accessibilityRole="button"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1E293B',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  label: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 8,
  },
  slider: { width: '100%', height: 40 },
  buttons: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cancelBtn: { flex: 1 },
  confirmBtn: { flex: 2 },
});
