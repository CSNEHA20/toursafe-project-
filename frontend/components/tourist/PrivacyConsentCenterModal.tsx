import React, { useState, useEffect } from 'react';
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  Switch,
  TextInput,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from 'react-native';
import {
  ShieldCheck,
  X,
  Info,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Download,
  Lock,
} from 'lucide-react-native';
import { usePrivacyStore } from '../../store/privacyStore';
import { ConsentPurpose, PrivacyRequestType } from '../../types/privacy';

interface Props {
  visible: boolean;
  onClose: () => void;
}

const PURPOSES_CONFIG: Array<{
  id: ConsentPurpose;
  title: string;
  category: string;
  description: string;
  retention: string;
  access: string;
  requiredForSafety: boolean;
}> = [
  {
    id: 'LOCATION_TRACKING',
    title: 'Real-Time Location Tracking',
    category: 'Operational Safety',
    description: 'Enables safety zone geofencing, hazard perimeter alerts, and immediate responder dispatch during emergencies.',
    retention: '90 days (730 days if incident-linked)',
    access: 'Authorized Dispatcher, Assigned Field Responders (within 500m / mission)',
    requiredForSafety: true,
  },
  {
    id: 'TELEMETRY_PROCESSING',
    title: 'IMU Sensor Telemetry & Anomaly Inference',
    category: 'Safety Intelligence',
    description: 'Samples 50Hz accelerometer and gyroscope motion vectors to infer falls, collisions, and sudden impact events.',
    retention: '30 days raw / 180 days anomaly events',
    access: 'Automated ML Inference Engine only (no human surveillance)',
    requiredForSafety: false,
  },
  {
    id: 'KYC_VERIFICATION',
    title: 'Digital Tourist Credential (KYC)',
    category: 'Identity & Access',
    description: 'Cryptographically verifies identity documents for issuing verifiable TSQR tourist credentials.',
    retention: '365 days post-departure',
    access: 'Verified Authority KYC reviewers & QR gate scanners',
    requiredForSafety: false,
  },
  {
    id: 'EMERGENCY_COMMUNICATION',
    title: 'Emergency Contact & SMS Notifications',
    category: 'Emergency Dispatch',
    description: 'Enables automated SMS and voice broadcast to designated emergency contacts during SOS escalations.',
    retention: 'Duration of active trip',
    access: 'Automated notification gateway & emergency dispatchers',
    requiredForSafety: true,
  },
];

