import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  CheckCircle2,
  Clock,
  Database,
  FileCheck,
  FileText,
  HelpCircle,
  MapPin,
  MessageSquare,
  Navigation,
  Phone,
  RefreshCw,
  Share2,
  Shield,
  ShieldAlert,
  Stethoscope,
  User,
  Users,
  X,
  XCircle,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { incidentApi, incidentAssignmentApi, responderApi } from '@/lib/api';
import { useResponderStore } from '@/store/responderStore';
import type {
  AssignmentRecord,
  HandoverReason,
  IncidentRecord,
  RejectionReason,
  ResponderSelfProfile,
  SceneAssessmentCategory,
  TimelineEvent,
} from '@/types';

const ASSESSMENT_CATEGORIES: Array<{ label: string; value: SceneAssessmentCategory; icon: string }> = [
  { label: 'Tourist Safe & Stable (No Hazard)', value: 'TOURIST_SAFE', icon: 'CheckCircle' },
  { label: 'First Aid Administered (Minor)', value: 'FIRST_AID_RENDERED', icon: 'Stethoscope' },
  { label: 'Advanced Medical / Ambulance Needed', value: 'MEDICAL_ASSISTANCE', icon: 'AlertCircle' },
  { label: 'Emergency Evacuation Required', value: 'EVACUATION_REQUIRED', icon: 'ShieldAlert' },
  { label: 'False Alarm / Inadvertent SOS', value: 'FALSE_ALARM', icon: 'HelpCircle' },
  { label: 'Physical Hazard Cleared', value: 'HAZARD_CLEARED', icon: 'FileCheck' },
  { label: 'Law Enforcement Required', value: 'POLICE_ASSISTANCE', icon: 'Shield' },
  { label: 'Search & Sweep Continuing', value: 'SEARCH_CONTINUING', icon: 'Navigation' },
];

const HANDOVER_REASONS: Array<{ label: string; value: HandoverReason }> = [
  { label: 'Fatigue / Maximum Shift Limit Reached', value: 'FATIGUE_SHIFT_CHANGE' },
  { label: 'Specialized Tactical Capability Required', value: 'WRONG_CAPABILITY' },
  { label: 'Terrain Obstacle / Access Route Impassable', value: 'TERRAIN_OR_ACCESS' },
  { label: 'Casualty Criticality Beyond Unit Level', value: 'CASUALTY_CRITICALITY' },
  { label: 'Equipment Malfunction / Depleted Resources', value: 'EQUIPMENT_FAILURE' },
  { label: 'Displaced Location / Outside Sector', value: 'LOCATION' },
  { label: 'Authority Command Reassignment Directive', value: 'COMMAND_DIRECTIVE' },
];

const REJECTION_REASONS: Array<{ label: string; value: RejectionReason }> = [
  { label: 'Unreachable / Communication Outage', value: 'UNREACHABLE_OR_OFFLINE' },
  { label: 'Insufficient Tactical Equipment / Capability', value: 'INSUFFICIENT_CAPABILITY' },
  { label: 'Equipment Malfunction / Vehicle Breakdown', value: 'EQUIPMENT_MALFUNCTION' },
  { label: 'Geographic Terrain Barrier / Route Blocked', value: 'GEOGRAPHIC_BARRIER' },
  { label: 'Imminent Physical Safety Hazard', value: 'SAFETY_HAZARD' },
  { label: 'Handling Concurrent Critical Response', value: 'CONCURRENT_ACTIVE_RESPONSE' },
  { label: 'Other Operational Grounding Reason', value: 'OTHER' },
];

