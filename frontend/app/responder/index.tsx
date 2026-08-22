import { useEffect, useState, useRef } from 'react';
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { router } from 'expo-router';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BatteryCharging,
  Compass,
  Flame,
  HeartPulse,
  LogOut,
  MapPin,
  MessageSquare,
  Navigation,
  Power,
  Radio,
  RefreshCw,
  Shield,
  ShieldAlert,
  User,
  Users,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { responderApi, incidentAssignmentApi } from '@/lib/api';
import type {
  AssignmentRecord,
  IncidentRecord,
  Responder,
  ResponderLocationLive,
  ResponderSelfProfile,
  ResponderStatus,
  ResponderUnitRecord,
} from '@/types';

export default function ResponderDashboardScreen() {
  const [profile, setProfile] = useState<ResponderSelfProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [trackingLoading, setTrackingLoading] = useState(false);

  useEffect(() => {
    loadProfile();
    const interval = setInterval(loadProfile, 8000);
    return () => clearInterval(interval);
  }, []);

  async function loadProfile() {
    try {
      const res = await responderApi.getMe();
      if (res?.data) {
        setProfile(res.data);
      }
    } catch (e: any) {
      // If mock mode or network error
      console.warn('Failed to load responder profile:', e?.message || e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function handleToggleStatus(targetStatus: ResponderStatus) {
    if (!profile?.responder) return;
    try {
      setStatusUpdating(true);
      await responderApi.updateStatus(targetStatus, `Status updated by responder`);
      Toast.show({
        type: 'success',
        text1: 'Status Updated',
        text2: `Status changed to ${targetStatus}`,
      });
      await loadProfile();
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Status Transition Rejected',
        text2: err?.response?.data?.detail || err?.message || 'Invalid transition',
      });
    } finally {
      setStatusUpdating(false);
    }
  }

  async function handleToggleTracking() {
    if (!profile?.responder) return;
    const isCurrentlyTracking = profile.responder.tracking_active;
    try {
      setTrackingLoading(true);
      if (isCurrentlyTracking) {
        await responderApi.stopTracking(88);
        Toast.show({
          type: 'info',
          text1: 'Tracking Paused',
          text2: 'Live GPS broadcast session ended.',
        });
      } else {
        await responderApi.startTracking(88);
        Toast.show({
          type: 'success',
          text1: 'Live Tracking Active',
          text2: 'Transmitting high-precision GPS to Dispatch Command.',
        });
      }
      await loadProfile();
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Tracking Action Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not toggle tracking session',
      });
    } finally {
      setTrackingLoading(false);
    }
  }

  const responder = profile?.responder;
  const unit = profile?.active_unit;
  const assignment = profile?.active_assignment;
  const incident = profile?.active_incident;
  const location = profile?.live_location;

  const isAssignedOrResponding =
    responder?.status === 'ASSIGNED' ||
    responder?.status === 'RESPONDING' ||
    responder?.status === 'ON_SCENE';

  const statusColor =
    responder?.status === 'AVAILABLE'
      ? '#10B981'
      : responder?.status === 'RESPONDING'
      ? '#F59E0B'
      : responder?.status === 'ON_SCENE'
      ? '#8B5CF6'
      : responder?.status === 'ASSIGNED'
      ? '#3B82F6'
      : responder?.status === 'UNAVAILABLE'
      ? '#EF4444'
      : '#6B7280';

  if (loading && !profile) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>Connecting to TourSafe Tactical Grid...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Top Tactical App Bar */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.badgeIconWrap}>
            <Shield size={20} color="#60A5FA" />
          </View>
          <View>
            <Text style={styles.responderName}>{responder?.name || 'Field Responder'}</Text>
            <Text style={styles.responderRole}>
              {responder?.type || 'FIELD_RESPONDER'} {unit ? `• ${unit.callsign}` : ''}
            </Text>
          </View>
        </View>

        <TouchableOpacity
          style={styles.refreshBtn}
          onPress={() => {
            setRefreshing(true);
            loadProfile();
          }}
        >
          <RefreshCw size={18} color="#94A3B8" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollArea}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadProfile();
            }}
            tintColor="#3B82F6"
          />
        }
      >
        {/* Status & Availability Command Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <Radio size={16} color="#60A5FA" />
              <Text style={styles.cardSectionTitle}>OPERATIONAL READINESS</Text>
            </View>
            <View style={[styles.statusPill, { backgroundColor: `${statusColor}20`, borderColor: statusColor }]}>
              <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
              <Text style={[styles.statusPillText, { color: statusColor }]}>
                {responder?.status || 'OFFLINE'}
              </Text>
            </View>
          </View>

          <Text style={styles.statusDescription}>
            {responder?.status === 'AVAILABLE'
              ? 'Ready for dispatch. You are discoverable by Authority Command.'
              : responder?.status === 'ASSIGNED'
              ? 'Incident dispatched. Acceptance required.'
              : responder?.status === 'RESPONDING'
              ? 'Active response in transit.'
              : responder?.status === 'ON_SCENE'
              ? 'On-scene tactical operations underway.'
              : responder?.status === 'UNAVAILABLE'
              ? 'Temporarily off-duty / maintenance.'
              : 'Offline. Connect when ready to receive dispatches.'}
          </Text>

          {/* Status Selector Buttons */}
          <View style={styles.statusButtonGroup}>
            <TouchableOpacity
              style={[
                styles.statusBtn,
                responder?.status === 'AVAILABLE' && styles.statusBtnActiveAvailable,
              ]}
              disabled={statusUpdating || isAssignedOrResponding}
              onPress={() => handleToggleStatus('AVAILABLE')}
            >
              <Text
                style={[
                  styles.statusBtnText,
                  responder?.status === 'AVAILABLE' && styles.statusBtnTextActive,
                ]}
              >
                AVAILABLE
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.statusBtn,
                responder?.status === 'UNAVAILABLE' && styles.statusBtnActiveUnavailable,
              ]}
              disabled={statusUpdating || isAssignedOrResponding}
              onPress={() => handleToggleStatus('UNAVAILABLE')}
            >
              <Text
                style={[
                  styles.statusBtnText,
                  responder?.status === 'UNAVAILABLE' && styles.statusBtnTextActive,
                ]}
              >
                UNAVAILABLE
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.statusBtn,
                responder?.status === 'OFFLINE' && styles.statusBtnActiveOffline,
              ]}
              disabled={statusUpdating || isAssignedOrResponding}
              onPress={() => handleToggleStatus('OFFLINE')}
            >
              <Text
                style={[
                  styles.statusBtnText,
                  responder?.status === 'OFFLINE' && styles.statusBtnTextActive,
                ]}
              >
                OFFLINE
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Live GPS Broadcast Session Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <Compass size={16} color="#34D399" />
              <Text style={styles.cardSectionTitle}>TACTICAL GPS TRACKING</Text>
            </View>
            <View
              style={[
                styles.statusPill,
                {
                  backgroundColor: responder?.tracking_active ? '#065F4640' : '#37415140',
                  borderColor: responder?.tracking_active ? '#10B981' : '#6B7280',
                },
              ]}
            >
              <Text
                style={[
                  styles.statusPillText,
                  { color: responder?.tracking_active ? '#34D399' : '#9CA3AF' },
                ]}
              >
                {responder?.tracking_active ? 'TRANSMITTING' : 'PAUSED'}
              </Text>
            </View>
          </View>

          <View style={styles.locationMetaGrid}>
            <View style={styles.locationMetaItem}>
              <Text style={styles.metaLabel}>COORDINATES</Text>
              <Text style={styles.metaValue}>
                {location
                  ? `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`
                  : responder?.current_location
                  ? `${responder.current_location.latitude.toFixed(4)}, ${responder.current_location.longitude.toFixed(4)}`
                  : 'No Fix'}
              </Text>
            </View>

            <View style={styles.locationMetaItem}>
              <Text style={styles.metaLabel}>ACCURACY</Text>
              <Text
                style={[
                  styles.metaValue,
                  {
                    color:
                      (location?.accuracy || 10) < 25 ? '#34D399' : '#F59E0B',
                  },
                ]}
              >
                ±{location?.accuracy ? Math.round(location.accuracy) : 10}m
              </Text>
            </View>

            <View style={styles.locationMetaItem}>
              <Text style={styles.metaLabel}>SPEED</Text>
              <Text style={styles.metaValue}>
                {location?.speed ? `${(location.speed * 3.6).toFixed(1)} km/h` : '0 km/h'}
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={[
              styles.trackingActionBtn,
              responder?.tracking_active ? styles.trackingBtnStop : styles.trackingBtnStart,
            ]}
            disabled={trackingLoading}
            onPress={handleToggleTracking}
          >
            <Power size={16} color="#FFFFFF" />
            <Text style={styles.trackingActionBtnText}>
              {trackingLoading
                ? 'UPDATING...'
                : responder?.tracking_active
                ? 'STOP GPS BROADCAST'
                : 'START GPS BROADCAST'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* ACTIVE INCIDENT ACTION CARD */}
        {assignment && incident ? (
          <View style={[styles.card, styles.activeIncidentCard]}>
            <View style={styles.incidentBanner}>
              <View style={styles.incidentBannerTitle}>
                <ShieldAlert size={18} color="#EF4444" />
                <Text style={styles.incidentBannerText}>ACTIVE INCIDENT ASSIGNMENT</Text>
              </View>
              <View
                style={[
                  styles.severityPill,
                  {
                    backgroundColor:
                      incident.severity === 'CRITICAL'
                        ? '#7F1D1D'
                        : incident.severity === 'HIGH'
                        ? '#78350F'
                        : '#1E3A8A',
                  },
                ]}
              >
                <Text style={styles.severityPillText}>{incident.severity}</Text>
              </View>
            </View>

            <Text style={styles.incidentIdText}>ID: {incident.incident_id}</Text>
            <Text style={styles.incidentSourceText}>
              Source: {incident.source} • Status: {assignment.status}
            </Text>

            {incident.reasons && incident.reasons.length > 0 && (
              <View style={styles.reasonsBox}>
                <Text style={styles.reasonsText}>{incident.reasons.join(', ')}</Text>
              </View>
            )}

            {incident.location_data && (
              <View style={styles.incidentLocationRow}>
                <MapPin size={14} color="#60A5FA" />
                <Text style={styles.incidentLocationText}>
                  {incident.location_data.zone_name || 'Assigned Zone'} (
                  {incident.location_data.latitude.toFixed(4)},{' '}
                  {incident.location_data.longitude.toFixed(4)})
                </Text>
              </View>
            )}

            {/* Incident Quick Actions */}
            <View style={styles.incidentActionsRow}>
              <TouchableOpacity
                style={styles.openIncidentBtn}
                onPress={() =>
                  router.push({
                    pathname: '/responder/incident',
                    params: { incident_id: incident.incident_id },
                  })
                }
              >
                <Text style={styles.openIncidentBtnText}>OPEN INCIDENT COMMAND</Text>
                <ArrowRight size={16} color="#FFFFFF" />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.chatShortcutBtn}
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
          </View>
        ) : (
          <View style={styles.idleIncidentCard}>
            <HeartPulse size={24} color="#4B5563" />
            <Text style={styles.idleTitle}>No Active Incident Assigned</Text>
            <Text style={styles.idleSubtitle}>
              Stay in AVAILABLE status to receive dispatches from Authority Command.
            </Text>
          </View>
        )}

        {/* Tactical Navigation Shortcuts */}
        <View style={styles.shortcutsRow}>
          <TouchableOpacity
            style={styles.shortcutCard}
            onPress={() => router.push('/responder/map')}
          >
            <View style={[styles.shortcutIconWrap, { backgroundColor: '#1E293B' }]}>
              <Navigation size={20} color="#38BDF8" />
            </View>
            <Text style={styles.shortcutTitle}>Tactical Map</Text>
            <Text style={styles.shortcutSub}>View GPS & Incidents</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.shortcutCard}
            onPress={() => {
              if (incident) {
                router.push({
                  pathname: '/responder/messages',
                  params: { incident_id: incident.incident_id },
                });
              } else {
                Toast.show({
                  type: 'info',
                  text1: 'No Active Incident',
                  text2: 'Operational chat is tied to assigned incidents.',
                });
              }
            }}
          >
            <View style={[styles.shortcutIconWrap, { backgroundColor: '#1E293B' }]}>
              <MessageSquare size={20} color="#818CF8" />
            </View>
            <Text style={styles.shortcutTitle}>Operational Chat</Text>
            <Text style={styles.shortcutSub}>Authority Comms</Text>
          </TouchableOpacity>
        </View>

        {/* Assigned Unit & Capabilities */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardHeaderTitleRow}>
              <Users size={16} color="#A78BFA" />
              <Text style={styles.cardSectionTitle}>ASSIGNED UNIT & CAPABILITIES</Text>
            </View>
          </View>

          <View style={styles.unitInfoRow}>
            <Text style={styles.unitName}>{unit ? unit.callsign : 'Independent Dispatch'}</Text>
            <Text style={styles.unitType}>{unit ? unit.unit_type : responder?.type}</Text>
          </View>

          <View style={styles.capsWrapper}>
            {(responder?.capabilities || ['GENERAL_PATROL']).map((cap, idx) => (
              <View key={idx} style={styles.capTag}>
                <Text style={styles.capTagText}>{cap}</Text>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>
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
    gap: 12,
  },
  loadingText: {
    color: '#94A3B8',
    fontSize: 14,
    fontWeight: '500',
  },
  header: {
    paddingTop: 54,
    paddingHorizontal: 20,
    paddingBottom: 16,
    backgroundColor: '#0D1424',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  badgeIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    justifyContent: 'center',
    alignItems: 'center',
  },
  responderName: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
  },
  responderRole: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 2,
  },
  refreshBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    gap: 16,
    paddingBottom: 40,
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
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: '700',
  },
  statusDescription: {
    color: '#CBD5E1',
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 14,
  },
  statusButtonGroup: {
    flexDirection: 'row',
    gap: 8,
  },
  statusBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  statusBtnActiveAvailable: {
    backgroundColor: '#065F46',
    borderColor: '#10B981',
  },
  statusBtnActiveUnavailable: {
    backgroundColor: '#7F1D1D',
    borderColor: '#EF4444',
  },
  statusBtnActiveOffline: {
    backgroundColor: '#374151',
    borderColor: '#6B7280',
  },
  statusBtnText: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '700',
  },
  statusBtnTextActive: {
    color: '#FFFFFF',
  },
  locationMetaGrid: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 14,
  },
  locationMetaItem: {
    flex: 1,
    backgroundColor: '#1E293B60',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#33415550',
  },
  metaLabel: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 4,
  },
  metaValue: {
    color: '#F1F5F9',
    fontSize: 12,
    fontWeight: '700',
  },
  trackingActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 8,
  },
  trackingBtnStart: {
    backgroundColor: '#2563EB',
  },
  trackingBtnStop: {
    backgroundColor: '#DC2626',
  },
  trackingActionBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  activeIncidentCard: {
    borderColor: '#DC262680',
    backgroundColor: '#18111A',
  },
  incidentBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  incidentBannerTitle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  incidentBannerText: {
    color: '#F87171',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  severityPill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  severityPillText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
  },
  incidentIdText: {
    color: '#F1F5F9',
    fontSize: 14,
    fontWeight: '700',
  },
  incidentSourceText: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 2,
    marginBottom: 8,
  },
  reasonsBox: {
    backgroundColor: '#2A1723',
    padding: 8,
    borderRadius: 6,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#4A1D2B',
  },
  reasonsText: {
    color: '#FCA5A5',
    fontSize: 12,
    fontWeight: '500',
  },
  incidentLocationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 14,
  },
  incidentLocationText: {
    color: '#93C5FD',
    fontSize: 12,
  },
  incidentActionsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  openIncidentBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#DC2626',
    paddingVertical: 12,
    borderRadius: 8,
  },
  openIncidentBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  chatShortcutBtn: {
    width: 44,
    height: 44,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  idleIncidentCard: {
    backgroundColor: '#0F172A',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  idleTitle: {
    color: '#94A3B8',
    fontSize: 14,
    fontWeight: '700',
    marginTop: 6,
  },
  idleSubtitle: {
    color: '#64748B',
    fontSize: 12,
    textAlign: 'center',
  },
  shortcutsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  shortcutCard: {
    flex: 1,
    backgroundColor: '#0F172A',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 14,
  },
  shortcutIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  shortcutTitle: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '700',
  },
  shortcutSub: {
    color: '#64748B',
    fontSize: 11,
    marginTop: 2,
  },
  unitInfoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  unitName: {
    color: '#F1F5F9',
    fontSize: 14,
    fontWeight: '700',
  },
  unitType: {
    color: '#94A3B8',
    fontSize: 12,
  },
  capsWrapper: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  capTag: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  capTagText: {
    color: '#C4B5FD',
    fontSize: 10,
    fontWeight: '600',
  },
});
