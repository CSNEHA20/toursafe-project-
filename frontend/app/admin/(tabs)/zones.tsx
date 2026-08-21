import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { demoZones } from '@/lib/demoContent';
import { MapPinned, ShieldAlert } from 'lucide-react-native';

export default function AdminZones() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Zones</Text>
        <Text style={styles.subtitle}>Drawn from mock geofence data for the frontend prototype</Text>
      </View>

      {demoZones.map((zone) => (
        <View key={zone.id} style={styles.card}>
          <View style={styles.cardHeader}>
            <MapPinned size={18} color={zone.zone_type === 'danger' ? '#ef4444' : zone.zone_type === 'warning' ? '#f59e0b' : '#0d9488'} />
            <Text style={styles.cardTitle}>{zone.name}</Text>
          </View>
          <Text style={styles.cardMeta}>{zone.alert_message_en}</Text>
          <View style={styles.tags}>
            <Tag label={zone.zone_type.toUpperCase()} />
            <Tag label={`${zone.tourist_count} tourists`} />
            <Tag label={`${zone.active_alerts} alerts`} />
          </View>
        </View>
      ))}
      <View style={styles.footerCard}>
        <ShieldAlert size={16} color="#1a365d" />
        <Text style={styles.footerText}>Future backend version can enable real polygon editing and publish workflows.</Text>
      </View>
    </ScrollView>
  );
}

function Tag({ label }: { label: string }) {
  return (
    <View style={styles.tag}>
      <Text style={styles.tagText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  card: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  cardHeader: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  cardTitle: { fontSize: 16, fontWeight: '800', color: '#0f172a', flex: 1 },
  cardMeta: { marginTop: 10, color: 'rgba(100,116,139,0.8)', lineHeight: 20 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  tag: { backgroundColor: '#eff6ff', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6 },
  tagText: { fontSize: 11, fontWeight: '800', color: '#1a365d' },
  footerCard: { backgroundColor: '#ecfeff', borderRadius: 18, padding: 14, borderWidth: 1, borderColor: '#a5f3fc', flexDirection: 'row', gap: 10, alignItems: 'center' },
  footerText: { flex: 1, color: '#155e75', lineHeight: 20 },
});
