import { TouchableOpacity, View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { ShieldAlert, User } from 'lucide-react-native';

type RoleSwitchProps = {
  currentRole: 'tourist' | 'authority';
};

export default function RoleSwitch({ currentRole }: RoleSwitchProps) {
  const router = useRouter();
  const devBypass = process.env.EXPO_PUBLIC_DEV_BYPASS === 'true';

  if (!devBypass) {
    return null;
  }

  const nextRole = currentRole === 'tourist' ? 'authority' : 'tourist';

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Dev switch</Text>
      <TouchableOpacity
        onPress={() =>
          router.replace(
            nextRole === 'tourist' ? '/tourist/(tabs)/dashboard' : '/admin/(tabs)/dashboard'
          )
        }
        style={styles.switch}
        activeOpacity={0.85}
      >
        <View style={[styles.segment, currentRole === 'tourist' && styles.segmentActive]}>
          <User size={14} color={currentRole === 'tourist' ? '#fff' : '#64748b'} />
          <Text style={[styles.segmentText, currentRole === 'tourist' && styles.segmentTextActive]}>
            User
          </Text>
        </View>
        <View style={[styles.segment, currentRole === 'authority' && styles.segmentActive]}>
          <ShieldAlert size={14} color={currentRole === 'authority' ? '#fff' : '#64748b'} />
          <Text style={[styles.segmentText, currentRole === 'authority' && styles.segmentTextActive]}>
            Authority
          </Text>
        </View>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  label: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748b',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  switch: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    padding: 4,
  },
  segment: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
  },
  segmentActive: {
    backgroundColor: '#1a365d',
  },
  segmentText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748b',
  },
  segmentTextActive: {
    color: '#fff',
  },
});
