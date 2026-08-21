import { ScrollView, View, Text, StyleSheet, Platform } from 'react-native';
import { MapPinned, Users, TriangleAlert, Activity, Layers3 } from 'lucide-react-native';
import { demoHeatmapPoints, demoTourists, demoZones } from '@/lib/demoContent';
import RealMap from '@/components/RealMap';

const baseRegion = { latitude: 10.19, longitude: 77.47, latitudeDelta: 0.18, longitudeDelta: 0.18 };

const touristPins = demoTourists.slice(0, 6).map((tourist, index) => ({
  latitude: 10.17 + index * 0.015,
  longitude: 77.42 + index * 0.012,
  title: tourist.full_name,
}));

export default function AdminMap() {
  const zonePolygon = [
    { latitude: 10.26, longitude: 77.39 },
    { latitude: 10.3, longitude: 77.53 },
    { latitude: 10.15, longitude: 77.58 },
    { latitude: 10.07, longitude: 77.43 },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Live Command Map</Text>
        <Text style={styles.subtitle}>Real map with live-looking tourists, zones, and incident markers</Text>
      </View>

      <View style={styles.kpiRow}>
        <MiniStat icon={<Users size={16} color="#1a365d" />} label="Tourists" value={String(demoTourists.length)} />
        <MiniStat icon={<TriangleAlert size={16} color="#b45309" />} label="Incidents" value="4 active" />
        <MiniStat icon={<Activity size={16} color="#0d9488" />} label="Heat points" value={String(demoHeatmapPoints.length)} />
        <MiniStat icon={<Layers3 size={16} color="#475569" />} label="Map mode" value={Platform.OS === 'web' ? 'OpenStreetMap' : 'Native'} />
      </View>

      <View style={styles.mapCard}>
        <View style={styles.mapTopRow}>
          <View style={styles.mapPill}>
            <MapPinned size={14} color="#0f172a" />
            <Text style={styles.mapPillText}>Operator view</Text>
          </View>
          <Text style={styles.mapNote}>Polygon zones, tourist pins, and active routes</Text>
        </View>

        <RealMap
          region={baseRegion}
          polygon={zonePolygon}
          route={[
            { latitude: 10.27, longitude: 77.45 },
            { latitude: 10.23, longitude: 77.47 },
            { latitude: 10.2, longitude: 77.48 },
          ]}
          markers={touristPins.map((pin, index) => ({
            ...pin,
            color: index % 3 === 0 ? '#16a34a' : index % 3 === 1 ? '#f59e0b' : '#ef4444',
          }))}
          overlayTitle="TourSafe live command map"
          overlayText="The operator view uses the same real map layer with tourist pins, a zone polygon, and active route."
        />
      </View>

      <View style={styles.listCard}>
        <Text style={styles.listTitle}>Zone snapshot</Text>
        {demoZones.slice(0, 5).map((zone) => (
          <View key={zone.id} style={styles.row}>
            <MapPinned
              size={16}
              color={zone.zone_type === 'danger' ? '#ef4444' : zone.zone_type === 'warning' ? '#f59e0b' : '#0d9488'}
            />
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{zone.name}</Text>
              <Text style={styles.rowMeta}>
                {zone.tourist_count} tourists · {zone.active_alerts} alerts
              </Text>
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function MiniStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
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
  kpi: {
    flex: 1,
    minWidth: '30%',
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 6,
  },
  kpiLabel: {
    fontSize: 11,
    textTransform: 'uppercase',
    color: 'rgba(100,116,139,0.7)',
    fontWeight: '700',
  },
  kpiValue: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  mapCard: { backgroundColor: '#1a365d', borderRadius: 20, padding: 12 },
  mapTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  mapPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#fff',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  mapPillText: { fontSize: 11, color: '#0f172a', fontWeight: '700' },
  mapNote: { fontSize: 11, color: 'rgba(255,255,255,0.75)' },
  listCard: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  listTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#eef2f7',
  },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowMeta: { marginTop: 4, fontSize: 12, color: 'rgba(100,116,139,0.8)' },
});
