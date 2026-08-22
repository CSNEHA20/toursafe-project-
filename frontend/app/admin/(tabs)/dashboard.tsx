import React, { useState } from 'react';
import { ScrollView, View, Text, StyleSheet, TouchableOpacity, Modal, TextInput } from 'react-native';
import { BellRing, Gauge, MapPinned, Users, ShieldAlert, FileText, Activity, AlertTriangle, CheckCircle, ShieldCheck, Clock, Eye } from 'lucide-react-native';
import RoleSwitch from '@/components/RoleSwitch';
import { demoTourists, demoZones, demoActivityFeed } from '@/lib/demoContent';
import { useAnomalyStore } from '@/store/anomalyStore';
import { useSafetyStore } from '@/store/safetyStore';
import { useGeofenceStore } from '@/store/geofenceStore';
import Toast from 'react-native-toast-message';
import { useRouter } from 'expo-router';

export default function AdminDashboard() {
  const router = useRouter();
  const activeAnomalies = useAnomalyStore((state) => Object.values(state.activeAnomalies));
  const activeIncidents = useSafetyStore((state) => Object.values(state.activeIncidents));
  const activeSafetyStates = useSafetyStore((state) => Object.values(state.activeSafetyStates));
  const removeIncident = useSafetyStore((state) => state.removeIncident);

  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
  const [resolveReason, setResolveReason] = useState('');
  const [isResolving, setIsResolving] = useState(false);

  const getSafetyBadgeStyle = (state: string) => {
    switch (state) {
      case 'NORMAL':
        return { bg: '#dcfce7', text: '#15803d', label: 'NORMAL' };
      case 'WATCH':
        return { bg: '#fef9c3', text: '#a16207', label: 'WATCH' };
      case 'ELEVATED':
        return { bg: '#ffedd5', text: '#c2410c', label: 'ELEVATED' };
      case 'INCIDENT_CANDIDATE':
        return { bg: '#fee2e2', text: '#b91c1c', label: 'CANDIDATE' };
      case 'INCIDENT':
        return { bg: '#f87171', text: '#7f1d1d', label: 'INCIDENT' };
      case 'RECOVERING':
        return { bg: '#e0e7ff', text: '#4338ca', label: 'RECOVERING' };
      case 'UNKNOWN':
      default:
        return { bg: '#f1f5f9', text: '#64748b', label: 'UNKNOWN' };
    }
  };

  const handleAcknowledge = (incId: string) => {
    Toast.show({
      type: 'success',
      text1: 'Incident Acknowledged',
      text2: `Incident ${incId.slice(0, 8)} set to ACKNOWLEDGED state.`,
    });
  };

  const handleResolve = () => {
    if (!selectedIncident) return;
    removeIncident(selectedIncident.incident_id);
    setSelectedIncident(null);
    setResolveReason('');
    setIsResolving(false);
    Toast.show({
      type: 'success',
      text1: 'Incident Resolved',
      text2: 'Safety state returning via RECOVERING cooldown pipeline.',
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <RoleSwitch currentRole="authority" />

      <View style={styles.hero}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Authority command center</Text>
          <Text style={styles.title}>TourSafe Safety Orchestration</Text>
          <Text style={styles.subtitle}>
            Multi-signal risk fusion across GPS, geofences, motion anomaly, and telemetry stream quality.
          </Text>
        </View>
        <View style={[styles.alertBubble, activeIncidents.length > 0 && { backgroundColor: '#b91c1c' }]}>
          <ShieldAlert size={24} color="#fff" />
          <Text style={styles.alertBubbleText}>{activeIncidents.length} INC</Text>
        </View>
      </View>

      {/* Primary KPI Grid */}
      <View style={styles.kpiRow}>
        <Kpi icon={<Users size={16} color="#1a365d" />} label="Tourists" value={String(demoTourists.length)} />
        <Kpi icon={<ShieldCheck size={16} color="#059669" />} label="Rule Engine" value="v1.0" />
        <Kpi icon={<Activity size={16} color="#d97706" />} label="Anomalies" value={String(activeAnomalies.length)} />
        <Kpi icon={<AlertTriangle size={16} color="#ef4444" />} label="Incidents" value={String(activeIncidents.length)} />
      </View>

      {/* Active Multi-Signal Incidents Section */}
      {activeIncidents.length > 0 ? (
        <View style={styles.incidentSection}>
          <View style={styles.incidentHeader}>
            <AlertTriangle size={18} color="#b91c1c" />
            <Text style={styles.incidentSectionTitle}>Active Safety Incidents ({activeIncidents.length})</Text>
          </View>
          <Text style={styles.incidentDisclaimer}>
            Multi-signal risk fusion generated incidents with explainable deterministic rule audits.
          </Text>

          {activeIncidents.map((inc) => (
            <View key={inc.incident_id} style={styles.incidentCard}>
              <View style={styles.incidentTopRow}>
                <View style={[styles.statusBadge, { backgroundColor: '#fee2e2' }]}>
                  <Text style={[styles.statusBadgeText, { color: '#991b1b' }]}>{inc.status}</Text>
                </View>
                <Text style={styles.severityTag}>Severity: {inc.severity}</Text>
              </View>

              <View style={styles.reasonsBox}>
                <Text style={styles.reasonsTitle}>Triggered Reasons:</Text>
                {inc.reasons.map((r, idx) => (
                  <Text key={idx} style={styles.reasonText}>• {r}</Text>
                ))}
              </View>

              <View style={styles.incidentActionRow}>
                <TouchableOpacity
                  style={[styles.incBtn, styles.ackBtn]}
                  onPress={() => handleAcknowledge(inc.incident_id)}
                >
                  <Eye size={14} color="#1e3a8a" />
                  <Text style={styles.ackBtnText}>Acknowledge</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.incBtn, styles.resolveBtn]}
                  onPress={() => {
                    setSelectedIncident(inc);
                    setIsResolving(true);
                  }}
                >
                  <CheckCircle size={14} color="#15803d" />
                  <Text style={styles.resolveBtnText}>Resolve</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      ) : (
        <View style={styles.allClearCard}>
          <ShieldCheck size={20} color="#059669" />
          <View style={{ flex: 1 }}>
            <Text style={styles.allClearTitle}>All Monitored Zones & Tourists Safe</Text>
            <Text style={styles.allClearSub}>No active cross-signal incident candidates detected.</Text>
          </View>
        </View>
      )}

      {/* Real-Time ML Motion Anomaly Section */}
      {activeAnomalies.length > 0 && (
        <View style={styles.anomalySection}>
          <View style={styles.anomalyHeader}>
            <Activity size={18} color="#d97706" />
            <Text style={styles.anomalySectionTitle}>Active Motion Anomalies ({activeAnomalies.length})</Text>
          </View>

          {activeAnomalies.map((anom) => (
            <View key={anom.anomaly_id} style={styles.anomalyCard}>
              <View style={styles.anomalyTopRow}>
                <View style={styles.anomalyBadge}>
                  <Text style={styles.anomalyBadgeText}>LSTM MOTION ANOMALY</Text>
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
        <Text style={styles.sectionTitle}>Operational activity stream</Text>
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

      {/* Resolution Modal */}
      <Modal visible={isResolving} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Resolve Incident</Text>
            <Text style={styles.modalSub}>
              Enter resolution justification for audit logging. The tourist state will transition to RECOVERING.
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="e.g. Verified safe via field radio check..."
              value={resolveReason}
              onChangeText={setResolveReason}
              multiline
            />
            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalCancel]}
                onPress={() => setIsResolving(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalConfirm]}
                onPress={handleResolve}
              >
                <Text style={styles.modalConfirmText}>Confirm Resolution</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  alertBubble: { width: 72, height: 72, borderRadius: 22, backgroundColor: '#475569', alignItems: 'center', justifyContent: 'center' },
  alertBubbleText: { color: '#fff', fontWeight: '800', marginTop: 4, fontSize: 11 },
  kpiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpi: { flex: 1, minWidth: '22%', backgroundColor: '#fff', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: '#e2e8f0', gap: 6 },
  kpiLabel: { fontSize: 11, textTransform: 'uppercase', color: 'rgba(100,116,139,0.7)', fontWeight: '700' },
  kpiValue: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  allClearCard: { backgroundColor: '#ecfdf5', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#a7f3d0', flexDirection: 'row', alignItems: 'center', gap: 12 },
  allClearTitle: { fontSize: 14, fontWeight: '800', color: '#065f46' },
  allClearSub: { fontSize: 12, color: '#047857', marginTop: 2 },
  incidentSection: { backgroundColor: '#fef2f2', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#fecaca', gap: 12 },
  incidentHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  incidentSectionTitle: { fontSize: 16, fontWeight: '800', color: '#991b1b' },
  incidentDisclaimer: { fontSize: 12, color: '#b91c1c', lineHeight: 16 },
  incidentCard: { backgroundColor: '#fff', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#fee2e2', gap: 10 },
  incidentTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  statusBadgeText: { fontSize: 11, fontWeight: '800' },
  severityTag: { fontSize: 12, fontWeight: '700', color: '#b91c1c' },
  reasonsBox: { backgroundColor: '#f8fafc', padding: 10, borderRadius: 8, gap: 4 },
  reasonsTitle: { fontSize: 11, fontWeight: '700', color: '#475569', textTransform: 'uppercase' },
  reasonText: { fontSize: 12, color: '#1e293b', lineHeight: 16 },
  incidentActionRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
  incBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  ackBtn: { backgroundColor: '#eff6ff', borderWidth: 1, borderColor: '#bfdbfe' },
  ackBtnText: { color: '#1d4ed8', fontWeight: '700', fontSize: 12 },
  resolveBtn: { backgroundColor: '#f0fdf4', borderWidth: 1, borderColor: '#bbf7d0' },
  resolveBtnText: { color: '#15803d', fontWeight: '700', fontSize: 12 },
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
  anomalyCard: { backgroundColor: '#fff', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: '#fef3c7', gap: 8 },
  anomalyTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  anomalyBadge: { backgroundColor: '#fef3c7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  anomalyBadgeText: { color: '#b45309', fontSize: 10, fontWeight: '800' },
  modelTag: { fontSize: 11, color: '#94a3b8', fontWeight: '600' },
  anomalyGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  gridItem: { flex: 1, minWidth: '45%' },
  gridLabel: { fontSize: 10, textTransform: 'uppercase', color: '#94a3b8', fontWeight: '700' },
  gridVal: { fontSize: 13, fontWeight: '700', color: '#1e293b', marginTop: 2 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.6)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { backgroundColor: '#fff', borderRadius: 20, padding: 20, width: '100%', maxWidth: 440, gap: 14 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  modalSub: { fontSize: 13, color: '#64748b', lineHeight: 18 },
  modalInput: { backgroundColor: '#f8fafc', borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 10, padding: 12, minHeight: 80, textAlignVertical: 'top', fontSize: 14 },
  modalBtnRow: { flexDirection: 'row', gap: 10, marginTop: 6 },
  modalBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  modalCancel: { backgroundColor: '#f1f5f9' },
  modalCancelText: { fontWeight: '700', color: '#475569' },
  modalConfirm: { backgroundColor: '#15803d' },
  modalConfirmText: { fontWeight: '700', color: '#fff' },
});
