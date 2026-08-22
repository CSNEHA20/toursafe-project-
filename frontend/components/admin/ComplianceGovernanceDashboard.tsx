import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useComplianceStore } from '../../store/complianceStore';
import { usePrivacyStore } from '../../store/privacyStore';
import { FrameworkType } from '../../types/compliance';

export const ComplianceGovernanceDashboard: React.FC = () => {
  const [activeSection, setActiveSection] = useState<
    'FRAMEWORKS' | 'RETENTION' | 'LEGAL_HOLDS' | 'ACCESS_PAM' | 'VENDORS' | 'DSR_QUEUE' | 'AUDITOR'
  >('FRAMEWORKS');

  const [selectedFramework, setSelectedFramework] = useState<FrameworkType>('ISO_27001');
  const [bgRole, setBgRole] = useState('SUPER_ADMIN');
  const [bgReason, setBgReason] = useState('');
  const [bgScope, setBgScope] = useState('SYSTEM_RECOVERY');
  const [holdTitle, setHoldTitle] = useState('');
  const [holdReason, setHoldReason] = useState('');
  const [holdScopeId, setHoldScopeId] = useState('');

  const {
    policies,
    legalHolds,
    vendors,
    accessReviews,
    breakGlassSessions,
    readinessReports,
    isLoading,
    fetchPolicies,
    triggerRetentionRun,
    approvePolicy,
    fetchLegalHolds,
    createLegalHold,
    releaseLegalHold,
    fetchVendors,
    updateVendorReview,
    fetchAccessReviews,
    requestBreakGlass,
    fetchBreakGlassSessions,
    revokeBreakGlass,
    fetchFrameworkReadiness,
    fetchAuditorExport,
  } = useComplianceStore();

  const { requests: dsrRequests, fetchRequests: fetchDsrRequests, reviewRequest: reviewDsr } = usePrivacyStore();

  useEffect(() => {
    fetchPolicies();
    fetchLegalHolds();
    fetchVendors();
    fetchAccessReviews();
    fetchBreakGlassSessions();
    fetchFrameworkReadiness(selectedFramework);
    fetchDsrRequests();
  }, [selectedFramework]);

  const currentReport = readinessReports[selectedFramework];

  const handleCreateHold = async () => {
    if (!holdTitle || !holdReason || !holdScopeId) {
      Alert.alert('Missing Fields', 'Please fill title, reason, and target user/incident ID.');
      return;
    }
    const hold = await createLegalHold({
      title: holdTitle,
      reason: holdReason,
      scope_type: 'USER',
      scope_id: holdScopeId,
      data_categories: ['LOCATION', 'TELEMETRY', 'IDENTITY', 'INCIDENT'],
    });
    if (hold) {
      Alert.alert('Hold Placed', `Legal hold #${hold.id} is now ACTIVE. Automated deletion blocked.`);
      setHoldTitle('');
      setHoldReason('');
      setHoldScopeId('');
    }
  };

  const handleRequestBreakGlass = async () => {
    if (!bgReason) {
      Alert.alert('Reason Required', 'Emergency elevation requires verified justification.');
      return;
    }
    const sess = await requestBreakGlass(bgRole, bgReason, bgScope, 2);
    if (sess) {
      Alert.alert('Elevated Session Active', `Break-Glass #${sess.id} active for 2 hours. Audited.`);
      setBgReason('');
    }
  };

  return (
    <View className="flex-1 bg-slate-950 p-4">
      {/* Top Banner Disclaimer */}
      <View className="bg-amber-950/30 border border-amber-800/40 p-3 rounded-2xl mb-4 flex-row items-center space-x-3">
        <Ionicons name="warning-outline" size={20} color="#fbbf24" />
        <View className="flex-1">
          <Text className="text-xs font-bold text-amber-300">Regulatory Readiness & Governance Mode</Text>
          <Text className="text-[11px] text-amber-400/80">
            Technical readiness assessment only; not legal certification. Legal compliance requires qualified jurisdictional review.
          </Text>
        </View>
      </View>

      {/* Navigation Sub-Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mb-4">
        <View className="flex-row space-x-2">
          {(
            [
              { id: 'FRAMEWORKS', label: 'Framework Controls', icon: 'ribbon-outline' },
              { id: 'RETENTION', label: 'Retention & Deletion', icon: 'timer-outline' },
              { id: 'LEGAL_HOLDS', label: 'Legal Holds', icon: 'lock-closed-outline' },
              { id: 'ACCESS_PAM', label: 'Access & Break-Glass', icon: 'key-outline' },
              { id: 'VENDORS', label: 'Third-Party Processors', icon: 'business-outline' },
              { id: 'DSR_QUEUE', label: 'Privacy DSR Queue', icon: 'person-circle-outline' },
              { id: 'AUDITOR', label: 'Auditor Portal', icon: 'document-text-outline' },
            ] as const
          ).map((t) => (
            <TouchableOpacity
              key={t.id}
              onPress={() => setActiveSection(t.id)}
              className={`flex-row items-center space-x-2 px-3.5 py-2.5 rounded-xl border ${
                activeSection === t.id
                  ? 'bg-teal-500/20 border-teal-500/60'
                  : 'bg-slate-900 border-slate-800'
              }`}
            >
              <Ionicons
                name={t.icon}
                size={16}
                color={activeSection === t.id ? '#2dd4bf' : '#94a3b8'}
              />
              <Text
                className={`text-xs font-bold ${
                  activeSection === t.id ? 'text-teal-300' : 'text-slate-400'
                }`}
              >
                {t.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Main Content Area */}
      <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
        {/* SECTION 1: FRAMEWORKS */}
        {activeSection === 'FRAMEWORKS' && (
          <View className="space-y-4 pb-12">
            <View className="flex-row flex-wrap gap-2 mb-2">
              {(['ISO_27001', 'SOC_2', 'GDPR_READINESS', 'DPDP_READINESS', 'NIST_CSF'] as FrameworkType[]).map((fw) => (
                <TouchableOpacity
                  key={fw}
                  onPress={() => setSelectedFramework(fw)}
                  className={`px-3 py-1.5 rounded-lg border ${
                    selectedFramework === fw ? 'bg-slate-800 border-teal-500' : 'bg-slate-900/60 border-slate-800'
                  }`}
                >
                  <Text className={`text-xs font-bold ${selectedFramework === fw ? 'text-teal-400' : 'text-slate-400'}`}>
                    {fw.replace('_', ' ')}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {currentReport ? (
              <View className="bg-slate-900 border border-slate-800 p-4 rounded-2xl space-y-4">
                <View className="flex-row justify-between items-center">
                  <View>
                    <Text className="text-base font-bold text-slate-100">{currentReport.framework} Readiness</Text>
                    <Text className="text-xs text-slate-400">{currentReport.total_controls} Technical Controls Mapped</Text>
                  </View>
                  <View className="items-end">
                    <Text className="text-2xl font-black text-teal-400">{currentReport.readiness_percentage}%</Text>
                    <Text className="text-[10px] text-slate-500 uppercase tracking-widest">Readiness Score</Text>
                  </View>
                </View>

                {/* Progress Bar */}
                <View className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden flex-row">
                  <View style={{ width: `${currentReport.readiness_percentage}%` }} className="bg-teal-500 h-full" />
                </View>

                {/* Controls List */}
                <Text className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-2">Mapped Controls & Evidences</Text>
                {currentReport.controls_summary.map((ctrl) => (
                  <View key={ctrl.control_id} className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-1.5">
                    <View className="flex-row items-center justify-between">
                      <Text className="text-xs font-bold text-slate-200">
                        {ctrl.control_id} • {ctrl.title}
                      </Text>
                      <View className="bg-emerald-500/20 px-2 py-0.5 rounded border border-emerald-500/30">
                        <Text className="text-[10px] font-bold text-emerald-400">{ctrl.implementation_status}</Text>
                      </View>
                    </View>
                    <Text className="text-[11px] text-slate-400">{ctrl.description}</Text>
                    <View className="flex-row items-center space-x-2 pt-1">
                      <Text className="text-[10px] text-slate-500 font-mono">Evidence: {ctrl.evidence_refs.join(', ')}</Text>
                    </View>
                  </View>
                ))}
              </View>
            ) : (
              <ActivityIndicator size="small" color="#2dd4bf" className="py-6" />
            )}
          </View>
        )}

        {/* SECTION 2: RETENTION */}
        {activeSection === 'RETENTION' && (
          <View className="space-y-4 pb-12">
            <View className="flex-row justify-between items-center">
              <Text className="text-sm font-bold text-slate-200">Active Retention Policies</Text>
              <TouchableOpacity
                onPress={async () => {
                  const res = await triggerRetentionRun(false);
                  Alert.alert('Retention Run Complete', `Deleted: ${res?.total_records_deleted || 0}, Blocked by Hold: ${res?.total_records_retained_legal_hold || 0}`);
                }}
                className="bg-teal-600 px-3 py-1.5 rounded-lg flex-row items-center space-x-1.5"
              >
                <Ionicons name="play" size={12} color="#fff" />
                <Text className="text-xs font-bold text-white">Execute Sweep</Text>
              </TouchableOpacity>
            </View>

            {policies.map((p) => (
              <View key={p.id} className="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-2">
                <View className="flex-row justify-between items-center">
                  <View className="flex-row items-center space-x-2">
                    <Text className="text-sm font-bold text-slate-100">{p.data_type}</Text>
                    <Text className="text-xs font-mono text-slate-500">v{p.version}</Text>
                  </View>
                  <View className={`px-2 py-0.5 rounded ${p.status === 'ACTIVE' ? 'bg-teal-500/20' : 'bg-slate-800'}`}>
                    <Text className={`text-[10px] font-bold ${p.status === 'ACTIVE' ? 'text-teal-400' : 'text-slate-400'}`}>
                      {p.status}
                    </Text>
                  </View>
                </View>
                <Text className="text-xs text-slate-400">{p.description}</Text>
                <View className="flex-row justify-between pt-2 border-t border-slate-800 text-[11px]">
                  <Text className="text-slate-500">Retention Window: <Text className="text-slate-300 font-bold">{p.retention_period_days} Days</Text></Text>
                  <Text className="text-slate-500">Action: <Text className="text-slate-300">{p.deletion_behavior}</Text></Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* SECTION 3: LEGAL HOLDS */}
        {activeSection === 'LEGAL_HOLDS' && (
          <View className="space-y-4 pb-12">
            <View className="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-3">
              <Text className="text-sm font-bold text-slate-200">Place New Legal Hold</Text>
              <TextInput
                value={holdTitle}
                onChangeText={setHoldTitle}
                placeholder="Case / Warrant / Investigation Title"
                placeholderTextColor="#64748b"
                className="bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200"
              />
              <TextInput
                value={holdScopeId}
                onChangeText={setHoldScopeId}
                placeholder="Target User ID or Incident ID"
                placeholderTextColor="#64748b"
                className="bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200"
              />
              <TextInput
                value={holdReason}
                onChangeText={setHoldReason}
                placeholder="Statutory / Investigative Reason"
                placeholderTextColor="#64748b"
                className="bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200"
              />
              <TouchableOpacity
                onPress={handleCreateHold}
                className="bg-amber-600 p-2.5 rounded-xl items-center"
              >
                <Text className="text-xs font-bold text-white">Apply Protective Hold</Text>
              </TouchableOpacity>
            </View>

            <Text className="text-sm font-bold text-slate-200 mt-2">Active Holds Register</Text>
            {legalHolds.map((h) => (
              <View key={h.id} className="bg-slate-900 p-4 rounded-2xl border border-amber-500/30 space-y-2">
                <View className="flex-row justify-between items-center">
                  <Text className="text-xs font-bold text-amber-300">{h.title}</Text>
                  <View className="bg-amber-500/20 px-2 py-0.5 rounded">
                    <Text className="text-[10px] font-bold text-amber-400">{h.status}</Text>
                  </View>
                </View>
                <Text className="text-xs text-slate-400">Target: {h.scope_id} ({h.scope_type})</Text>
                <Text className="text-xs text-slate-500">Reason: {h.reason}</Text>

                {h.status === 'ACTIVE' && (
                  <TouchableOpacity
                    onPress={async () => {
                      await releaseLegalHold(h.id, 'Investigation closed');
                      Alert.alert('Hold Released', `Legal hold #${h.id} released.`);
                    }}
                    className="bg-slate-800 py-1.5 rounded-lg items-center mt-2 border border-slate-700"
                  >
                    <Text className="text-xs font-bold text-slate-300">Release Hold</Text>
                  </TouchableOpacity>
                )}
              </View>
            ))}
          </View>
        )}

        {/* SECTION 4: ACCESS & BREAK-GLASS */}
        {activeSection === 'ACCESS_PAM' && (
          <View className="space-y-4 pb-12">
            <View className="bg-slate-900 p-4 rounded-2xl border border-red-500/30 space-y-3">
              <View className="flex-row items-center space-x-2">
                <Ionicons name="key" size={16} color="#f87171" />
                <Text className="text-sm font-bold text-red-400">Emergency Break-Glass PAM Elevation</Text>
              </View>
              <Text className="text-xs text-slate-400">
                Grants temporary audited high-privilege access for disaster recovery or emergency incident overrides.
              </Text>
              <TextInput
                value={bgReason}
                onChangeText={setBgReason}
                placeholder="Operational justification (mandatory for audit)..."
                placeholderTextColor="#64748b"
                className="bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200"
              />
              <TouchableOpacity
                onPress={handleRequestBreakGlass}
                className="bg-red-600/80 p-2.5 rounded-xl items-center border border-red-500"
              >
                <Text className="text-xs font-bold text-white">Activate 2-Hour Elevation</Text>
              </TouchableOpacity>
            </View>

            <Text className="text-sm font-bold text-slate-200 mt-2">Break-Glass Audit Stream</Text>
            {breakGlassSessions.map((bg) => (
              <View key={bg.id} className="bg-slate-900 p-3 rounded-xl border border-slate-800 space-y-1">
                <View className="flex-row justify-between items-center">
                  <Text className="text-xs font-bold text-slate-200">{bg.user_email} • {bg.requested_role}</Text>
                  <Text className="text-[10px] font-bold text-teal-400">{bg.status}</Text>
                </View>
                <Text className="text-xs text-slate-400">Justification: {bg.justification}</Text>
                <Text className="text-[10px] text-slate-500">Expires: {new Date(bg.expires_at).toLocaleTimeString()}</Text>
              </View>
            ))}
          </View>
        )}

        {/* SECTION 5: VENDORS */}
        {activeSection === 'VENDORS' && (
          <View className="space-y-4 pb-12">
            <Text className="text-sm font-bold text-slate-200">Third-Party Data Processor Register</Text>
            {vendors.map((v) => (
              <View key={v.id} className="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-2">
                <View className="flex-row justify-between items-center">
                  <Text className="text-sm font-bold text-slate-100">{v.vendor_name} ({v.service_name})</Text>
                  <View className="bg-teal-500/20 px-2 py-0.5 rounded">
                    <Text className="text-[10px] font-bold text-teal-400">{v.security_review_status}</Text>
                  </View>
                </View>
                <Text className="text-xs text-slate-400">{v.purpose}</Text>
                <View className="bg-slate-950 p-2.5 rounded-xl space-y-1 text-[11px]">
                  <Text className="text-slate-500">Data Shared: <Text className="text-slate-300">{v.data_shared.join(', ')}</Text></Text>
                  <Text className="text-slate-500">Residency Region: <Text className="text-slate-300">{v.data_residency_region}</Text></Text>
                  <Text className="text-slate-500">Cross-Border Transfer: <Text className="text-slate-300">{v.cross_border_transfer ? 'YES' : 'NO'}</Text></Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* SECTION 6: DSR QUEUE */}
        {activeSection === 'DSR_QUEUE' && (
          <View className="space-y-4 pb-12">
            <Text className="text-sm font-bold text-slate-200">Pending Data Subject Requests (DSR)</Text>
            {dsrRequests.map((r) => (
              <View key={r.id} className="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-2">
                <View className="flex-row justify-between items-center">
                  <Text className="text-xs font-bold text-slate-200">#{r.id.slice(0, 8)} • {r.request_type}</Text>
                  <Text className="text-[10px] font-bold text-amber-400">{r.status}</Text>
                </View>
                <Text className="text-xs text-slate-400">Subject: {r.subject_id}</Text>
                <Text className="text-[11px] text-slate-500">Scope: {r.scope.join(', ')}</Text>

                {r.status !== 'COMPLETED' && r.status !== 'REJECTED' && (
                  <View className="flex-row space-x-2 pt-2">
                    <TouchableOpacity
                      onPress={async () => {
                        await reviewDsr(r.id, 'APPROVE');
                        Alert.alert('Approved', `Executed ${r.request_type} request #${r.id.slice(0, 8)}`);
                      }}
                      className="flex-1 bg-teal-600 py-1.5 rounded-lg items-center"
                    >
                      <Text className="text-xs font-bold text-white">Approve & Execute</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={async () => {
                        await reviewDsr(r.id, 'REJECT', 'Rejected by administrator');
                        Alert.alert('Rejected', `Rejected request #${r.id.slice(0, 8)}`);
                      }}
                      className="flex-1 bg-slate-800 py-1.5 rounded-lg items-center border border-slate-700"
                    >
                      <Text className="text-xs font-bold text-slate-400">Reject</Text>
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            ))}
          </View>
        )}

        {/* SECTION 7: AUDITOR */}
        {activeSection === 'AUDITOR' && (
          <View className="space-y-4 pb-12">
            <View className="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-3">
              <Text className="text-sm font-bold text-slate-100">Sanitized Compliance Evidence Export</Text>
              <Text className="text-xs text-slate-400">
                Generates a formal, machine-readable audit report containing framework control mappings, active retention policies, vendor DPA statuses, and hash-chained audit trails stripped of operational PII.
              </Text>
              <TouchableOpacity
                onPress={async () => {
                  const bundle = await fetchAuditorExport();
                  if (bundle) {
                    Alert.alert('Audit Package Ready', `Export generated. Total controls: ${Object.keys(bundle.framework_readiness).length} frameworks.`);
                  }
                }}
                className="bg-teal-600 p-3 rounded-xl items-center"
              >
                <Text className="text-xs font-bold text-white">Generate Auditor Package</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
};