export function PrivacyConsentCenterModal({ visible, onClose }: Props) {
  const {
    consents,
    requests,
    isLoading,
    fetchConsents,
    grantConsent,
    withdrawConsent,
    fetchRequests,
    submitRequest,
    verifyRequest,
  } = usePrivacyStore();

  const [activeTab, setActiveTab] = useState<'CONSENTS' | 'REQUESTS' | 'EXPORTS'>('CONSENTS');
  const [selectedReqType, setSelectedReqType] = useState<PrivacyRequestType>('ACCESS');
  const [reqNotes, setReqNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (visible) {
      fetchConsents();
      fetchRequests();
    }
  }, [visible]);

  const isConsentGranted = (purpose: ConsentPurpose): boolean => {
    const c = consents.find((x) => x.purpose === purpose);
    return c ? c.status === 'GRANTED' : false;
  };

  const handleToggleConsent = async (purpose: ConsentPurpose, currentGranted: boolean) => {
    try {
      if (currentGranted) {
        await withdrawConsent(purpose, 'Revoked in privacy center');
      } else {
        await grantConsent(purpose);
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to update consent preference.');
    }
  };

  const handleCreateRequest = async () => {
    setSubmitting(true);
    const req = await submitRequest(selectedReqType, [], reqNotes);
    setSubmitting(false);
    if (req) {
      Alert.alert('Request Submitted', `Your privacy request #${req.id.slice(0, 8)} has been logged. Please complete identity verification.`);
      setReqNotes('');
    } else {
      Alert.alert('Error', 'Failed to submit request. Please try again.');
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <View style={styles.iconBox}>
                <ShieldCheck size={22} color="#0D7680" />
              </View>
              <View>
                <Text style={styles.title}>Privacy & Consent Center</Text>
                <Text style={styles.subtitle}>DPDP Act 2023 / GDPR Sovereign Privacy Management</Text>
              </View>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityRole="button" accessibilityLabel="Close privacy center">
              <X size={20} color="#94A3B8" />
            </TouchableOpacity>
          </View>

          {/* Tabs */}
          <View style={styles.tabRow}>
            {(['CONSENTS', 'REQUESTS', 'EXPORTS'] as const).map((tab) => (
              <TouchableOpacity
                key={tab}
                onPress={() => setActiveTab(tab)}
                style={[styles.tab, activeTab === tab && styles.tabActive]}
                accessibilityRole="tab"
                accessibilityState={{ selected: activeTab === tab }}
              >
                <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
                  {tab === 'CONSENTS' ? 'Data Consents' : tab === 'REQUESTS' ? 'Privacy Requests' : 'Data Portability'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Tab Content */}
          <ScrollView style={styles.scrollArea} showsVerticalScrollIndicator={false}>
            {activeTab === 'CONSENTS' && (
              <View style={styles.contentBlock}>
                <View style={styles.infoBanner}>
                  <Info size={14} color="#93C5FD" />
                  <Text style={styles.infoBannerText}>
                    Privacy by Design: TourSafe collects data solely for verified safety & rescue operations. You have the right to modify optional permissions anytime.
                  </Text>
                </View>

                {PURPOSES_CONFIG.map((p) => {
                  const granted = isConsentGranted(p.id);
                  return (
                    <View key={p.id} style={styles.consentCard}>
                      <View style={styles.consentCardTop}>
                        <View style={styles.consentCardLeft}>
                          <View style={styles.consentTitleRow}>
                            <Text style={styles.consentTitle}>{p.title}</Text>
                            {p.requiredForSafety && (
                              <View style={styles.safetyTag}>
                                <Text style={styles.safetyTagText}>Safety Core</Text>
                              </View>
                            )}
                          </View>
                          <Text style={styles.consentDesc}>{p.description}</Text>
                        </View>
                        <Switch
                          value={granted}
                          onValueChange={() => handleToggleConsent(p.id, granted)}
                          trackColor={{ false: '#334155', true: '#0D7680' }}
                          thumbColor={granted ? '#2DD4BF' : '#94A3B8'}
                        />
                      </View>

                      <View style={styles.consentMeta}>
                        <View style={styles.metaRow}>
                          <Text style={styles.metaLabel}>Retention:</Text>
                          <Text style={styles.metaValue}>{p.retention}</Text>
                        </View>
                        <View style={styles.metaRow}>
                          <Text style={styles.metaLabel}>Authorized Access:</Text>
                          <Text style={styles.metaValue}>{p.access}</Text>
                        </View>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}

            {activeTab === 'REQUESTS' && (
              <View style={styles.contentBlock}>
                <View style={styles.formCard}>
                  <Text style={styles.formCardTitle}>Submit Data Subject Request (DSR)</Text>
                  <Text style={styles.formCardSubtitle}>
                    Exercise statutory rights under the DPDP Act 2023 to access, export, correct, or erase your records.
                  </Text>

                  <Text style={styles.fieldLabel}>Request Type:</Text>
                  <View style={styles.pillRow}>
                    {(['ACCESS', 'EXPORT', 'CORRECTION', 'DELETION'] as PrivacyRequestType[]).map((type) => (
                      <TouchableOpacity
                        key={type}
                        onPress={() => setSelectedReqType(type)}
                        style={[styles.pill, selectedReqType === type && styles.pillActive]}
                      >
                        <Text style={[styles.pillText, selectedReqType === type && styles.pillTextActive]}>
                          {type}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <Text style={styles.fieldLabel}>Details / Scope Notes (Optional):</Text>
                  <TextInput
                    value={reqNotes}
                    onChangeText={setReqNotes}
                    placeholder="Specify details, date range, or reason..."
                    placeholderTextColor="#64748B"
                    style={styles.input}
                    multiline
                    numberOfLines={2}
                  />

                  <TouchableOpacity
                    onPress={handleCreateRequest}
                    disabled={submitting}
                    style={styles.submitBtn}
                    accessibilityRole="button"
                  >
                    {submitting ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={styles.submitBtnText}>Submit Privacy Request</Text>
                    )}
                  </TouchableOpacity>
                </View>

                {/* Existing Requests */}
                <Text style={styles.historyHeading}>Request History</Text>
                {requests.length === 0 ? (
                  <Text style={styles.emptyHistory}>No privacy requests logged yet.</Text>
                ) : (
                  requests.map((r) => (
                    <View key={r.id} style={styles.requestItem}>
                      <View style={styles.requestItemHeader}>
                        <Text style={styles.requestId}>
                          #{r.id.slice(0, 8)} • {r.request_type}
                        </Text>
                        <View
                          style={[
                            styles.requestBadge,
                            r.status === 'COMPLETED'
                              ? styles.badgeSuccess
                              : r.status === 'REJECTED'
                              ? styles.badgeDanger
                              : styles.badgeWarning,
                          ]}
                        >
                          <Text style={styles.requestBadgeText}>{r.status}</Text>
                        </View>
                      </View>
                      <Text style={styles.requestDate}>
                        Submitted: {new Date(r.created_at).toLocaleDateString()} • Deadline: {new Date(r.deadline_at).toLocaleDateString()}
                      </Text>

                      {!r.identity_verified && r.status === 'SUBMITTED' && (
                        <TouchableOpacity
                          onPress={async () => {
                            await verifyRequest(r.id);
                            Alert.alert('Verified', 'Session identity verification confirmed.');
                          }}
                          style={styles.verifyBtn}
                        >
                          <Text style={styles.verifyBtnText}>Verify Identity with Session</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  ))
                )}
              </View>
            )}

            {activeTab === 'EXPORTS' && (
              <View style={styles.contentBlock}>
                <View style={styles.formCard}>
                  <Text style={styles.formCardTitle}>Portable Data Export Bundle</Text>
                  <Text style={styles.formCardSubtitle}>
                    Generate a machine-readable JSON package containing all location telemetry, itineraries, verified KYC metadata, and audit events.
                  </Text>

                  <TouchableOpacity
                    onPress={() => {
                      setSelectedReqType('EXPORT');
                      setActiveTab('REQUESTS');
                    }}
                    style={styles.exportTokenBtn}
                  >
                    <Download size={15} color="#0D7680" />
                    <Text style={styles.exportTokenText}>Generate New Export Token</Text>
                  </TouchableOpacity>
                </View>

                {requests.filter((r) => r.export_token).map((r) => (
                  <View key={r.id} style={styles.exportReadyCard}>
                    <View style={styles.requestItemHeader}>
                      <Text style={styles.exportReadyTitle}>Export Ready ({r.id.slice(0, 8)})</Text>
                      <Text style={styles.exportExpiry}>Expires in 24h</Text>
                    </View>
                    <Text style={styles.exportTokenLine}>Token: {r.export_token}</Text>
                    <Text style={styles.exportEndpointLine}>Endpoint: /api/v1/privacy/export/{r.export_token}</Text>
                  </View>
                ))}
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: '#0F172A',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: 1,
    borderColor: '#1E293B',
    maxHeight: '90%',
    padding: 20,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconBox: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: 'rgba(13, 118, 128, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(13, 118, 128, 0.3)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 17,
    fontWeight: '800',
    color: '#F8FAFC',
  },
  subtitle: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 2,
  },
  closeBtn: {
    padding: 8,
    borderRadius: 20,
    backgroundColor: '#1E293B',
  },
  tabRow: {
    flexDirection: 'row',
    backgroundColor: '#020617',
    padding: 4,
    borderRadius: 12,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  tab: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
  },
  tabActive: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
  },
  tabText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
  },
  tabTextActive: {
    color: '#2DD4BF',
  },
  scrollArea: {
    marginTop: 16,
  },
  contentBlock: {
    gap: 14,
    paddingBottom: 36,
  },
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(30, 58, 138, 0.25)',
    borderWidth: 1,
    borderColor: 'rgba(30, 58, 138, 0.4)',
    padding: 12,
    borderRadius: 12,
  },
  infoBannerText: {
    fontSize: 11,
    color: '#93C5FD',
    flex: 1,
    lineHeight: 16,
  },
  consentCard: {
    backgroundColor: 'rgba(30, 41, 59, 0.7)',
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  consentCardTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  consentCardLeft: {
    flex: 1,
    paddingRight: 12,
  },
  consentTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  consentTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#E2E8F0',
  },
  safetyTag: {
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  safetyTagText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#FBBF24',
  },
  consentDesc: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 4,
    lineHeight: 16,
  },
  consentMeta: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: 'rgba(51, 65, 85, 0.4)',
    gap: 4,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metaLabel: {
    fontSize: 10,
    color: '#64748B',
  },
  metaValue: {
    fontSize: 10,
    color: '#94A3B8',
    fontWeight: '600',
  },
  formCard: {
    backgroundColor: 'rgba(30, 41, 59, 0.8)',
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#334155',
  },
  formCardTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#F8FAFC',
    marginBottom: 4,
  },
  formCardSubtitle: {
    fontSize: 11,
    color: '#94A3B8',
    lineHeight: 16,
    marginBottom: 12,
  },
  fieldLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#CBD5E1',
    marginBottom: 6,
  },
  pillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    backgroundColor: '#0F172A',
  },
  pillActive: {
    backgroundColor: 'rgba(13, 118, 128, 0.25)',
    borderColor: '#0D7680',
  },
  pillText: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '600',
  },
  pillTextActive: {
    color: '#2DD4BF',
  },
  input: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 10,
    padding: 10,
    fontSize: 12,
    color: '#F8FAFC',
    marginBottom: 12,
  },
  submitBtn: {
    backgroundColor: '#0D7680',
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  submitBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#ffffff',
  },
  historyHeading: {
    fontSize: 13,
    fontWeight: '700',
    color: '#E2E8F0',
    marginTop: 6,
  },
  emptyHistory: {
    fontSize: 11,
    color: '#64748B',
    fontStyle: 'italic',
  },
  requestItem: {
    backgroundColor: 'rgba(30, 41, 59, 0.5)',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1E293B',
    gap: 6,
  },
  requestItemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  requestId: {
    fontSize: 12,
    fontWeight: '700',
    color: '#CBD5E1',
  },
  requestBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeSuccess: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  badgeDanger: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  badgeWarning: {
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
  },
  requestBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  requestDate: {
    fontSize: 10,
    color: '#64748B',
  },
  verifyBtn: {
    backgroundColor: '#1E293B',
    paddingVertical: 6,
    borderRadius: 6,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  verifyBtnText: {
    fontSize: 11,
    color: '#2DD4BF',
    fontWeight: '600',
  },
  exportTokenBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: 'rgba(13, 118, 128, 0.15)',
    borderWidth: 1,
    borderColor: '#0D7680',
    paddingVertical: 10,
    borderRadius: 10,
  },
  exportTokenText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#2DD4BF',
  },
  exportReadyCard: {
    backgroundColor: 'rgba(30, 41, 59, 0.6)',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(13, 118, 128, 0.4)',
    gap: 4,
  },
  exportReadyTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#2DD4BF',
  },
  exportExpiry: {
    fontSize: 10,
    color: '#94A3B8',
  },
  exportTokenLine: {
    fontSize: 11,
    color: '#CBD5E1',
    fontFamily: 'monospace',
  },
  exportEndpointLine: {
    fontSize: 10,
    color: '#64748B',
  },
});
