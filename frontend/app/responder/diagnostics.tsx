import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { router } from 'expo-router';
import {
  Activity,
  ArrowLeft,
  BatteryCharging,
  CheckCircle,
  Compass,
  Cpu,
  Database,
  Globe,
  HardDrive,
  Navigation,
  Radio,
  RefreshCw,
  Server,
  Shield,
  Wifi,
  WifiOff,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { useResponderStore } from '@/store/responderStore';

export default function ResponderDiagnosticsScreen() {
  const {
    profile,
    currentGps,
    offlineNotesQueue,
    isSyncingNotes,
    lastNotesSyncTime,
    diagnostics,
    syncPendingNotes,
    loadProfile,
  } = useResponderStore();

  const [refreshing, setRefreshing] = useState(false);

  const handleManualSync = async () => {
    if (offlineNotesQueue.length === 0) {
      Toast.show({ type: 'info', text1: 'Queue Empty', text2: 'No offline notes pending synchronization' });
      return;
    }
    const synced = await syncPendingNotes();
    Toast.show({
      type: synced > 0 ? 'success' : 'error',
      text1: synced > 0 ? 'Notes Synchronized' : 'Sync Failed',
      text2: synced > 0 ? `Synced ${synced} notes with central command` : 'Could not reach server. Notes remain queued.',
    });
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadProfile();
    setRefreshing(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <ArrowLeft size={20} color="#F8FAFC" />
        </TouchableOpacity>
        <View>
          <Text style={styles.headerTitle}>Field Diagnostics</Text>
          <Text style={styles.headerSubtitle}>Real-time telemetry & system health</Text>
        </View>
        <TouchableOpacity style={styles.refreshButton} onPress={handleRefresh}>
          {refreshing ? <ActivityIndicator size="small" color="#3B82F6" /> : <RefreshCw size={18} color="#94A3B8" />}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Network & Realtime Status */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHeader}>
            <Globe size={18} color="#3B82F6" />
            <Text style={styles.sectionTitle}>Network & WebSocket</Text>
          </View>
          <View style={styles.grid}>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>WS Channel</Text>
              <View style={styles.badgeRow}>
                <View style={[styles.dot, { backgroundColor: '#10B981' }]} />
                <Text style={styles.gridValue}>CONNECTED</Text>
              </View>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>API Gateway</Text>
              <View style={styles.badgeRow}>
                <View style={[styles.dot, { backgroundColor: '#10B981' }]} />
                <Text style={styles.gridValue}>OPERATIONAL</Text>
              </View>
            </View>
          </View>
        </View>

        {/* GPS Telemetry */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHeader}>
            <Navigation size={18} color="#10B981" />
            <Text style={styles.sectionTitle}>GPS Telemetry Engine</Text>
          </View>
          <View style={styles.grid}>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Latitude</Text>
              <Text style={styles.gridValueMono}>{currentGps?.latitude ? currentGps.latitude.toFixed(6) : '—'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Longitude</Text>
              <Text style={styles.gridValueMono}>{currentGps?.longitude ? currentGps.longitude.toFixed(6) : '—'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Accuracy</Text>
              <Text style={styles.gridValueMono}>{currentGps?.accuracy ? `±${currentGps.accuracy.toFixed(1)} m` : '—'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Speed</Text>
              <Text style={styles.gridValueMono}>{currentGps?.speed ? `${(currentGps.speed * 3.6).toFixed(1)} km/h` : '0.0 km/h'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Heading</Text>
              <Text style={styles.gridValueMono}>{currentGps?.heading ? `${currentGps.heading.toFixed(0)}°` : '—'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Tracking Active</Text>
              <Text style={[styles.gridValue, { color: profile?.responder?.tracking_active ? '#10B981' : '#94A3B8' }]}>
                {profile?.responder?.tracking_active ? 'ENABLED' : 'STANDBY'}
              </Text>
            </View>
          </View>
        </View>

        {/* Offline Queue Engine */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHeader}>
            <Database size={18} color="#F59E0B" />
            <Text style={styles.sectionTitle}>Offline Field Queue</Text>
          </View>
          <View style={styles.grid}>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Pending Notes</Text>
              <Text style={[styles.gridValue, { color: offlineNotesQueue.length > 0 ? '#F59E0B' : '#10B981' }]}>
                {offlineNotesQueue.length} notes
              </Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Last Sync</Text>
              <Text style={styles.gridValueSmall}>
                {lastNotesSyncTime ? new Date(lastNotesSyncTime).toLocaleTimeString() : 'Never'}
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.syncButton, (offlineNotesQueue.length === 0 || isSyncingNotes) && styles.syncButtonDisabled]}
            onPress={handleManualSync}
            disabled={offlineNotesQueue.length === 0 || isSyncingNotes}
          >
            {isSyncingNotes ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <>
                <RefreshCw size={16} color="#FFFFFF" />
                <Text style={styles.syncButtonText}>Sync Queue Now ({offlineNotesQueue.length})</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Responder Hardware Identity */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHeader}>
            <Shield size={18} color="#8B5CF6" />
            <Text style={styles.sectionTitle}>Unit & Responder Identity</Text>
          </View>
          <View style={styles.grid}>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Responder ID</Text>
              <Text style={styles.gridValueMono}>{profile?.responder?.responder_id || '—'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Assigned Unit</Text>
              <Text style={styles.gridValue}>{profile?.active_unit?.callsign || 'Standalone Unit'}</Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Capabilities</Text>
              <Text style={styles.gridValueSmall}>
                {profile?.responder?.capabilities ? profile.responder.capabilities.join(', ') : 'STANDARD'}
              </Text>
            </View>
            <View style={styles.gridItem}>
              <Text style={styles.gridLabel}>Assigned Incident</Text>
              <Text style={styles.gridValueMono}>{profile?.active_assignment?.incident_id || 'None (Idle)'}</Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  backButton: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#1E293B',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#64748B',
  },
  refreshButton: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#1E293B',
  },
  scrollContent: {
    padding: 16,
    gap: 16,
  },
  sectionCard: {
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  gridItem: {
    width: '47%',
    backgroundColor: '#0B1120',
    borderRadius: 8,
    padding: 10,
  },
  gridLabel: {
    fontSize: 11,
    color: '#64748B',
    textTransform: 'uppercase',
    fontWeight: '600',
    marginBottom: 4,
  },
  gridValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#E2E8F0',
  },
  gridValueSmall: {
    fontSize: 12,
    fontWeight: '600',
    color: '#E2E8F0',
  },
  gridValueMono: {
    fontSize: 13,
    fontWeight: '700',
    color: '#93C5FD',
    fontFamily: 'monospace',
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#2563EB',
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 14,
  },
  syncButtonDisabled: {
    backgroundColor: '#1E293B',
  },
  syncButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
