import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { demoAnalytics, demoZoneSummary } from '@/lib/demoContent';
import { Activity, TrendingUp, Gauge, MapPinned } from 'lucide-react-native';

export default function AdminAnalytics() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Analytics</Text>
        <Text style={styles.subtitle}>A visual MVP with stat cards, trend bars, and zones</Text>
      </View>

      <View style={styles.kpiRow}>
        <Kpi icon={<Activity size={16} color="#1a365d" />} label="Active tourists" value="47" />
        <Kpi icon={<Gauge size={16} color="#0d9488" />} label="Avg response" value="7.2 min" />
        <Kpi icon={<TrendingUp size={16} color="#b45309" />} label="Alerts today" value="8" />
      </View>

      <View style={styles.panel}>
        <Text style={styles.panelTitle}>Trend snapshot</Text>
        {demoAnalytics.slice(-5).map((point) => (
          <View key={point.date} style={styles.trendRow}>
            <Text style={styles.trendLabel}>{point.date}</Text>
            <View style={styles.barWrap}>
              <View style={[styles.bar, { width: `${Math.min(point.tourists, 60)}%` }]} />
            </View>
            <Text style={styles.trendValue}>{point.tourists}</Text>
          </View>
        ))}
      </View>

      <View style={styles.panel}>
        <Text style={styles.panelTitle}>Zone risk table</Text>
        {demoZoneSummary.map((zone) => (
          <View key={zone.id} style={styles.zoneRow}>
            <MapPinned size={16} color={zone.zone_type === 'danger' ? '#ef4444' : zone.zone_type === 'warning' ? '#f59e0b' : '#0d9488'} />
            <View style={{ flex: 1 }}>
              <Text style={styles.zoneName}>{zone.name}</Text>
              <Text style={styles.zoneMeta}>{zone.tourist_count} tourists · risk {zone.avg_response_minutes}m</Text>
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function Kpi({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <View style={styles.kpi}>
      {icon}
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={styles.kpiValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  kpiRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  kpi: { flex: 1, minWidth: '30%', backgroundColor: '#fff', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: '#e2e8f0', gap: 6 },
  kpiLabel: { fontSize: 11, textTransform: 'uppercase', color: 'rgba(100,116,139,0.7)', fontWeight: '700' },
  kpiValue: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  panel: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  panelTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  trendRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  trendLabel: { width: 56, fontSize: 12, color: 'rgba(100,116,139,0.8)' },
  barWrap: { flex: 1, height: 10, backgroundColor: '#e2e8f0', borderRadius: 999, overflow: 'hidden' },
  bar: { height: '100%', backgroundColor: '#0d9488' },
  trendValue: { width: 24, textAlign: 'right', fontWeight: '700', color: '#0f172a' },
  zoneRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#eef2f7' },
  zoneName: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  zoneMeta: { marginTop: 4, fontSize: 12, color: 'rgba(100,116,139,0.8)' },
});
