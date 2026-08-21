import React from 'react';
import { ScrollView, View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { BellRing, Gauge, MapPinned, Users, ShieldAlert, FileText, Activity, AlertTriangle } from 'lucide-react-native';
import RoleSwitch from '@/components/RoleSwitch';
import { demoTourists, demoZones, demoActivityFeed } from '@/lib/demoContent';
import { useAnomalyStore } from '@/store/anomalyStore';
import Toast from 'react-native-toast-message';
import { useRouter } from 'expo-router';

export default function AdminDashboard() {
  const router = useRouter();
  const activeAnomalies = useAnomalyStore((state) => Object.values(state.activeAnomalies));

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <RoleSwitch currentRole="authority" />

      <View style={styles.hero}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Authority command center</Text>
          <Text style={styles.title}>TourSafe Operational Dashboard</Text>
          <Text style={styles.subtitle}>
            Live tourist tracking, geospatial zone surveillance, and ML motion anomaly observability.
          </Text>
        </View>
        <View style={styles.alertBubble}>
          <ShieldAlert size={24} color="#fff" />
          <Text style={styles.alertBubbleText}>1 SOS</Text>
        </View>
      </View>

      <View style={styles.kpiRow}>
        <Kpi icon={<Users size={16} color="#1a365d" />} label="Tourists" value={String(demoTourists.length)} />
        <Kpi icon={<Activity size={16} color="#d97706" />} label="Sensor Anomalies" value={String(activeAnomalies.length)} />
        <Kpi icon={<BellRing size={16} color="#b45309" />} label="Alerts" value={String(demoActivityFeed.length)} />
        <Kpi icon={<MapPinned size={16} color="#ef4444" />} label="Zones" value={String(demoZones.length)} />
      </View>

      {/* Real-Time ML Motion Anomaly Section */}
      {activeAnomalies.length > 0 && (
        <View style={styles.anomalySection}>
          <View style={styles.anomalyHeader}>
            <Activity size={18} color="#d97706" />
            <Text style={styles.anomalySectionTitle}>Active Motion Anomalies ({activeAnomalies.length})</Text>
          </View>
          <Text style={styles.anomalyDisclaimer}>
            ML-detected kinetic anomaly episodes. Evaluated via 3-second LSTM Autoencoder reconstruction.
          </Text>

          {activeAnomalies.map((anom) => (
            <View key={anom.anomaly_id} style={styles.anomalyCard}>
              <View style={styles.anomalyTopRow}>
                <View style={styles.anomalyBadge}>
                  <Text style={styles.anomalyBadgeText}>MOTION ANOMALY</Text>
                </View>
                <Text style={styles.modelTag}>Model: {anom.model_version}</Text>
              </View>

              <View style={styles.anomalyGrid}>
                <View style={styles.gridItem}>
                  <Text style={styles.gridLabel}>Tourist ID</Text>
                  <Text style={styles.gridVal}>{anom.tourist_id.slice(0, 10)}...</Text>
                </View>
                <View style={styles.gridItem}>
                  <Text style={styles.gridLabel}>Score / Threshold</Text>
                  <Text style={[styles.gridVal, { color: '#b45309', fontWeight: '800' }]}>
                    {anom.current_score.toFixed(2)} / {anom.threshold.toFixed(2)}
                  </Text>
                </View>
                <View style={styles.gridItem}>
                  <Text style={styles.gridLabel}>Peak Score</Text>
                  <Text style={styles.gridVal}>{anom.peak_score.toFixed(2)}</Text>
                </View>
                <View style={styles.gridItem}>
                  <Text style={styles.gridLabel}>Duration</Text>
                  <Text style={styles.gridVal}>{anom.duration_seconds.toFixed(0)}s ({anom.window_count} win)</Text>
                </View>
              </View>
            </View>
          ))}
        </View>
      )}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Quick actions</Text>
        <View style={styles.actionsRow}>
          <Action
            label="Open live map"
            icon={<MapPinned size={16} color="#1a365d" />}
            onPress={() => router.push('/admin/(tabs)/map')}
          />
          <Action
            label="Review incidents"
            icon={<FileText size={16} color="#0d9488" />}
            onPress={() => router.push('/admin/(tabs)/alerts')}
          />
          <Action
            label="Mock broadcast"
            icon={<ShieldAlert size={16} color="#ef4444" />}
            onPress={() =>
              Toast.show({
                type: 'success',
                text1: 'Broadcast queued',
                text2: 'All tourists in the selected zone receive a mock emergency message.',
              })
            }
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Operational snapshot</Text>
        {demoActivityFeed.slice(0, 4).map((item) => (
          <View key={item.text} style={styles.row}>
            <View style={[styles.dot, { backgroundColor: item.color }]} />
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{item.text}</Text>
              <Text style={styles.rowMeta}>{item.sub}</Text>
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

function Action({
  label,
  icon,
  onPress,
}: {
  label: string;
  icon: React.ReactNode;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity style={styles.action} onPress={onPress} activeOpacity={0.85}>
      {icon}
      <Text style={styles.actionText}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  hero: { backgroundColor: '#1a365d', borderRadius: 20, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 14 },
  kicker: { color: 'rgba(255,255,255,0.6)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, fontWeight: '700' },
  title: { color: '#fff', fontSize: 22, fontWeight: '800', marginTop: 6 },
  subtitle: { color: 'rgba(255,255,255,0.75)', marginTop: 8, lineHeight: 20 },
  alertBubble: { width: 72, height: 72, borderRadius: 22, backgroundColor: '#ef4444', alignItems: 'center', justifyContent: 'center' },
  alertBubbleText: { color: '#fff', fontWeight: '800', marginTop: 4 },
  kpiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpi: { flex: 1, minWidth: '22%', backgroundColor: '#fff', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: '#e2e8f0', gap: 6 },
  kpiLabel: { fontSize: 11, textTransform: 'uppercase', color: 'rgba(100,116,139,0.7)', fontWeight: '700' },
  kpiValue: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  section: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  actionsRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  action: { flex: 1, minWidth: '48%', backgroundColor: '#f8fafc', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#e2e8f0', flexDirection: 'row', alignItems: 'center', gap: 10 },
  actionText: { fontWeight: '700', color: '#0f172a' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#eef2f7' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowMeta: { marginTop: 4, fontSize: 12, color: 'rgba(100,116,139,0.8)' },
  anomalySection: { backgroundColor: '#fffbeb', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#fde68a', gap: 10 },
  anomalyHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  anomalySectionTitle: { fontSize: 16, fontWeight: '800', color: '#92400e' },
  anomalyDisclaimer: { fontSize: 12, color: '#b45309', lineHeight: 16 },
  anomalyCard: { backgroundColor: '#fff', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: '#fef3c7', gap: 8 },
  anomalyTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  anomalyBadge: { backgroundColor: '#fef3c7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  anomalyBadgeText: { color: '#b45309', fontSize: 10, fontWeight: '800' },
  modelTag: { fontSize: 11, color: '#94a3b8', fontWeight: '600' },
  anomalyGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  gridItem: { flex: 1, minWidth: '45%' },
  gridLabel: { fontSize: 10, textTransform: 'uppercase', color: '#94a3b8', fontWeight: '700' },
  gridVal: { fontSize: 13, fontWeight: '700', color: '#1e293b', marginTop: 2 },
});
