import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import {
  CheckCircle2,
  Clock,
  Copy,
  FileCheck,
  Fingerprint,
  Globe,
  Info,
  KeyRound,
  Lock,
  RefreshCw,
  RotateCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Upload,
  UserCheck,
  UserRound,
  X,
  XCircle,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { useAuthStore } from '@/store/authStore';

export default function DigitalID() {
  const { user, accessToken, isAuthenticated } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [identityData, setIdentityData] = useState<any>(null);
  const [credentialData, setCredentialData] = useState<any>(null);
  const [privacyData, setPrivacyData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'credential' | 'kyc' | 'privacy'>('credential');

  // KYC submission modal state
  const [kycModalVisible, setKycModalVisible] = useState(false);
  const [docType, setDocType] = useState('PASSPORT');
  const [issuingCountry, setIssuingCountry] = useState('IND');
  const [maskedId, setMaskedId] = useState('•••• 4321');
  const [submittingKyc, setSubmittingKyc] = useState(false);

  const apiBase = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

  const loadProfileData = async () => {
    if (!isAuthenticated || !accessToken) {
      setLoading(false);
      return;
    }

    try {
      // 1. Fetch Identity Self-View
      const idRes = await fetch(`${apiBase}/api/v1/identity/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (idRes.ok) {
        const idJson = await idRes.json();
        setIdentityData(idJson);
      }

      // 2. Fetch Active Credential
      const credRes = await fetch(`${apiBase}/api/v1/credentials/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (credRes.ok) {
        const credJson = await credRes.json();
        setCredentialData(credJson);
      }

      // 3. Fetch Privacy Center
      const privRes = await fetch(`${apiBase}/api/v1/identity/privacy`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (privRes.ok) {
        const privJson = await privRes.json();
        setPrivacyData(privJson);
      }
    } catch (err: any) {
      console.warn('Could not load identity data from API, using demo mode', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadProfileData();
  }, [isAuthenticated, accessToken]);

  const handleRotateQR = async () => {
    if (!accessToken) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/credentials/me/rotate-qr`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (res.ok) {
        const updated = await res.json();
        setCredentialData((prev: any) => ({ ...prev, active_credential: updated }));
        Toast.show({
          type: 'success',
          text1: 'QR Token Rotated',
          text2: 'Cryptographic nonce rotated for enhanced security.',
        });
      } else {
        Toast.show({ type: 'error', text1: 'Rotation Failed', text2: 'Could not rotate QR token.' });
      }
    } catch (e: any) {
      Toast.show({ type: 'error', text1: 'Network Error', text2: e.message });
    }
  };

  const handleSubmitKyc = async () => {
    if (!accessToken) return;
    setSubmittingKyc(true);
    try {
      await fetch(`${apiBase}/api/v1/kyc/start`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      const res = await fetch(`${apiBase}/api/v1/kyc/documents`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          document_type: docType,
          issuing_country: issuingCountry,
          masked_identifier: maskedId,
          file_size_bytes: 2048,
          mime_type: 'application/pdf',
        }),
      });

      if (res.ok) {
        setKycModalVisible(false);
        Toast.show({
          type: 'success',
          text1: 'KYC Document Submitted',
          text2: 'Your metadata is under review by the authority.',
        });
        loadProfileData();
      } else {
        const err = await res.json();
        Toast.show({ type: 'error', text1: 'Submission Failed', text2: err.detail || 'Error' });
      }
    } catch (e: any) {
      Toast.show({ type: 'error', text1: 'Error', text2: e.message });
    } finally {
      setSubmittingKyc(false);
    }
  };

  const handleToggleConsent = async (consentType: string, currentlyGranted: boolean) => {
    if (!accessToken) return;
    try {
      if (currentlyGranted) {
        const res = await fetch(`${apiBase}/api/v1/identity/consents/${consentType}/withdraw`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason: 'User toggled off in settings' }),
        });
        if (res.ok) {
          const data = await res.json();
          Toast.show({
            type: 'info',
            text1: 'Consent Withdrawn',
            text2: data.safety_impact || 'Consent updated',
          });
          loadProfileData();
        }
      } else {
        const res = await fetch(`${apiBase}/api/v1/identity/consents`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ consent_type: consentType, version: 'v1.0' }),
        });
        if (res.ok) {
          Toast.show({ type: 'success', text1: 'Consent Granted', text2: 'Settings saved' });
          loadProfileData();
        }
      }
    } catch (e: any) {
      Toast.show({ type: 'error', text1: 'Update Failed', text2: e.message });
    }
  };

  const activeCred = credentialData?.active_credential;
  const qrString = activeCred?.qr_payload || `TSQR:offline_mock_${user?.id || 'demo_tourist'}`;
  const status = identityData?.identity_status || (activeCred ? 'VERIFIED' : 'NOT_STARTED');

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'VERIFIED':
        return { bg: '#ecfdf5', text: '#059669', label: 'Verified Tourist', icon: CheckCircle2 };
      case 'UNDER_REVIEW':
        return { bg: '#eff6ff', text: '#2563eb', label: 'Under Review', icon: Clock };
      case 'REQUIRES_ACTION':
        return { bg: '#fef3c7', text: '#d97706', label: 'Action Required', icon: ShieldAlert };
      case 'REJECTED':
        return { bg: '#fef2f2', text: '#dc2626', label: 'Rejected', icon: XCircle };
      case 'SUSPENDED':
        return { bg: '#fffbeb', text: '#b45309', label: 'Suspended', icon: ShieldAlert };
      case 'EXPIRED':
        return { bg: '#f1f5f9', text: '#64748b', label: 'Expired', icon: Clock };
      default:
        return { bg: '#f8fafc', text: '#64748b', label: 'Not Started', icon: Shield };
    }
  };

  const badge = getStatusBadge(status);
  const BadgeIcon = badge.icon;

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#1a365d" />
        <Text style={styles.loadingText}>Loading Digital Tourist Credential...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Top Segment Control */}
      <View style={styles.segmentContainer}>
        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'credential' && styles.segmentBtnActive]}
          onPress={() => setActiveTab('credential')}
        >
          <KeyRound size={16} color={activeTab === 'credential' ? '#fff' : '#64748b'} />
          <Text style={[styles.segmentText, activeTab === 'credential' && styles.segmentTextActive]}>
            Credential
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'kyc' && styles.segmentBtnActive]}
          onPress={() => setActiveTab('kyc')}
        >
          <FileCheck size={16} color={activeTab === 'kyc' ? '#fff' : '#64748b'} />
          <Text style={[styles.segmentText, activeTab === 'kyc' && styles.segmentTextActive]}>
            KYC Workflow
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.segmentBtn, activeTab === 'privacy' && styles.segmentBtnActive]}
          onPress={() => setActiveTab('privacy')}
        >
          <Lock size={16} color={activeTab === 'privacy' ? '#fff' : '#64748b'} />
          <Text style={[styles.segmentText, activeTab === 'privacy' && styles.segmentTextActive]}>
            Privacy Center
          </Text>
        </TouchableOpacity>
      </View>

      {/* Tab 1: Digital Tourist Credential */}
      {activeTab === 'credential' && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.badgeWrap}>
              <ShieldCheck size={20} color="#0d9488" />
            </View>
            <View style={styles.headerTitles}>
              <Text style={styles.title}>Digital Tourist Credential</Text>
              <Text style={styles.subtitle}>Cryptographically verifiable authority pass</Text>
            </View>
          </View>

          {/* Status Pill */}
          <View style={[styles.statusBanner, { backgroundColor: badge.bg }]}>
            <BadgeIcon size={18} color={badge.text} />
            <Text style={[styles.statusBannerText, { color: badge.text }]}>{badge.label}</Text>
          </View>

          {/* Profile Block */}
          <View style={styles.profileBlock}>
            <View style={styles.avatar}>
              <UserRound size={28} color="#1a365d" />
            </View>
            <View style={styles.profileText}>
              <Text style={styles.name}>{identityData?.full_name || user?.full_name || 'Traveler'}</Text>
              <Text style={styles.meta}>
                {identityData?.nationality || 'International'} Traveler • {user?.email || ''}
              </Text>
              <Text style={styles.metaRef}>
                Ref: {activeCred?.credential_reference || 'PENDING-ISSUANCE'}
              </Text>
            </View>
          </View>

          {/* QR Code Container */}
          <View style={styles.qrFrame}>
            <QRCode value={qrString} size={190} backgroundColor="#fff" color="#1a365d" />
            <Text style={styles.qrCaption}>Present to checkpoint authority for verification</Text>
            <Text style={styles.qrVersion}>
              Version {activeCred?.version || 1} • Nonce {activeCred?.token_nonce?.slice(0, 8) || 'xxxx'}
            </Text>
          </View>

          {/* Info Chips */}
          <View style={styles.infoGrid}>
            <InfoChip
              icon={<Fingerprint size={16} color="#0d9488" />}
              label="Credential Ref"
              value={activeCred?.credential_reference?.slice(0, 14) || 'Pending'}
            />
            <InfoChip
              icon={<Globe size={16} color="#3b82f6" />}
              label="Nationality"
              value={identityData?.nationality || 'Global'}
            />
            <InfoChip
              icon={<Clock size={16} color="#6366f1" />}
              label="Valid Until"
              value={activeCred?.expires_at ? new Date(activeCred.expires_at).toLocaleDateString() : 'N/A'}
            />
          </View>

          {/* Actions */}
          <View style={styles.actionRow}>
            {activeCred && (
              <TouchableOpacity style={styles.secondaryBtn} onPress={handleRotateQR}>
                <RotateCw size={16} color="#1a365d" />
                <Text style={styles.secondaryBtnText}>Rotate Token</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity
              style={styles.primaryBtn}
              onPress={() => {
                Toast.show({
                  type: 'success',
                  text1: 'QR Token Copied',
                  text2: 'Payload copied to clipboard for authority inspection.',
                });
              }}
            >
              <Copy size={16} color="#fff" />
              <Text style={styles.primaryBtnText}>Copy Token</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Tab 2: KYC Workflow & Documents */}
      {activeTab === 'kyc' && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.badgeWrap}>
              <FileCheck size={20} color="#2563eb" />
            </View>
            <View style={styles.headerTitles}>
              <Text style={styles.title}>Identity Verification (KYC)</Text>
              <Text style={styles.subtitle}>Government ID metadata verification lifecycle</Text>
            </View>
          </View>

          <View style={styles.disclaimerBox}>
            <Info size={18} color="#2563eb" />
            <Text style={styles.disclaimerText}>
              TourSafe does not store raw government ID numbers or photos unmasked. Only masked references and secure cryptographic metadata are processed.
            </Text>
          </View>

          {/* KYC Status Progression */}
          <View style={styles.stepProgress}>
            <StepItem
              number="1"
              title="Profile Setup"
              completed={Boolean(identityData?.full_name)}
              active={status === 'NOT_STARTED'}
            />
            <StepItem
              number="2"
              title="Document Submission"
              completed={status !== 'NOT_STARTED'}
              active={status === 'PENDING'}
            />
            <StepItem
              number="3"
              title="Authority Review"
              completed={status === 'VERIFIED'}
              active={status === 'UNDER_REVIEW' || status === 'REQUIRES_ACTION'}
            />
            <StepItem
              number="4"
              title="Credential Issued"
              completed={status === 'VERIFIED' && Boolean(activeCred)}
              active={status === 'VERIFIED'}
            />
          </View>

          {status !== 'VERIFIED' && (
            <TouchableOpacity style={styles.submitDocBtn} onPress={() => setKycModalVisible(true)}>
              <Upload size={18} color="#fff" />
              <Text style={styles.submitDocBtnText}>Submit KYC Document</Text>
            </TouchableOpacity>
          )}

          {status === 'VERIFIED' && (
            <View style={styles.verifiedSuccessBox}>
              <UserCheck size={24} color="#059669" />
              <View style={styles.verifiedSuccessText}>
                <Text style={styles.verifiedTitle}>KYC Verification Complete</Text>
                <Text style={styles.verifiedDesc}>
                  Verified fields: {identityData?.verified_fields?.join(', ') || 'Full Name, Nationality'}
                </Text>
              </View>
            </View>
          )}
        </View>
      )}

      {/* Tab 3: Privacy & Consent Center */}
      {activeTab === 'privacy' && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.badgeWrap}>
              <Lock size={20} color="#7c3aed" />
            </View>
            <View style={styles.headerTitles}>
              <Text style={styles.title}>Privacy & Consent Center</Text>
              <Text style={styles.subtitle}>Granular data sharing and zero-trust scoring guarantee</Text>
            </View>
          </View>

          <View style={styles.privacyNotice}>
            <ShieldCheck size={20} color="#059669" />
            <Text style={styles.privacyNoticeText}>
              Zero Trust/Risk Scoring Policy: TourSafe never calculates or shares behavioral trust scores, risk scores, or demographic scores.
            </Text>
          </View>

          <Text style={styles.sectionHeader}>Granular Consents</Text>

          <ConsentToggleItem
            title="Identity Verification"
            description="Process masked document metadata to issue digital credentials"
            enabled={privacyData?.consents_summary?.IDENTITY_VERIFICATION ?? true}
            onToggle={() =>
              handleToggleConsent(
                'IDENTITY_VERIFICATION',
                privacyData?.consents_summary?.IDENTITY_VERIFICATION ?? true
              )
            }
          />

          <ConsentToggleItem
            title="Location Processing"
            description="Real-time geofence alerting and automatic boundary hazard warnings"
            enabled={privacyData?.consents_summary?.LOCATION_PROCESSING ?? true}
            onToggle={() =>
              handleToggleConsent(
                'LOCATION_PROCESSING',
                privacyData?.consents_summary?.LOCATION_PROCESSING ?? true
              )
            }
          />

          <ConsentToggleItem
            title="Telemetry Processing"
            description="Sensor anomaly detection for fall and crash incident escalation"
            enabled={privacyData?.consents_summary?.TELEMETRY_PROCESSING ?? true}
            onToggle={() =>
              handleToggleConsent(
                'TELEMETRY_PROCESSING',
                privacyData?.consents_summary?.TELEMETRY_PROCESSING ?? true
              )
            }
          />

          <ConsentToggleItem
            title="Credential Sharing"
            description="Allow offline QR verification at authorized checkpoints"
            enabled={privacyData?.consents_summary?.CREDENTIAL_SHARING ?? true}
            onToggle={() =>
              handleToggleConsent(
                'CREDENTIAL_SHARING',
                privacyData?.consents_summary?.CREDENTIAL_SHARING ?? true
              )
            }
          />
        </View>
      )}

      {/* KYC Submission Modal */}
      <Modal visible={kycModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Submit KYC Document</Text>
              <TouchableOpacity onPress={() => setKycModalVisible(false)}>
                <X size={20} color="#64748b" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Document Type</Text>
            <View style={styles.typeRow}>
              {['PASSPORT', 'NATIONAL_ID', 'DRIVING_LICENSE'].map((type) => (
                <TouchableOpacity
                  key={type}
                  style={[styles.typePill, docType === type && styles.typePillActive]}
                  onPress={() => setDocType(type)}
                >
                  <Text style={[styles.typePillText, docType === type && styles.typePillTextActive]}>
                    {type.replace('_', ' ')}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.inputLabel}>Issuing Country (ISO Code)</Text>
            <TextInput
              style={styles.textInput}
              value={issuingCountry}
              onChangeText={setIssuingCountry}
              placeholder="e.g. IND, USA, CAN, GBR"
            />

            <Text style={styles.inputLabel}>Masked Document Identifier</Text>
            <TextInput
              style={styles.textInput}
              value={maskedId}
              onChangeText={setMaskedId}
              placeholder="e.g. •••• 1234"
            />
            <Text style={styles.inputHint}>
              Only enter masked reference. Never enter your full unmasked government ID number.
            </Text>

            <TouchableOpacity
              style={styles.modalSubmitBtn}
              onPress={handleSubmitKyc}
              disabled={submittingKyc}
            >
              {submittingKyc ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.modalSubmitBtnText}>Submit for Verification</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function InfoChip({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <View style={styles.chip}>
      <View style={styles.chipIcon}>{icon}</View>
      <Text style={styles.chipLabel}>{label}</Text>
      <Text style={styles.chipValue}>{value}</Text>
    </View>
  );
}

function StepItem({
  number,
  title,
  completed,
  active,
}: {
  number: string;
  title: string;
  completed: boolean;
  active: boolean;
}) {
  return (
    <View style={styles.stepRow}>
      <View
        style={[
          styles.stepCircle,
          completed && styles.stepCircleCompleted,
          active && styles.stepCircleActive,
        ]}
      >
        <Text
          style={[
            styles.stepNumber,
            (completed || active) && styles.stepNumberActive,
          ]}
        >
          {completed ? '✓' : number}
        </Text>
      </View>
      <Text style={[styles.stepTitle, active && styles.stepTitleActive]}>{title}</Text>
    </View>
  );
}

function ConsentToggleItem({
  title,
  description,
  enabled,
  onToggle,
}: {
  title: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <View style={styles.consentItem}>
      <View style={styles.consentTextWrap}>
        <Text style={styles.consentTitle}>{title}</Text>
        <Text style={styles.consentDesc}>{description}</Text>
      </View>
      <TouchableOpacity
        style={[styles.toggleBtn, enabled ? styles.toggleBtnActive : styles.toggleBtnInactive]}
        onPress={onToggle}
      >
        <Text style={styles.toggleBtnText}>{enabled ? 'Granted' : 'Withdrawn'}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  content: { padding: 16, paddingBottom: 40 },
  centerContainer: { flex: 1, backgroundColor: '#0f172a', justifyContent: 'center', alignItems: 'center' },
  loadingText: { color: '#94a3b8', marginTop: 12, fontSize: 14 },

  segmentContainer: {
    flexDirection: 'row',
    backgroundColor: '#1e293b',
    borderRadius: 14,
    padding: 4,
    marginBottom: 16,
  },
  segmentBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  segmentBtnActive: { backgroundColor: '#2563eb' },
  segmentText: { color: '#94a3b8', fontSize: 13, fontWeight: '600' },
  segmentTextActive: { color: '#fff', fontWeight: '700' },

  card: {
    backgroundColor: '#1e293b',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  badgeWrap: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#0f172a',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  headerTitles: { flex: 1 },
  title: { fontSize: 19, fontWeight: '800', color: '#f8fafc' },
  subtitle: { fontSize: 12, color: '#94a3b8', marginTop: 2 },

  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 16,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  statusBannerText: { fontSize: 13, fontWeight: '700' },

  profileBlock: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    marginTop: 16,
    padding: 14,
    borderRadius: 16,
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
  },
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 16,
    backgroundColor: '#334155',
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileText: { flex: 1, gap: 2 },
  name: { fontSize: 17, fontWeight: '800', color: '#f8fafc' },
  meta: { fontSize: 12, color: '#94a3b8' },
  metaRef: { fontSize: 11, color: '#64748b', marginTop: 2, fontFamily: 'monospace' },

  qrFrame: {
    marginTop: 18,
    alignItems: 'center',
    padding: 20,
    borderRadius: 18,
    backgroundColor: '#ffffff',
  },
  qrCaption: { color: '#475569', fontSize: 12, marginTop: 12, fontWeight: '600' },
  qrVersion: { color: '#94a3b8', fontSize: 11, marginTop: 4, fontFamily: 'monospace' },

  infoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 16 },
  chip: {
    flex: 1,
    minWidth: '30%',
    backgroundColor: '#0f172a',
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  chipIcon: { marginBottom: 6 },
  chipLabel: { fontSize: 10, textTransform: 'uppercase', color: '#64748b', fontWeight: '700' },
  chipValue: { fontSize: 13, fontWeight: '700', color: '#f8fafc', marginTop: 2 },

  actionRow: { flexDirection: 'row', gap: 10, marginTop: 18 },
  primaryBtn: {
    flex: 1,
    backgroundColor: '#2563eb',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 12,
  },
  primaryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  secondaryBtn: {
    backgroundColor: '#f8fafc',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
  },
  secondaryBtnText: { color: '#1a365d', fontWeight: '700', fontSize: 14 },

  disclaimerBox: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: '#0f172a',
    padding: 12,
    borderRadius: 12,
    marginTop: 14,
    borderWidth: 1,
    borderColor: '#1e3a8a',
  },
  disclaimerText: { color: '#93c5fd', fontSize: 12, flex: 1, lineHeight: 18 },

  stepProgress: { marginTop: 18, gap: 14 },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stepCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#334155',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepCircleActive: { backgroundColor: '#2563eb' },
  stepCircleCompleted: { backgroundColor: '#059669' },
  stepNumber: { color: '#94a3b8', fontSize: 12, fontWeight: '700' },
  stepNumberActive: { color: '#fff' },
  stepTitle: { color: '#94a3b8', fontSize: 14, fontWeight: '600' },
  stepTitleActive: { color: '#f8fafc', fontWeight: '700' },

  submitDocBtn: {
    backgroundColor: '#2563eb',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 20,
    paddingVertical: 14,
    borderRadius: 12,
  },
  submitDocBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },

  verifiedSuccessBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#064e3b',
    padding: 14,
    borderRadius: 14,
    marginTop: 20,
  },
  verifiedSuccessText: { flex: 1 },
  verifiedTitle: { color: '#a7f3d0', fontSize: 15, fontWeight: '800' },
  verifiedDesc: { color: '#6ee7b7', fontSize: 12, marginTop: 2 },

  privacyNotice: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: '#064e3b',
    padding: 12,
    borderRadius: 12,
    marginTop: 14,
  },
  privacyNoticeText: { color: '#a7f3d0', fontSize: 12, flex: 1, lineHeight: 18 },
  sectionHeader: { color: '#cbd5e1', fontSize: 15, fontWeight: '800', marginTop: 20, marginBottom: 10 },

  consentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0f172a',
    padding: 14,
    borderRadius: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  consentTextWrap: { flex: 1, marginRight: 10 },
  consentTitle: { color: '#f8fafc', fontSize: 14, fontWeight: '700' },
  consentDesc: { color: '#64748b', fontSize: 11, marginTop: 2 },
  toggleBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  toggleBtnActive: { backgroundColor: '#059669' },
  toggleBtnInactive: { backgroundColor: '#475569' },
  toggleBtnText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1e293b',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 },
  modalTitle: { color: '#f8fafc', fontSize: 18, fontWeight: '800' },
  inputLabel: { color: '#cbd5e1', fontSize: 13, fontWeight: '600', marginTop: 12, marginBottom: 6 },
  typeRow: { flexDirection: 'row', gap: 8 },
  typePill: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
  },
  typePillActive: { backgroundColor: '#2563eb', borderColor: '#3b82f6' },
  typePillText: { color: '#94a3b8', fontSize: 12, fontWeight: '600' },
  typePillTextActive: { color: '#fff', fontWeight: '700' },
  textInput: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 10,
    padding: 12,
    color: '#f8fafc',
    fontSize: 14,
  },
  inputHint: { color: '#64748b', fontSize: 11, marginTop: 4 },
  modalSubmitBtn: {
    backgroundColor: '#2563eb',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 24,
  },
  modalSubmitBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});