export default function ResponderIncidentScreen() {
  const params = useLocalSearchParams<{ incident_id?: string }>();
  const [profile, setProfile] = useState<ResponderSelfProfile | null>(null);
  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [assignment, setAssignment] = useState<AssignmentRecord | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Zustand Store
  const { addOfflineNote, currentGps } = useResponderStore();

  // Rejection Modal
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [selectedRejectReason, setSelectedRejectReason] = useState<RejectionReason>('UNREACHABLE_OR_OFFLINE');
  const [rejectDetails, setRejectDetails] = useState('');

  // Scene Assessment Modal
  const [assessmentModalVisible, setAssessmentModalVisible] = useState(false);
  const [selectedAssessmentCategory, setSelectedAssessmentCategory] = useState<SceneAssessmentCategory>('TOURIST_SAFE');
  const [assessmentNotes, setAssessmentNotes] = useState('');
  const [touristObservedStatus, setTouristObservedStatus] = useState('');
  const [followUpRequired, setFollowUpRequired] = useState(false);

  // Handover Modal
  const [handoverModalVisible, setHandoverModalVisible] = useState(false);
  const [selectedHandoverReason, setSelectedHandoverReason] = useState<HandoverReason>('FATIGUE_SHIFT_CHANGE');
  const [handoverDetails, setHandoverDetails] = useState('');
  const [handoverCapability, setHandoverCapability] = useState('');

  // Offline Field Note Input
  const [fieldNoteText, setFieldNoteText] = useState('');
  const [isSavingNote, setIsSavingNote] = useState(false);

  // Completion Modal
  const [completeModalVisible, setCompleteModalVisible] = useState(false);
  const [completionReason, setCompletionReason] = useState('');
  const [completionNotes, setCompletionNotes] = useState('');

  // Arrival Override Dialog
  const [arrivalOverrideMode, setArrivalOverrideMode] = useState(false);

  useEffect(() => {
    loadIncidentData();
    const interval = setInterval(loadIncidentData, 8000);
    return () => clearInterval(interval);
  }, [params.incident_id]);

  async function loadIncidentData() {
    try {
      const profRes = await responderApi.getMe();
      if (profRes?.data) {
        setProfile(profRes.data);
        if (profRes.data.active_assignment) {
          setAssignment(profRes.data.active_assignment);
        }
      }

      const targetIncId = params.incident_id || profRes?.data?.active_incident?.incident_id;
      if (targetIncId) {
        const [incRes, timeRes] = await Promise.allSettled([
          incidentApi.getById(targetIncId),
          incidentApi.getTimeline(targetIncId),
        ]);

        if (incRes.status === 'fulfilled' && incRes.value?.data) {
          setIncident(incRes.value.data);
        }
        if (timeRes.status === 'fulfilled' && Array.isArray(timeRes.value?.data)) {
          setTimeline(timeRes.value.data);
        }
      }
    } catch (e: any) {
      console.warn('Failed to load incident operational details:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function handleAccept() {
    if (!incident || !assignment) return;
    try {
      setActionLoading(true);
      await incidentAssignmentApi.acceptAssignment(
        incident.incident_id,
        assignment.assignment_id,
        'Responder accepted assignment via mobile tactical terminal'
      );
      Toast.show({
        type: 'success',
        text1: 'Assignment Accepted',
        text2: 'You are now deployed. Prepare for response start.',
      });
      await loadIncidentData();
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Accept Action Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not accept assignment',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!incident || !assignment) return;
    try {
      setActionLoading(true);
      await incidentAssignmentApi.rejectAssignment(
        incident.incident_id,
        assignment.assignment_id,
        {
          reason: selectedRejectReason,
          details: rejectDetails || undefined,
        }
      );
      setRejectModalVisible(false);
      Toast.show({
        type: 'info',
        text1: 'Assignment Rejected',
        text2: 'Dispatch returned to Authority Command queue.',
      });
      router.replace('/responder');
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Reject Action Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not reject assignment',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStartResponse() {
    if (!incident || !assignment) return;
    try {
      setActionLoading(true);
      await incidentAssignmentApi.startResponse(
        incident.incident_id,
        assignment.assignment_id,
        'Unit en route to incident coordinates'
      );
      Toast.show({
        type: 'success',
        text1: 'Response Started',
        text2: 'Status updated to RESPONDING. Realtime tracking active.',
      });
      await loadIncidentData();
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Response Start Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not start response',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleMarkArrived(forceOverride = false) {
    if (!incident || !assignment) return;
    try {
      setActionLoading(true);
      const loc = profile?.live_location || profile?.responder?.current_location;
      await incidentAssignmentApi.markArrived(
        incident.incident_id,
        assignment.assignment_id,
        {
          latitude: loc?.latitude,
          longitude: loc?.longitude,
          accuracy: loc?.accuracy || 10,
          force_override: forceOverride,
          notes: forceOverride ? 'Manual proximity override accepted' : 'GPS verified arrival',
        }
      );
      setArrivalOverrideMode(false);
      Toast.show({
        type: 'success',
        text1: 'Marked Arrived On Scene',
        text2: 'Proximity verified. Status transitioned to ON_SCENE.',
      });
      await loadIncidentData();
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || '';
      if (errMsg.includes('Arrival proximity check failed')) {
        setArrivalOverrideMode(true);
      }
      Toast.show({
        type: 'error',
        text1: 'Arrival Verification Error',
        text2: errMsg || 'Proximity check failed',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCompleteResponse() {
    if (!incident || !assignment || !completionReason.trim()) {
      Toast.show({
        type: 'error',
        text1: 'Missing Reason',
        text2: 'Please describe the resolution reason before concluding response.',
      });
      return;
    }
    try {
      setActionLoading(true);
      await incidentAssignmentApi.completeResponse(
        incident.incident_id,
        assignment.assignment_id,
        {
          completion_reason: completionReason.trim(),
          resolution_notes: completionNotes.trim() || undefined,
        }
      );
      setCompleteModalVisible(false);
      Toast.show({
        type: 'success',
        text1: 'Response Concluded',
        text2: 'Mission logged. Status restored to AVAILABLE.',
      });
      router.replace('/responder');
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Completion Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not conclude response',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSubmitAssessment() {
    if (!incident || !assignment) return;
    try {
      setActionLoading(true);
      await incidentAssignmentApi.submitSceneAssessment(
        incident.incident_id,
        assignment.assignment_id,
        {
          category: selectedAssessmentCategory,
          notes: assessmentNotes.trim() || undefined,
          tourist_status_observed: touristObservedStatus.trim() || undefined,
          follow_up_required: followUpRequired,
        }
      );
      setAssessmentModalVisible(false);
      Toast.show({
        type: 'success',
        text1: 'Scene Assessment Recorded',
        text2: `Status categorized as ${selectedAssessmentCategory}`,
      });
      await loadIncidentData();
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Assessment Submission Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not submit assessment',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRequestHandover() {
    if (!incident || !assignment) return;
    try {
      setActionLoading(true);
      await responderApi.requestHandover(assignment.assignment_id, {
        reason: selectedHandoverReason,
        details: handoverDetails.trim() || undefined,
        replacement_capability: handoverCapability.trim() || undefined,
      });
      setHandoverModalVisible(false);
      Toast.show({
        type: 'info',
        text1: 'Handover Requested',
        text2: 'Assignment released. Incident returned to dispatch pool.',
      });
      router.replace('/responder');
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Handover Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not request handover',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSaveFieldNote() {
    if (!incident || !fieldNoteText.trim()) return;
    try {
      setIsSavingNote(true);
      await addOfflineNote(
        incident.incident_id,
        fieldNoteText.trim(),
        currentGps?.latitude,
        currentGps?.longitude
      );
      setFieldNoteText('');
      Toast.show({
        type: 'success',
        text1: 'Field Note Saved',
        text2: 'Stored locally and synced with timeline.',
      });
      await loadIncidentData();
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Could not save note',
        text2: err?.message || 'Note storage error',
      });
    } finally {
      setIsSavingNote(false);
    }
  }


  if (loading && !incident) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#EF4444" />
        <Text style={styles.loadingText}>Loading Incident Command Dossier...</Text>
      </View>
    );
  }

  if (!incident) {
    return (
      <View style={styles.centerContainer}>
        <AlertTriangle size={32} color="#EF4444" />
        <Text style={styles.notFoundTitle}>Incident Not Found</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={styles.backBtnText}>Return to Dashboard</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const isPending = assignment?.status === 'PENDING';
  const isAccepted = assignment?.status === 'ACCEPTED';
  const isActiveEnRoute = assignment?.status === 'ACTIVE' && profile?.responder?.status !== 'ON_SCENE';
  const isOnScene = profile?.responder?.status === 'ON_SCENE' || assignment?.status === 'ON_SCENE';

  return (
    <View style={styles.container}>
      {/* Tactical Top Bar */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBackBtn} onPress={() => router.back()}>
          <ArrowLeft size={20} color="#F8FAFC" />
        </TouchableOpacity>
        <View style={styles.headerTitleWrap}>
          <Text style={styles.headerTitle}>INCIDENT COMMAND</Text>
          <Text style={styles.headerSubtitle}>{incident.incident_id}</Text>
        </View>
        <TouchableOpacity
          style={styles.chatHeaderBtn}
          onPress={() =>
            router.push({
              pathname: '/responder/messages',
              params: { incident_id: incident.incident_id },
            })
          }
        >
          <MessageSquare size={18} color="#60A5FA" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollArea}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={loadIncidentData} tintColor="#EF4444" />
        }
      >
        {/* Incident Severity Banner */}
        <View style={styles.severityCard}>
          <View style={styles.severityRow}>
            <View style={styles.severityBadge}>
              <ShieldAlert size={18} color="#FFFFFF" />
              <Text style={styles.severityBadgeText}>{incident.severity}</Text>
            </View>
            <View style={styles.statusPill}>
              <Text style={styles.statusPillText}>{incident.status}</Text>
            </View>
          </View>

          <Text style={styles.sourceText}>Source: {incident.source}</Text>
          <Text style={styles.startedText}>
            Reported: {new Date(incident.started_at || incident.created_at).toLocaleTimeString()}
          </Text>

          {incident.reasons && incident.reasons.length > 0 && (
            <View style={styles.reasonsBox}>
              <Text style={styles.reasonsTitle}>Triggered Conditions:</Text>
              <Text style={styles.reasonsList}>{incident.reasons.join('\n• ')}</Text>
            </View>
          )}
        </View>

        {/* Location & Navigation Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <MapPin size={16} color="#60A5FA" />
              <Text style={styles.cardSectionTitle}>TARGET COORDINATES</Text>
            </View>
            <TouchableOpacity
              style={styles.mapLinkBtn}
              onPress={() => router.push('/responder/map')}
            >
              <Text style={styles.mapLinkText}>View Tactical Map</Text>
              <Navigation size={12} color="#60A5FA" />
            </TouchableOpacity>
          </View>

          <View style={styles.locDetailsBox}>
            <Text style={styles.locZoneName}>
              {incident.location_data?.zone_name || 'Geofenced Safety Sector'}
            </Text>
            <Text style={styles.locCoords}>
              Lat: {incident.location_data?.latitude?.toFixed(5) || 'N/A'} • Lng:{' '}
              {incident.location_data?.longitude?.toFixed(5) || 'N/A'}
            </Text>
            <Text style={styles.locFixStatus}>
              Fix Quality: {incident.location_data?.location_status || 'CURRENT'}
            </Text>
          </View>
        </View>

        {/* Tactical Actions Matrix */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <Shield size={16} color="#34D399" />
              <Text style={styles.cardSectionTitle}>OPERATIONAL RESPONSE ACTIONS</Text>
            </View>
          </View>

          {/* Pending: Accept / Reject */}
          {isPending && (
            <View style={styles.actionGrid}>
              <TouchableOpacity
                style={[styles.primaryActionBtn, styles.acceptBtn]}
                disabled={actionLoading}
                onPress={handleAccept}
              >
                <CheckCircle size={18} color="#FFFFFF" />
                <Text style={styles.primaryActionBtnText}>ACCEPT DISPATCH</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.secondaryActionBtn, styles.rejectBtn]}
                disabled={actionLoading}
                onPress={() => setRejectModalVisible(true)}
              >
                <XCircle size={18} color="#EF4444" />
                <Text style={styles.rejectBtnText}>REJECT WITH REASON</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Accepted: Start Transit */}
          {isAccepted && (
            <TouchableOpacity
              style={[styles.primaryActionBtn, styles.startBtn]}
              disabled={actionLoading}
              onPress={handleStartResponse}
            >
              <Navigation size={18} color="#FFFFFF" />
              <Text style={styles.primaryActionBtnText}>COMMENCE TRANSIT (START RESPONSE)</Text>
            </TouchableOpacity>
          )}

          {/* Active (En Route): Mark Arrived */}
          {isActiveEnRoute && (
            <View style={styles.arrivalActionBox}>
              <TouchableOpacity
                style={[styles.primaryActionBtn, styles.arriveBtn]}
                disabled={actionLoading}
                onPress={() => handleMarkArrived(false)}
              >
                <MapPin size={18} color="#FFFFFF" />
                <Text style={styles.primaryActionBtnText}>VERIFY ARRIVAL ON SCENE</Text>
              </TouchableOpacity>

              {arrivalOverrideMode && (
                <View style={styles.overrideWarningBox}>
                  <AlertTriangle size={16} color="#F59E0B" />
                  <Text style={styles.overrideWarningText}>
                    GPS distance check failed. If you are physically at scene, activate manual override:
                  </Text>
                  <TouchableOpacity
                    style={styles.overrideBtn}
                    disabled={actionLoading}
                    onPress={() => handleMarkArrived(true)}
                  >
                    <Text style={styles.overrideBtnText}>CONFIRM ON-SCENE OVERRIDE</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}

          {/* On Scene: Structured Assessment, Handover & Complete Response */}
          {isOnScene && (
            <View style={styles.onSceneActionStack}>
              <TouchableOpacity
                style={[styles.primaryActionBtn, styles.assessBtn]}
                disabled={actionLoading}
                onPress={() => setAssessmentModalVisible(true)}
              >
                <Stethoscope size={18} color="#FFFFFF" />
                <Text style={styles.primaryActionBtnText}>SUBMIT SCENE ASSESSMENT</Text>
              </TouchableOpacity>

              <View style={styles.onSceneSecondaryRow}>
                <TouchableOpacity
                  style={[styles.secondaryActionBtn, styles.handoverBtn]}
                  disabled={actionLoading}
                  onPress={() => setHandoverModalVisible(true)}
                >
                  <Share2 size={16} color="#FBBF24" />
                  <Text style={styles.handoverBtnText}>REQUEST HANDOVER</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.primaryActionBtn, styles.completeBtn, { flex: 1 }]}
                  disabled={actionLoading}
                  onPress={() => setCompleteModalVisible(true)}
                >
                  <CheckCircle2 size={18} color="#FFFFFF" />
                  <Text style={styles.primaryActionBtnText}>RESOLVE / CLOSE</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>

        {/* Tactical Offline Field Notes Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <Database size={16} color="#38BDF8" />
              <Text style={styles.cardSectionTitle}>TACTICAL FIELD NOTES (OFFLINE READY)</Text>
            </View>
          </View>

          <TextInput
            style={styles.fieldNoteInput}
            placeholder="Record observations, tourist vitals, terrain notes..."
            placeholderTextColor="#64748B"
            value={fieldNoteText}
            onChangeText={setFieldNoteText}
            multiline
          />

          <TouchableOpacity
            style={[styles.saveNoteBtn, (!fieldNoteText.trim() || isSavingNote) && styles.saveNoteBtnDisabled]}
            disabled={!fieldNoteText.trim() || isSavingNote}
            onPress={handleSaveFieldNote}
          >
            {isSavingNote ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <>
                <FileText size={16} color="#FFFFFF" />
                <Text style={styles.saveNoteBtnText}>RECORD FIELD NOTE</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Timeline Events Feed */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <Clock size={16} color="#94A3B8" />
              <Text style={styles.cardSectionTitle}>TACTICAL AUDIT TIMELINE</Text>
            </View>
          </View>

          <View style={styles.timelineList}>
            {timeline.length === 0 ? (
              <Text style={styles.emptyTimelineText}>No audit entries recorded.</Text>
            ) : (
              timeline.map((evt, idx) => (
                <View key={idx} style={styles.timelineItem}>
                  <View style={styles.timelineDot} />
                  <View style={styles.timelineContent}>
                    <View style={styles.timelineTitleRow}>
                      <Text style={styles.timelineAction}>{evt.action}</Text>
                      <Text style={styles.timelineTime}>
                        {new Date(evt.timestamp).toLocaleTimeString()}
                      </Text>
                    </View>
                    <Text style={styles.timelineActor}>
                      Actor: {evt.actor_type} ({evt.actor_id})
                    </Text>
                    {evt.reason && <Text style={styles.timelineReason}>"{evt.reason}"</Text>}
                  </View>
                </View>
              ))
            )}
          </View>
        </View>
      </ScrollView>

      {/* REJECTION REASON MODAL */}
      <Modal visible={rejectModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Reject Incident Dispatch</Text>
              <TouchableOpacity onPress={() => setRejectModalVisible(false)}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Mandatory tactical ground reason required for incident reassignment:
            </Text>

            <ScrollView style={styles.reasonScroll}>
              {REJECTION_REASONS.map((r, idx) => (
                <TouchableOpacity
                  key={idx}
                  style={[
                    styles.reasonOption,
                    selectedRejectReason === r.value && styles.reasonOptionSelected,
                  ]}
                  onPress={() => setSelectedRejectReason(r.value)}
                >
                  <View
                    style={[
                      styles.reasonRadio,
                      selectedRejectReason === r.value && styles.reasonRadioSelected,
                    ]}
                  />
                  <Text style={styles.reasonOptionText}>{r.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TextInput
              style={styles.modalTextInput}
              placeholder="Additional operational details..."
              placeholderTextColor="#64748B"
              value={rejectDetails}
              onChangeText={setRejectDetails}
              multiline
            />

            <View style={styles.modalButtonsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setRejectModalVisible(false)}
              >
                <Text style={styles.modalCancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSubmitRejectBtn}
                disabled={actionLoading}
                onPress={handleReject}
              >
                <Text style={styles.modalSubmitBtnText}>Submit Rejection</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* RESOLUTION COMPLETION MODAL */}
      <Modal visible={completeModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Conclude Response Mission</Text>
              <TouchableOpacity onPress={() => setCompleteModalVisible(false)}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Provide primary resolution summary and return to AVAILABLE duty status:
            </Text>

            <TextInput
              style={styles.modalInputSingle}
              placeholder="Primary Completion Reason (e.g. Tourist safely escorted to station)"
              placeholderTextColor="#64748B"
              value={completionReason}
              onChangeText={setCompletionReason}
            />

            <TextInput
              style={styles.modalTextInput}
              placeholder="Detailed tactical notes / medical triage handover..."
              placeholderTextColor="#64748B"
              value={completionNotes}
              onChangeText={setCompletionNotes}
              multiline
            />

            <View style={styles.modalButtonsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setCompleteModalVisible(false)}
              >
                <Text style={styles.modalCancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSubmitCompleteBtn}
                disabled={actionLoading || !completionReason.trim()}
                onPress={handleCompleteResponse}
              >
                <Text style={styles.modalSubmitBtnText}>Conclude Response</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* SCENE ASSESSMENT MODAL */}
      <Modal visible={assessmentModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Structured Scene Assessment</Text>
              <TouchableOpacity onPress={() => setAssessmentModalVisible(false)}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Categorize on-scene casualty / site condition for central timeline:
            </Text>

            <ScrollView style={styles.reasonScroll}>
              {ASSESSMENT_CATEGORIES.map((cat, idx) => (
                <TouchableOpacity
                  key={idx}
                  style={[
                    styles.reasonOption,
                    selectedAssessmentCategory === cat.value && styles.reasonOptionSelected,
                  ]}
                  onPress={() => setSelectedAssessmentCategory(cat.value)}
                >
                  <View
                    style={[
                      styles.reasonRadio,
                      selectedAssessmentCategory === cat.value && styles.reasonRadioSelected,
                    ]}
                  />
                  <Text style={styles.reasonOptionText}>{cat.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TextInput
              style={styles.modalInputSingle}
              placeholder="Observed Tourist Status (e.g. Conscious, oriented)"
              placeholderTextColor="#64748B"
              value={touristObservedStatus}
              onChangeText={setTouristObservedStatus}
            />

            <TextInput
              style={styles.modalTextInput}
              placeholder="Assessment notes, triage observations, treatments rendered..."
              placeholderTextColor="#64748B"
              value={assessmentNotes}
              onChangeText={setAssessmentNotes}
              multiline
            />

            <TouchableOpacity
              style={[styles.checkboxRow, followUpRequired && styles.checkboxRowActive]}
              onPress={() => setFollowUpRequired(!followUpRequired)}
            >
              <View style={[styles.checkboxBox, followUpRequired && styles.checkboxBoxActive]}>
                {followUpRequired && <CheckCircle size={14} color="#FFFFFF" />}
              </View>
              <Text style={styles.checkboxLabel}>Secondary follow-up / investigation required</Text>
            </TouchableOpacity>

            <View style={styles.modalButtonsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setAssessmentModalVisible(false)}
              >
                <Text style={styles.modalCancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSubmitAssessBtn}
                disabled={actionLoading}
                onPress={handleSubmitAssessment}
              >
                <Text style={styles.modalSubmitBtnText}>Submit Assessment</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* OPERATIONAL HANDOVER MODAL */}
      <Modal visible={handoverModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Request Operational Handover</Text>
              <TouchableOpacity onPress={() => setHandoverModalVisible(false)}>
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Select ground constraint necessitating assignment reassignment:
            </Text>

            <ScrollView style={styles.reasonScroll}>
              {HANDOVER_REASONS.map((h, idx) => (
                <TouchableOpacity
                  key={idx}
                  style={[
                    styles.reasonOption,
                    selectedHandoverReason === h.value && styles.reasonOptionSelected,
                  ]}
                  onPress={() => setSelectedHandoverReason(h.value)}
                >
                  <View
                    style={[
                      styles.reasonRadio,
                      selectedHandoverReason === h.value && styles.reasonRadioSelected,
                    ]}
                  />
                  <Text style={styles.reasonOptionText}>{h.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TextInput
              style={styles.modalInputSingle}
              placeholder="Replacement Capability Required (e.g. WATER_RESCUE, MEDICAL)"
              placeholderTextColor="#64748B"
              value={handoverCapability}
              onChangeText={setHandoverCapability}
            />

            <TextInput
              style={styles.modalTextInput}
              placeholder="Handover situation details (barrier, casualty condition)..."
              placeholderTextColor="#64748B"
              value={handoverDetails}
              onChangeText={setHandoverDetails}
              multiline
            />

            <View style={styles.modalButtonsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setHandoverModalVisible(false)}
              >
                <Text style={styles.modalCancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSubmitHandoverBtn}
                disabled={actionLoading}
                onPress={handleRequestHandover}
              >
                <Text style={styles.modalSubmitBtnText}>Submit Handover</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  centerContainer: {
    flex: 1,
    backgroundColor: '#090D16',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    gap: 12,
  },
  loadingText: {
    color: '#94A3B8',
    fontSize: 14,
    fontWeight: '500',
  },
  notFoundTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
  },
  backBtn: {
    marginTop: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#1E293B',
    borderRadius: 8,
  },
  backBtnText: {
    color: '#38BDF8',
    fontSize: 12,
    fontWeight: '600',
  },
  header: {
    paddingTop: 54,
    paddingHorizontal: 16,
    paddingBottom: 14,
    backgroundColor: '#0D1424',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerBackBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitleWrap: {
    alignItems: 'center',
  },
  headerTitle: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    color: '#94A3B8',
    fontSize: 11,
  },
  chatHeaderBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    gap: 14,
    paddingBottom: 40,
  },
  severityCard: {
    backgroundColor: '#1C131D',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#EF444460',
    padding: 16,
  },
  severityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  severityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#DC2626',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  severityBadgeText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '800',
  },
  statusPill: {
    backgroundColor: '#374151',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  statusPillText: {
    color: '#E5E7EB',
    fontSize: 11,
    fontWeight: '700',
  },
  sourceText: {
    color: '#FCA5A5',
    fontSize: 13,
    fontWeight: '600',
    marginTop: 4,
  },
  startedText: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  reasonsBox: {
    marginTop: 10,
    backgroundColor: '#2A1723',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#4A1D2B',
  },
  reasonsTitle: {
    color: '#F87171',
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 4,
  },
  reasonsList: {
    color: '#CBD5E1',
    fontSize: 12,
    lineHeight: 16,
  },
  card: {
    backgroundColor: '#0F172A',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  cardHeaderTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  cardSectionTitle: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  mapLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  mapLinkText: {
    color: '#60A5FA',
    fontSize: 11,
    fontWeight: '600',
  },
  locDetailsBox: {
    backgroundColor: '#1E293B60',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#33415550',
    gap: 4,
  },
  locZoneName: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '700',
  },
  locCoords: {
    color: '#94A3B8',
    fontSize: 12,
  },
  locFixStatus: {
    color: '#34D399',
    fontSize: 11,
    fontWeight: '600',
  },
  actionGrid: {
    gap: 10,
  },
  primaryActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 10,
  },
  acceptBtn: {
    backgroundColor: '#10B981',
  },
  startBtn: {
    backgroundColor: '#F59E0B',
  },
  arriveBtn: {
    backgroundColor: '#8B5CF6',
  },
  completeBtn: {
    backgroundColor: '#059669',
  },
  primaryActionBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  secondaryActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
  },
  rejectBtn: {
    borderColor: '#EF444450',
  },
  rejectBtnText: {
    color: '#EF4444',
    fontSize: 12,
    fontWeight: '700',
  },
  arrivalActionBox: {
    gap: 10,
  },
  overrideWarningBox: {
    backgroundColor: '#2D2013',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#78350F',
    gap: 8,
  },
  overrideWarningText: {
    color: '#FDE68A',
    fontSize: 12,
    lineHeight: 16,
  },
  overrideBtn: {
    backgroundColor: '#D97706',
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
  },
  overrideBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800',
  },
  timelineList: {
    gap: 12,
  },
  emptyTimelineText: {
    color: '#64748B',
    fontSize: 12,
  },
  timelineItem: {
    flexDirection: 'row',
    gap: 10,
  },
  timelineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#3B82F6',
    marginTop: 4,
  },
  timelineContent: {
    flex: 1,
  },
  timelineTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  timelineAction: {
    color: '#F1F5F9',
    fontSize: 12,
    fontWeight: '700',
  },
  timelineTime: {
    color: '#64748B',
    fontSize: 10,
  },
  timelineActor: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  timelineReason: {
    color: '#CBD5E1',
    fontSize: 11,
    fontStyle: 'italic',
    marginTop: 2,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#0F172A',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 20,
    maxHeight: '80%',
    gap: 12,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
  },
  modalSubtitle: {
    color: '#94A3B8',
    fontSize: 12,
  },
  reasonScroll: {
    maxHeight: 180,
  },
  reasonOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  reasonOptionSelected: {
    backgroundColor: '#1E293B',
  },
  reasonRadio: {
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: '#64748B',
  },
  reasonRadioSelected: {
    borderColor: '#EF4444',
    backgroundColor: '#EF4444',
  },
  reasonOptionText: {
    color: '#E2E8F0',
    fontSize: 12,
    fontWeight: '500',
    flex: 1,
  },
  modalInputSingle: {
    backgroundColor: '#1E293B',
    color: '#F8FAFC',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalTextInput: {
    backgroundColor: '#1E293B',
    color: '#F8FAFC',
    borderRadius: 8,
    padding: 12,
    height: 80,
    textAlignVertical: 'top',
    fontSize: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalButtonsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 6,
  },
  modalCancelBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    alignItems: 'center',
  },
  modalCancelBtnText: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '600',
  },
  modalSubmitRejectBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#DC2626',
    alignItems: 'center',
  },
  modalSubmitCompleteBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#059669',
    alignItems: 'center',
  },
  modalSubmitAssessBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#2563EB',
    alignItems: 'center',
  },
  modalSubmitHandoverBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#D97706',
    alignItems: 'center',
  },
  modalSubmitBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
  },
  onSceneActionStack: {
    gap: 10,
  },
  assessBtn: {
    backgroundColor: '#2563EB',
  },
  onSceneSecondaryRow: {
    flexDirection: 'row',
    gap: 10,
  },
  handoverBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#D97706',
  },
  handoverBtnText: {
    color: '#FBBF24',
    fontSize: 12,
    fontWeight: '700',
  },
  fieldNoteInput: {
    backgroundColor: '#0B1120',
    color: '#F8FAFC',
    borderRadius: 8,
    padding: 12,
    height: 72,
    textAlignVertical: 'top',
    fontSize: 13,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 10,
  },
  saveNoteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#0284C7',
    paddingVertical: 10,
    borderRadius: 8,
  },
  saveNoteBtnDisabled: {
    backgroundColor: '#1E293B',
  },
  saveNoteBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 6,
  },
  checkboxRowActive: {},
  checkboxBox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#475569',
    backgroundColor: '#1E293B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxBoxActive: {
    backgroundColor: '#2563EB',
    borderColor: '#3B82F6',
  },
  checkboxLabel: {
    fontSize: 12,
    color: '#CBD5E1',
    flex: 1,
  },
});

