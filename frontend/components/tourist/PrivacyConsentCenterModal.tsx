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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
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
    category: 'Safety Communications',
    description: 'Delivers automated SMS/Voice alerts to designated family and emergency services during an SOS event.',
    retention: '730 days statutory incident log',
    access: 'Police, EMS, and verified emergency contacts',
    requiredForSafety: true,
  },
  {
    id: 'OPTIONAL_ANALYTICS',
    title: 'Anonymous Tourism Flow Analytics',
    category: 'Analytics & Insights',
    description: 'Aggregates de-identified 2-decimal spatial coordinates to assist regional authorities in improving safety infrastructure.',
    retention: '3 years (strictly aggregated / no personal identifiers)',
    access: 'Regional Tourism Board Analytics Officers',
    requiredForSafety: false,
  },
  {
    id: 'OPTIONAL_PERSONALIZATION',
    title: 'AI Trip & Safety Recommendations',
    category: 'Personalization',
    description: 'Customizes safety warnings and route recommendations based on active itinerary checkpoints.',
    retention: '60 days',
    access: 'Tourist (Self)',
    requiredForSafety: false,
  },
];

export const PrivacyConsentCenterModal: React.FC<Props> = ({ visible, onClose }) => {
  const [activeTab, setActiveTab] = useState<'CONSENTS' | 'REQUESTS' | 'EXPORTS'>('CONSENTS');
  const [selectedReqType, setSelectedReqType] = useState<PrivacyRequestType>('ACCESS');
  const [reqNotes, setReqNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const { consents, requests, isLoading, fetchConsents, grantConsent, withdrawConsent, fetchRequests, submitRequest, verifyRequest } = usePrivacyStore();

  useEffect(() => {
    if (visible) {
      fetchConsents();
      fetchRequests();
    }
  }, [visible]);

  const isConsentGranted = (purpose: ConsentPurpose) => {
    const record = consents.find((c) => c.purpose === purpose && c.status === 'GRANTED');
    return !!record;
  };

  const handleToggleConsent = async (purpose: ConsentPurpose, currentVal: boolean) => {
    if (currentVal) {
      await withdrawConsent(purpose, 'Revoked by tourist via privacy center');
    } else {
      await grantConsent(purpose);
    }
  };

  const handleCreateRequest = async () => {
    setSubmitting(true);
    const req = await submitRequest(selectedReqType, ['IDENTITY', 'LOCATION', 'CONTACT'], reqNotes);
    setSubmitting(false);
    if (req) {
      Alert.alert('Request Submitted', `Your privacy request #${req.id.slice(0, 8)} has been logged. Please complete identity verification.`);
      setReqNotes('');
    } else {
      Alert.alert('Error', 'Failed to submit request. Please try again.');
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View className="flex-1 bg-black/80 justify-end">
        <View className="bg-slate-900 rounded-t-3xl border-t border-slate-800 max-h-[90%] p-5">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800">
            <View className="flex-row items-center space-x-3">
              <View className="w-10 h-10 rounded-xl bg-teal-500/10 items-center justify-center border border-teal-500/20">
                <Ionicons name="shield-checkmark" size={22} color="#14b8a6" />
              </View>
              <View>
                <Text className="text-lg font-bold text-slate-100">Privacy & Consent Center</Text>
                <Text className="text-xs text-slate-400">Manage data permissions & subject rights</Text>
              </View>
            </View>
            <TouchableOpacity onPress={onClose} className="p-2 rounded-full bg-slate-800">
              <Ionicons name="close" size={20} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {/* Tabs */}
          <View className="flex-row bg-slate-950 p-1 rounded-xl mt-4 border border-slate-800">
            {(['CONSENTS', 'REQUESTS', 'EXPORTS'] as const).map((tab) => (
              <TouchableOpacity
                key={tab}
                onPress={() => setActiveTab(tab)}
                className={`flex-1 py-2 rounded-lg items-center ${activeTab === tab ? 'bg-slate-800 border border-slate-700' : ''}`}
              >
                <Text className={`text-xs font-semibold ${activeTab === tab ? 'text-teal-400' : 'text-slate-400'}`}>
                  {tab === 'CONSENTS' ? 'Data Consents' : tab === 'REQUESTS' ? 'Privacy Requests' : 'Data Portability'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Tab Content */}
          <ScrollView className="mt-4" showsVerticalScrollIndicator={false}>
            {activeTab === 'CONSENTS' && (
              <View className="space-y-4 pb-8">
                <View className="bg-blue-950/30 border border-blue-800/40 p-3 rounded-xl">
                  <Text className="text-xs font-medium text-blue-300">
                    <Ionicons name="information-circle-outline" size={13} color="#93c5fd" /> Privacy by Design: TourSafe collects data solely for verified safety & rescue operations. You have the right to withdraw optional permissions anytime.
                  </Text>
                </View>

                {PURPOSES_CONFIG.map((p) => {
                  const granted = isConsentGranted(p.id);
                  return (
                    <View key={p.id} className="bg-slate-800/60 p-4 rounded-2xl border border-slate-800">
                      <View className="flex-row items-center justify-between">
                        <View className="flex-1 pr-3">
                          <View className="flex-row items-center space-x-2">
                            <Text className="text-sm font-bold text-slate-200">{p.title}</Text>
                            {p.requiredForSafety && (
                              <View className="bg-amber-500/20 px-2 py-0.5 rounded border border-amber-500/30">
                                <Text className="text-[10px] font-bold text-amber-400">Safety Core</Text>
                              </View>
                            )}
                          </View>
                          <Text className="text-xs text-slate-400 mt-1">{p.description}</Text>
                        </View>
                        <Switch
                          value={granted}
                          onValueChange={() => handleToggleConsent(p.id, granted)}
                          trackColor={{ false: '#334155', true: '#0d9488' }}
                          thumbColor={granted ? '#2dd4bf' : '#94a3b8'}
                        />
                      </View>

                      <View className="mt-3 pt-3 border-t border-slate-700/50 space-y-1">
                        <View className="flex-row justify-between">
                          <Text className="text-[11px] text-slate-500">Retention:</Text>
                          <Text className="text-[11px] text-slate-400 font-medium">{p.retention}</Text>
                        </View>
                        <View className="flex-row justify-between">
                          <Text className="text-[11px] text-slate-500">Authorized Access:</Text>
                          <Text className="text-[11px] text-slate-400 font-medium">{p.access}</Text>
                        </View>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}

            {activeTab === 'REQUESTS' && (
              <View className="space-y-4 pb-8">
                <View className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                  <Text className="text-sm font-bold text-slate-200 mb-2">Submit Data Subject Request (DSR)</Text>
                  <Text className="text-xs text-slate-400 mb-3">
                    Exercise your statutory rights (GDPR / DPDP) to access, correct, or erase personal records.
                  </Text>

                  <Text className="text-xs font-semibold text-slate-300 mb-1">Request Type:</Text>
                  <View className="flex-row flex-wrap gap-2 mb-3">
                    {(['ACCESS', 'EXPORT', 'CORRECTION', 'DELETION'] as PrivacyRequestType[]).map((type) => (
                      <TouchableOpacity
                        key={type}
                        onPress={() => setSelectedReqType(type)}
                        className={`px-3 py-1.5 rounded-lg border ${
                          selectedReqType === type ? 'bg-teal-500/20 border-teal-500 text-teal-300' : 'bg-slate-900 border-slate-700'
                        }`}
                      >
                        <Text className={`text-xs font-medium ${selectedReqType === type ? 'text-teal-400' : 'text-slate-400'}`}>
                          {type}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <Text className="text-xs font-semibold text-slate-300 mb-1">Details / Scope Notes (Optional):</Text>
                  <TextInput
                    value={reqNotes}
                    onChangeText={setReqNotes}
                    placeholder="Specify particular details or reason..."
                    placeholderTextColor="#64748b"
                    className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-slate-200 mb-3"
                    multiline
                    numberOfLines={2}
                  />

                  <TouchableOpacity
                    onPress={handleCreateRequest}
                    disabled={submitting}
                    className="bg-teal-600 p-3 rounded-xl items-center"
                  >
                    {submitting ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text className="text-xs font-bold text-white">Submit Request</Text>
                    )}
                  </TouchableOpacity>
                </View>

                {/* Existing Requests */}
                <Text className="text-sm font-bold text-slate-200 mt-2">Request History</Text>
                {requests.length === 0 ? (
                  <Text className="text-xs text-slate-500 italic py-2">No privacy requests logged yet.</Text>
                ) : (
                  requests.map((r) => (
                    <View key={r.id} className="bg-slate-800/40 p-3 rounded-xl border border-slate-800 space-y-2">
                      <View className="flex-row items-center justify-between">
                        <Text className="text-xs font-bold text-slate-300">
                          #{r.id.slice(0, 8)} • {r.request_type}
                        </Text>
                        <View
                          className={`px-2 py-0.5 rounded ${
                            r.status === 'COMPLETED'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : r.status === 'REJECTED'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-amber-500/20 text-amber-400'
                          }`}
                        >
                          <Text
                            className={`text-[10px] font-bold ${
                              r.status === 'COMPLETED'
                                ? 'text-emerald-400'
                                : r.status === 'REJECTED'
                                ? 'text-red-400'
                                : 'text-amber-400'
                            }`}
                          >
                            {r.status}
                          </Text>
                        </View>
                      </View>
                      <Text className="text-[11px] text-slate-400">
                        Submitted: {new Date(r.created_at).toLocaleDateString()} • Deadline: {new Date(r.deadline_at).toLocaleDateString()}
                      </Text>

                      {!r.identity_verified && r.status === 'SUBMITTED' && (
                        <TouchableOpacity
                          onPress={async () => {
                            await verifyRequest(r.id);
                            Alert.alert('Verified', 'Session identity verification confirmed.');
                          }}
                          className="bg-slate-700 py-1.5 rounded-lg items-center mt-1"
                        >
                          <Text className="text-xs font-semibold text-teal-300">Verify Identity with Session</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  ))
                )}
              </View>
            )}

            {activeTab === 'EXPORTS' && (
              <View className="space-y-4 pb-8">
                <View className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                  <Text className="text-sm font-bold text-slate-200 mb-1">Portable Data Export Bundle</Text>
                  <Text className="text-xs text-slate-400 mb-3">
                    Download a complete, machine-readable JSON archive of your personal profile, itineraries, emergency contacts, and consent audit records.
                  </Text>

                  <TouchableOpacity
                    onPress={() => {
                      setSelectedReqType('EXPORT');
                      setActiveTab('REQUESTS');
                    }}
                    className="bg-slate-700 py-2.5 rounded-xl items-center border border-slate-600"
                  >
                    <Text className="text-xs font-bold text-teal-300">Generate New Export Token</Text>
                  </TouchableOpacity>
                </View>

                {requests.filter((r) => r.export_token).map((r) => (
                  <View key={r.id} className="bg-slate-800/50 p-4 rounded-xl border border-teal-500/30 space-y-2">
                    <View className="flex-row items-center justify-between">
                      <Text className="text-xs font-bold text-teal-400">Export Ready ({r.id.slice(0, 8)})</Text>
                      <Text className="text-[10px] text-slate-400">Expires in 24h</Text>
                    </View>
                    <Text className="text-[11px] text-slate-300">
                      Token: {r.export_token}
                    </Text>
                    <Text className="text-[11px] text-slate-400">
                      Endpoint: /api/v1/privacy/export/{r.export_token}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};
