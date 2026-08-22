import React, { useEffect, useState } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Switch,
  ActivityIndicator,
  Modal,
} from 'react-native';
import {
  ShieldCheck,
  Building2,
  MapPin,
  Sliders,
  FileCode2,
  History,
  Activity,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCcw,
  PlayCircle,
  Cpu,
  Layers,
  Search,
} from 'lucide-react-native';
import { useAuthStore } from '@/store/authStore';
import { useGovernanceStore } from '@/store/governanceStore';
import Toast from 'react-native-toast-message';

export default function AdminSettings() {
  const { user, accessToken, isAuthenticated } = useAuthStore();
  const {
    metrics,
    organizations,
    jurisdictions,
    configurations,
    auditLogs,
    systemHealth,
    policySimulation,
    safetySimulation,
    loading,
    fetchOverview,
    fetchOrganizations,
    fetchJurisdictions,
    fetchConfigurations,
    fetchAuditLogs,
    fetchSystemHealth,
    approveConfig,
    rejectConfig,
    activateConfig,
    rollbackConfig,
    runSafetySimulation,
  } = useGovernanceStore();

  const [activeTab, setActiveTab] = useState<'overview' | 'configs' | 'jurisdictions' | 'simulation' | 'health' | 'audit'>('overview');
  const [selectedConfig, setSelectedConfig] = useState<any>(null);
  const [approvalModalVisible, setApprovalModalVisible] = useState(false);
  const [actionReason, setActionReason] = useState('');
  const [isApproving, setIsApproving] = useState(true);
  const [auditSearch, setAuditSearch] = useState('');

  useEffect(() => {
    if (isAuthenticated && accessToken) {
      fetchOverview(accessToken);
      fetchOrganizations(accessToken);
      fetchJurisdictions(accessToken);
      fetchConfigurations(accessToken);
      fetchAuditLogs(accessToken);
      fetchSystemHealth(accessToken);
    }
  }, [isAuthenticated, accessToken]);

  const handleAction = async () => {
    if (!selectedConfig || !accessToken) return;
    if (actionReason.trim().length < 3) {
      Toast.show({ type: 'error', text1: 'Validation Error', text2: 'Please provide a justification of at least 3 characters.' });
      return;
    }

    let ok = false;
    if (isApproving) {
      ok = await approveConfig(accessToken, selectedConfig.configuration_id, actionReason);
      if (ok) Toast.show({ type: 'success', text1: 'Approved', text2: `Configuration ${selectedConfig.version} approved.` });
    } else {
      ok = await rejectConfig(accessToken, selectedConfig.configuration_id, actionReason);
      if (ok) Toast.show({ type: 'info', text1: 'Rejected', text2: `Configuration ${selectedConfig.version} rejected.` });
    }

    if (ok) {
      setApprovalModalVisible(false);
      setActionReason('');
    }
  };

  const handleActivate = async (cfg: any) => {
    if (!accessToken) return;
    const ok = await activateConfig(accessToken, cfg.configuration_id, 'Production promotion by authorized administrator');
    if (ok) {
      Toast.show({ type: 'success', text1: 'Activated', text2: `Configuration ${cfg.version} is now active in production.` });
    }
  };

  const handleRollback = async (cfg: any) => {
    if (!accessToken) return;
    const ok = await rollbackConfig(accessToken, cfg.configuration_id, 'Emergency administrative rollback to prior approved baseline');
    if (ok) {
      Toast.show({ type: 'success', text1: 'Rollback Completed', text2: `Reverted runtime system to ${cfg.version}.` });
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <ShieldCheck size={24} color="#0284c7" />
          <Text style={styles.headerTitle}>TourSafe Authority Governance & Administration</Text>
        </View>
        <Text style={styles.headerSubtitle}>
          Government-grade configuration versioning, multi-tier approvals, policy governance, and immutable audit logs.
        </Text>

        {/* Tab Navigation */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabScroll} contentContainerStyle={styles.tabContainer}>
          <TabButton active={activeTab === 'overview'} label="Overview & KPIs" icon={<Activity size={16} />} onPress={() => setActiveTab('overview')} />
          <TabButton active={activeTab === 'configs'} label="Versioned Policies" icon={<Sliders size={16} />} onPress={() => setActiveTab('configs')} />
          <TabButton active={activeTab === 'jurisdictions'} label="Jurisdictions & Orgs" icon={<Building2 size={16} />} onPress={() => setActiveTab('jurisdictions')} />
          <TabButton active={activeTab === 'simulation'} label="Simulation Sandbox" icon={<PlayCircle size={16} />} onPress={() => setActiveTab('simulation')} />
          <TabButton active={activeTab === 'health'} label="System Health" icon={<Cpu size={16} />} onPress={() => setActiveTab('health')} />
          <TabButton active={activeTab === 'audit'} label="Immutable Audit Logs" icon={<History size={16} />} onPress={() => setActiveTab('audit')} />
        </ScrollView>
      </View>

      <ScrollView style={styles.contentScroll} contentContainerStyle={styles.content}>
        {/* Tab 1: Overview */}
        {activeTab === 'overview' && (
          <View style={styles.tabBody}>
            <View style={styles.kpiGrid}>
              <KpiCard label="Active Responders" value={metrics?.active_responders_count ?? '-'} badge="Field Units" />
              <KpiCard label="Active Geofence Zones" value={metrics?.active_zones_count ?? '-'} badge="2dsphere" />
              <KpiCard label="Active Response Policies" value={metrics?.active_policies_count ?? '-'} badge="Automated" />
              <KpiCard label="Pending Governance Approvals" value={metrics?.pending_approvals_count ?? 0} badge={metrics?.pending_approvals_count ? 'Action Required' : 'Clean'} alert={!!metrics?.pending_approvals_count} />
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>Active Production Intelligence Version</Text>
              <View style={styles.rowBetween}>
                <Text style={styles.textMuted}>Safety Rules & Risk Fusion Engine:</Text>
                <Text style={styles.textHighlight}>{metrics?.active_safety_config_version || 'v1.0.0'}</Text>
              </View>
              <View style={styles.rowBetween}>
                <Text style={styles.textMuted}>System Status:</Text>
                <Text style={{ color: metrics?.system_health_status === 'HEALTHY' ? '#10b981' : '#f59e0b', fontWeight: '700' }}>
                  {metrics?.system_health_status || 'HEALTHY'}
                </Text>
              </View>
              <View style={styles.rowBetween}>
                <Text style={styles.textMuted}>Recent Audit Events (24h):</Text>
                <Text style={styles.textBold}>{metrics?.recent_audit_events_count_24h ?? 0}</Text>
              </View>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>Recent Administrative Modifications</Text>
              {metrics?.recent_changes?.map((c, i) => (
                <View key={i} style={styles.changeRow}>
                  <View style={styles.changeHeader}>
                    <Text style={styles.changeAction}>{c.action}</Text>
                    <Text style={styles.changeType}>{c.resource_type} • {c.actor_role}</Text>
                  </View>
                  <Text style={styles.changeReason}>{c.change_reason || 'Administrative update'}</Text>
                  <Text style={styles.changeTime}>{new Date(c.timestamp).toLocaleString()}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Tab 2: Configurations & Policy Governance */}
        {activeTab === 'configs' && (
          <View style={styles.tabBody}>
            <View style={styles.rowBetween}>
              <Text style={styles.sectionHeader}>Policy & Configuration Lifecycle</Text>
              <TouchableOpacity style={styles.btnSecondary} onPress={() => accessToken && fetchConfigurations(accessToken)}>
                <Text style={styles.btnSecondaryText}>Refresh</Text>
              </TouchableOpacity>
            </View>

            {configurations.map((cfg) => (
              <View key={cfg.configuration_id} style={styles.configCard}>
                <View style={styles.rowBetween}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.configName}>{cfg.name}</Text>
                    <Text style={styles.configMeta}>
                      Type: <Text style={styles.textBold}>{cfg.type}</Text> • Version: <Text style={styles.textHighlight}>{cfg.version}</Text>
                    </Text>
                  </View>
                  <StatusBadge status={cfg.status} />
                </View>

                <Text style={styles.configReason}>"{cfg.change_reason}"</Text>
                <Text style={styles.textSmall}>Author: {cfg.created_by} | Approved By: {cfg.approved_by || 'Pending'}</Text>

                {/* Governance Controls */}
                <View style={styles.configActionRow}>
                  {cfg.status === 'DRAFT' || cfg.status === 'PENDING_APPROVAL' ? (
                    <>
                      <TouchableOpacity
                        style={[styles.btnAction, { backgroundColor: '#0284c7' }]}
                        onPress={() => {
                          setSelectedConfig(cfg);
                          setIsApproving(true);
                          setApprovalModalVisible(true);
                        }}
                      >
                        <Text style={styles.btnActionText}>Review & Approve</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.btnAction, { backgroundColor: '#ef4444' }]}
                        onPress={() => {
                          setSelectedConfig(cfg);
                          setIsApproving(false);
                          setApprovalModalVisible(true);
                        }}
                      >
                        <Text style={styles.btnActionText}>Reject</Text>
                      </TouchableOpacity>
                    </>
                  ) : null}

                  {cfg.status === 'APPROVED' ? (
                    <TouchableOpacity style={[styles.btnAction, { backgroundColor: '#10b981' }]} onPress={() => handleActivate(cfg)}>
                      <Text style={styles.btnActionText}>Promote to Active</Text>
                    </TouchableOpacity>
                  ) : null}

                  {cfg.status === 'RETIRED' ? (
                    <TouchableOpacity style={[styles.btnAction, { backgroundColor: '#f59e0b' }]} onPress={() => handleRollback(cfg)}>
                      <Text style={styles.btnActionText}>Rollback to this Version</Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Tab 3: Jurisdictions & Organizations */}
        {activeTab === 'jurisdictions' && (
          <View style={styles.tabBody}>
            <Text style={styles.sectionHeader}>Governing Organizations</Text>
            {organizations.map((org) => (
              <View key={org.id} style={styles.card}>
                <View style={styles.rowBetween}>
                  <Text style={styles.cardTitle}>{org.name}</Text>
                  <Text style={styles.badgeText}>{org.code}</Text>
                </View>
                <Text style={styles.textMuted}>Type: {org.type} | Status: {org.status}</Text>
                <Text style={styles.textSmall}>Email: {org.contact_email || 'N/A'} | Phone: {org.contact_phone || 'N/A'}</Text>
              </View>
            ))}

            <Text style={[styles.sectionHeader, { marginTop: 16 }]}>Active Geographic Jurisdictions</Text>
            {jurisdictions.map((jur) => (
              <View key={jur.id} style={styles.card}>
                <View style={styles.rowBetween}>
                  <Text style={styles.cardTitle}>{jur.name}</Text>
                  <Text style={styles.badgeText}>{jur.code}</Text>
                </View>
                <Text style={styles.textMuted}>Boundary Type: {jur.boundary.type} | Priority: {jur.overlap_priority}</Text>
                <Text style={styles.textSmall}>
                  Cross-Jurisdiction Dispatches: {jur.cross_jurisdiction_allowed ? 'PERMITTED' : 'RESTRICTED'}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Tab 4: Simulation Sandbox */}
        {activeTab === 'simulation' && (
          <View style={styles.tabBody}>
            <Text style={styles.sectionHeader}>Safety Intelligence Dry-Run Sandbox</Text>
            <Text style={styles.textMuted}>
              Simulate candidate parameters against synthetic telemetry signals without touching production.
            </Text>

            <TouchableOpacity
              style={[styles.btnPrimary, { marginTop: 12 }]}
              onPress={() => accessToken && runSafetySimulation(accessToken)}
            >
              <Text style={styles.btnPrimaryText}>Run Safety Risk Score Simulation</Text>
            </TouchableOpacity>

            {safetySimulation && (
              <View style={[styles.card, { marginTop: 16 }]}>
                <Text style={styles.cardTitle}>Simulation Results</Text>
                <View style={styles.rowBetween}>
                  <Text style={styles.textMuted}>Baseline Score:</Text>
                  <Text style={styles.textBold}>{safetySimulation.composite_risk_score_baseline} ({safetySimulation.baseline_state})</Text>
                </View>
                <View style={styles.rowBetween}>
                  <Text style={styles.textMuted}>Candidate Score:</Text>
                  <Text style={styles.textHighlight}>{safetySimulation.composite_risk_score_candidate} ({safetySimulation.candidate_state})</Text>
                </View>
                <View style={styles.rowBetween}>
                  <Text style={styles.textMuted}>Sensitivity Delta:</Text>
                  <Text style={{ color: safetySimulation.sensitivity_delta >= 0 ? '#ef4444' : '#10b981', fontWeight: '700' }}>
                    {safetySimulation.sensitivity_delta > 0 ? `+${safetySimulation.sensitivity_delta}` : safetySimulation.sensitivity_delta}
                  </Text>
                </View>

                <Text style={[styles.textBold, { marginTop: 12 }]}>Explainability Breakdown:</Text>
                {safetySimulation.explainability.map((exp, idx) => (
                  <Text key={idx} style={styles.textSmall}>• {exp}</Text>
                ))}
              </View>
            )}
          </View>
        )}

        {/* Tab 5: System Health */}
        {activeTab === 'health' && (
          <View style={styles.tabBody}>
            <Text style={styles.sectionHeader}>Subsystem Health Probes</Text>
            {systemHealth?.subsystems.map((sub, idx) => (
              <View key={idx} style={styles.card}>
                <View style={styles.rowBetween}>
                  <Text style={styles.cardTitle}>{sub.subsystem.toUpperCase()}</Text>
                  <Text style={{ color: sub.status === 'HEALTHY' ? '#10b981' : '#ef4444', fontWeight: '700' }}>
                    {sub.status}
                  </Text>
                </View>
                <Text style={styles.textSmall}>Latency: {sub.latency_ms ? `${sub.latency_ms}ms` : 'N/A'}</Text>
                <Text style={styles.textMuted}>Details: {JSON.stringify(sub.details || {})}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Tab 6: Immutable Audit Logs */}
        {activeTab === 'audit' && (
          <View style={styles.tabBody}>
            <View style={styles.rowBetween}>
              <Text style={styles.sectionHeader}>Immutable Audit Explorer</Text>
              <TouchableOpacity style={styles.btnSecondary} onPress={() => accessToken && fetchAuditLogs(accessToken, 1, auditSearch)}>
                <Text style={styles.btnSecondaryText}>Search</Text>
              </TouchableOpacity>
            </View>

            <TextInput
              style={styles.searchInput}
              placeholder="Search by actor, action, or justification..."
              value={auditSearch}
              onChangeText={setAuditSearch}
            />

            {auditLogs.map((log) => (
              <View key={log.audit_id} style={styles.card}>
                <View style={styles.rowBetween}>
                  <Text style={styles.textBold}>{log.action} • {log.resource_type}</Text>
                  <Text style={styles.textSmall}>{new Date(log.timestamp).toLocaleTimeString()}</Text>
                </View>
                <Text style={styles.textMuted}>Actor: {log.actor_role} ({log.actor_id})</Text>
                <Text style={styles.changeReason}>Reason: "{log.change_reason || 'System operation'}"</Text>
                <Text style={styles.hashText}>SHA-256: {log.integrity_hash?.substring(0, 24)}...</Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>

      {/* Approval / Rejection Modal */}
      <Modal visible={approvalModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>{isApproving ? 'Approve Configuration' : 'Reject Configuration'}</Text>
            <Text style={styles.textMuted}>
              {isApproving
                ? 'Sign off on this version for operational readiness. Separation of duties requires reviewer distinct from author.'
                : 'Reject this draft back to the author with mandatory operational reasoning.'}
            </Text>

            <TextInput
              style={styles.modalInput}
              multiline
              numberOfLines={3}
              placeholder="Enter mandatory justification reason..."
              value={actionReason}
              onChangeText={setActionReason}
            />

            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.btnSecondary} onPress={() => setApprovalModalVisible(false)}>
                <Text style={styles.btnSecondaryText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btnPrimary, { backgroundColor: isApproving ? '#0284c7' : '#ef4444' }]}
                onPress={handleAction}
              >
                <Text style={styles.btnPrimaryText}>{isApproving ? 'Confirm Approval' : 'Confirm Rejection'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function TabButton({ active, label, icon, onPress }: { active: boolean; label: string; icon: React.ReactNode; onPress: () => void }) {
  return (
    <TouchableOpacity style={[styles.tabBtn, active && styles.tabBtnActive]} onPress={onPress}>
      {icon}
      <Text style={[styles.tabBtnText, active && styles.tabBtnTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function KpiCard({ label, value, badge, alert }: { label: string; value: any; badge: string; alert?: boolean }) {
  return (
    <View style={[styles.kpiCard, alert && styles.kpiCardAlert]}>
      <Text style={styles.kpiValue}>{value}</Text>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={styles.kpiBadge}>{badge}</Text>
    </View>
  );
}

function StatusBadge({ status }: { status: string }) {
  let bg = '#64748b';
  if (status === 'ACTIVE') bg = '#10b981';
  if (status === 'APPROVED') bg = '#0284c7';
  if (status === 'DRAFT' || status === 'PENDING_APPROVAL') bg = '#f59e0b';
  if (status === 'REJECTED') bg = '#ef4444';

  return (
    <View style={[styles.statusBadge, { backgroundColor: bg }]}>
      <Text style={styles.statusBadgeText}>{status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#1e293b', backgroundColor: '#1e293b' },
  headerTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: '#f8fafc' },
  headerSubtitle: { marginTop: 4, color: '#94a3b8', fontSize: 12 },
  tabScroll: { marginTop: 12 },
  tabContainer: { flexDirection: 'row', gap: 8 },
  tabBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 8, backgroundColor: '#334155' },
  tabBtnActive: { backgroundColor: '#0284c7' },
  tabBtnText: { color: '#cbd5e1', fontSize: 12, fontWeight: '600' },
  tabBtnTextActive: { color: '#ffffff', fontWeight: '800' },
  contentScroll: { flex: 1 },
  content: { padding: 16 },
  tabBody: { gap: 14 },
  sectionHeader: { fontSize: 16, fontWeight: '800', color: '#f8fafc' },
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpiCard: { flex: 1, minWidth: '45%', backgroundColor: '#1e293b', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#334155' },
  kpiCardAlert: { borderColor: '#f59e0b' },
  kpiValue: { fontSize: 24, fontWeight: '900', color: '#f8fafc' },
  kpiLabel: { fontSize: 12, color: '#94a3b8', marginTop: 4 },
  kpiBadge: { fontSize: 10, color: '#38bdf8', marginTop: 6, fontWeight: '700' },
  card: { backgroundColor: '#1e293b', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#334155', gap: 6 },
  cardTitle: { fontSize: 14, fontWeight: '800', color: '#f8fafc' },
  configCard: { backgroundColor: '#1e293b', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#334155', gap: 8 },
  configName: { fontSize: 14, fontWeight: '800', color: '#f8fafc' },
  configMeta: { fontSize: 12, color: '#94a3b8' },
  configReason: { fontSize: 12, color: '#cbd5e1', fontStyle: 'italic' },
  configActionRow: { flexDirection: 'row', gap: 8, marginTop: 6 },
  btnAction: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: 6 },
  btnActionText: { color: '#ffffff', fontSize: 11, fontWeight: '700' },
  btnPrimary: { backgroundColor: '#0284c7', paddingVertical: 10, paddingHorizontal: 16, borderRadius: 8, alignItems: 'center' },
  btnPrimaryText: { color: '#ffffff', fontSize: 13, fontWeight: '700' },
  btnSecondary: { backgroundColor: '#334155', paddingVertical: 6, paddingHorizontal: 12, borderRadius: 6 },
  btnSecondaryText: { color: '#f8fafc', fontSize: 12, fontWeight: '600' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  textMuted: { color: '#94a3b8', fontSize: 12 },
  textHighlight: { color: '#38bdf8', fontWeight: '700' },
  textBold: { color: '#f8fafc', fontWeight: '700' },
  textSmall: { color: '#64748b', fontSize: 11 },
  badgeText: { color: '#38bdf8', fontSize: 11, fontWeight: '700' },
  statusBadge: { paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 },
  statusBadgeText: { color: '#ffffff', fontSize: 10, fontWeight: '800' },
  changeRow: { paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#334155', gap: 2 },
  changeHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  changeAction: { color: '#38bdf8', fontWeight: '800', fontSize: 12 },
  changeType: { color: '#94a3b8', fontSize: 11 },
  changeReason: { color: '#cbd5e1', fontSize: 11 },
  changeTime: { color: '#64748b', fontSize: 10 },
  hashText: { color: '#64748b', fontSize: 9, fontFamily: 'monospace' },
  searchInput: { backgroundColor: '#334155', color: '#f8fafc', padding: 10, borderRadius: 8, fontSize: 12 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalBox: { backgroundColor: '#1e293b', width: '100%', maxWidth: 500, borderRadius: 14, padding: 20, gap: 12, borderWidth: 1, borderColor: '#334155' },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#f8fafc' },
  modalInput: { backgroundColor: '#0f172a', color: '#f8fafc', padding: 12, borderRadius: 8, textAlignVertical: 'top', borderWidth: 1, borderColor: '#334155', fontSize: 12 },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 8 },
});