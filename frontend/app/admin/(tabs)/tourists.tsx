import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { demoTourists } from '@/lib/demoContent';
import { UserRound, MapPin, ShieldAlert } from 'lucide-react-native';

export default function AdminTourists() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Tourists</Text>
        <Text style={styles.subtitle}>A compact roster view for the command demo</Text>
      </View>

      {demoTourists.map((tourist) => (
        <View key={tourist.id} style={styles.card}>
          <View style={styles.avatar}>
            <UserRound size={18} color="#1a365d" />
          </View>
          <View style={styles.body}>
            <Text style={styles.name}>{tourist.full_name}</Text>
            <Text style={styles.meta}>{tourist.nationality} · {tourist.blood_type ?? 'O+'}</Text>
            <View style={styles.metaRow}>
              <MapPin size={12} color="#0d9488" />
              <Text style={styles.meta}>{tourist.current_zone_id ?? 'Unknown zone'}</Text>
            </View>
          </View>
          <View style={styles.statusPill}>
            <ShieldAlert size={12} color={tourist.status === 'sos' ? '#ef4444' : tourist.status === 'warning' ? '#f59e0b' : '#0d9488'} />
            <Text style={styles.statusText}>{tourist.status?.toUpperCase() ?? 'SAFE'}</Text>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  card: { backgroundColor: '#fff', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#e2e8f0', flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 42, height: 42, borderRadius: 14, backgroundColor: '#dbeafe', alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1 },
  name: { fontSize: 14, fontWeight: '800', color: '#0f172a' },
  meta: { fontSize: 12, color: 'rgba(100,116,139,0.8)', marginTop: 4 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  statusPill: { alignItems: 'center', justifyContent: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 999, backgroundColor: '#f8fafc', borderWidth: 1, borderColor: '#e2e8f0' },
  statusText: { fontSize: 11, fontWeight: '800', color: '#1a365d' },
});
