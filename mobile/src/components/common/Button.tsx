import { StyleSheet, Text, TouchableOpacity, type TouchableOpacityProps } from 'react-native';

interface ButtonProps extends TouchableOpacityProps {
  label: string;
  variant?: 'primary' | 'secondary';
}

export default function Button({ label, variant = 'primary', style, ...rest }: ButtonProps) {
  return (
    <TouchableOpacity
      style={[styles.base, variant === 'secondary' ? styles.secondary : styles.primary, style]}
      {...rest}
    >
      <Text style={[styles.text, variant === 'secondary' && styles.textSecondary]}>
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: { borderRadius: 10, paddingVertical: 14, paddingHorizontal: 24, alignItems: 'center' },
  primary: { backgroundColor: '#2563EB' },
  secondary: { backgroundColor: 'transparent', borderWidth: 1, borderColor: '#334155' },
  text: { color: '#fff', fontWeight: '700', fontSize: 16 },
  textSecondary: { color: '#94A3B8' },
});
