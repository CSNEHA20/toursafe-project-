import React, { useState, useEffect } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Platform,
  ActivityIndicator,
} from 'react-native';
import {
  Layers,
  MapPin,
  RefreshCw,
  ArrowLeft,
  Shield,
  AlertTriangle,
  Clock,
  Radio,
  Compass,
} from 'lucide-react-native';
import { useRouter } from 'expo-router';
import Toast from 'react-native-toast-message';
import { useLocationStore } from '@/store/locationStore';
import { useGeofenceStore } from '@/store/geofenceStore';
import { geofenceApi } from '@/lib/api';
import { realtimeClient } from '@/lib/realtimeClient';

export default function GeofenceDiagnosticsScreen() {
  const router = useRouter();
  const currentLocation = useLocationStore((state) => state.currentLocation);
  const {
    activeZones,
    highestRiskLevel,
    primaryZoneType,
    isStale,
    lastEventNotice,
  } = useGeofenceStore();

  const [loading, setLoading] = useState(false);
  const [diagnosticsData, setDiagnosticsData] = useState<any>(null);

  const fetchLiveDiagnostics = async () => {
    setLoading(true);
    try {
      const res = await geofenceApi.getMyCurrentZones();
      useGeofenceStore.getState().setSnapshot(res.data);

      const diagRes = await geofenceApi.getDiagnostics('me').catch(() => null);
      if (diagRes?.data) {
        setDiagnosticsData(diagRes.data);
      }
      Toast.show({ type: 'success', text1: 'Diagnostics refreshed' });
    } catch (err: any) {
      Toast.show({ type: 'error', text1: 'Failed to fetch diagnostics', text2: err?.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLiveDiagnostics();

    // Subscribe to realtime geofence events
    const unsubEntered = realtimeClient.onEvent('zone.entered', (env: any) => {
      useGeofenceStore.getState().handleRealtimeZoneEvent(env.payload);
      Toast.show({
        type: 'info',
        text1: `Zone Entered: ${env.payload?.zone_name}`,
        text2: `Risk Level: ${env.payload?.risk_level}`,
      });
    });

    const unsubExited = realtimeClient.onEvent('zone.exited', (env: any) => {
      useGeofenceStore.getState().handleRealtimeZoneEvent(env.payload);
      Toast.show({
        type: 'info',
        text1: `Zone Exited: ${env.payload?.zone_name}`,
        text2: `Dwell: ${env.payload?.dwell_duration_seconds}s`,
      });
    });

    const unsubDwell = realtimeClient.onEvent('zone.dwell.threshold_reached', (env: any) => {
      useGeofenceStore.getState().handleRealtimeZoneEvent(env.payload);
      Toast.show({
        type: 'info',
        text1: `Dwell Threshold Reached: ${env.payload?.zone_name}`,
      });
    });

    return () => {
      unsubEntered();
      unsubExited();
      unsubDwell();
    };
  }, []);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <ArrowLeft size={20} color="#94A3B8" />
        </TouchableOpacity>
        <View style={styles.headerTitleContainer}>
          <Text style={styles.headerTitle}>Geofencing Diagnostics</Text>
          <Text style={styles.headerSubtitle}>Real-time GeoJSON point-in-polygon engine</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={fetchLiveDiagnostics}>
          {loading ? (
            <ActivityIndicator size="small" color="#38BDF8" />
          ) : (
            <RefreshCw size={18} color="#38BDF8" />
          )}
        </TouchableOpacity>
      </View>

      {/* Real-Time Live Status Banner */}
      <View style={[styles.card, styles.statusCard]}>
        <View style={styles.rowBetween}>
          <View style={styles.row}>
            <Layers size={22} color="#38BDF8" />
            <Text style={styles.cardTitle}>Engine Status</Text>
          </View>
          <View style={[styles.badge, isStale ? styles.badgeStale : styles.badgeLive]}>
            <Text style={styles.badgeText}>{isStale ? 'STALE GPS' : 'LIVE MONITORING'}</Text>
          </View>
        </View>

        <View style={styles.metricGrid}>
          <View style={styles.metricBox}>
            <Text style={styles.metricLabel}>Active Zones</Text>
            <Text style={styles.metricValue}>{activeZones.length}</Text>
          </View>
          <View style={styles.metricBox}>
            <Text style={styles.metricLabel}>Highest Risk</Text>
            <Text style={[styles.metricValue, { color: highestRiskLevel === 'critical' ? '#F43F5E' : highestRiskLevel === 'high' ? '#FB923C' : '#34D399' }]}>
              {highestRiskLevel.toUpperCase()}
            </Text>
          </View>
          <View style={styles.metricBox}>
            <Text style={styles.metricLabel}>Primary Type</Text>
            <Text style={styles.metricValue}>{primaryZoneType.toUpperCase()}</Text>
          </View>
        </View>

        {lastEventNotice && (
          <View style={styles.eventNoticeBox}>
            <Text style={styles.eventNoticeLabel}>Last Realtime Event:</Text>
            <Text style={styles.eventNoticeText}>{lastEventNotice}</Text>
          </View>
        )}
      </View>

      {/* Current GPS Stream Info */}
      <View style={styles.card}>
        <View style={styles.row}>
          <MapPin size={20} color="#F59E0B" />
          <Text style={styles.cardTitle}>Live GPS Input</Text>
        </View>
        {currentLocation ? (
          <View style={styles.coordsBox}>
            <Text style={styles.coordText}>
              Lat: <Text style={styles.monoText}>{currentLocation.latitude.toFixed(6)}</Text> | Lon:{' '}
              <Text style={styles.monoText}>{currentLocation.longitude.toFixed(6)}</Text>
            </Text>
            <Text style={styles.subCoordText}>
              Accuracy: {currentLocation.accuracy ? `±${currentLocation.accuracy.toFixed(1)}m` : 'N/A'} | Seq:{' '}
              {currentLocation.sequence_number} | Provider: {currentLocation.provider || 'gps'}
            </Text>
          </View>
        ) : (
          <Text style={styles.mutedText}>No active GPS location sample streaming.</Text>
        )}
      </View>

      {/* Active Zone Memberships */}
      <View style={styles.card}>
        <View style={styles.row}>
          <Shield size={20} color="#34D399" />
          <Text style={styles.cardTitle}>Active Zone Memberships ({activeZones.length})</Text>
        </View>

        {activeZones.length === 0 ? (
          <Text style={styles.mutedText}>Tourist is currently outside all configured safety zones.</Text>
        ) : (
          activeZones.map((z, idx) => (
            <View key={z.zone_id || idx} style={styles.zoneItem}>
              <View style={styles.rowBetween}>
                <Text style={styles.zoneName}>{z.name}</Text>
                <View style={[styles.riskPill, z.risk_level === 'critical' ? styles.pillRed : z.risk_level === 'high' ? styles.pillOrange : styles.pillGreen]}>
                  <Text style={styles.riskPillText}>{z.risk_level.toUpperCase()}</Text>
                </View>
              </View>

              <View style={styles.zoneDetailsRow}>
                <View style={styles.row}>
                  <Clock size={14} color="#94A3B8" />
                  <Text style={styles.detailText}>
                    Dwell: {Math.floor(z.dwell_duration_seconds / 60)}m {Math.floor(z.dwell_duration_seconds % 60)}s
                  </Text>
                </View>
                <View style={styles.row}>
                  <Compass size={14} color="#94A3B8" />
                  <Text style={styles.detailText}>
                    Boundary Dist: {z.distance_to_boundary_meters?.toFixed(1)}m
                  </Text>
                </View>
              </View>

              <View style={styles.zoneDetailsRow}>
                <Text style={styles.detailText}>
                  State: <Text style={{ color: '#38BDF8', fontWeight: 'bold' }}>{z.state.toUpperCase()}</Text>
                </Text>
                <Text style={styles.detailText}>
                  Confidence: <Text style={{ color: '#34D399' }}>{z.confidence_level.toUpperCase()} ({(z.confidence_score * 100).toFixed(0)}%)</Text>
                </Text>
              </View>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
    marginTop: Platform.OS === 'ios' ? 44 : 10,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#1E293B',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  headerTitleContainer: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#64748B',
  },
  refreshBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#1E293B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  statusCard: {
    borderLeftWidth: 4,
    borderLeftColor: '#38BDF8',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#F8FAFC',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  badgeLive: {
    backgroundColor: 'rgba(52, 211, 153, 0.2)',
  },
  badgeStale: {
    backgroundColor: 'rgba(244, 63, 94, 0.2)',
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#34D399',
  },
  metricGrid: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
  },
  metricBox: {
    flex: 1,
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: 11,
    color: '#94A3B8',
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  eventNoticeBox: {
    marginTop: 12,
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: 'rgba(56, 189, 248, 0.2)',
  },
  eventNoticeLabel: {
    fontSize: 11,
    color: '#38BDF8',
    fontWeight: 'bold',
  },
  eventNoticeText: {
    fontSize: 12,
    color: '#E2E8F0',
    marginTop: 2,
  },
  coordsBox: {
    marginTop: 10,
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
  },
  coordText: {
    fontSize: 13,
    color: '#F8FAFC',
    fontWeight: '500',
  },
  subCoordText: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 4,
  },
  monoText: {
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    color: '#38BDF8',
  },
  mutedText: {
    fontSize: 13,
    color: '#64748B',
    marginTop: 10,
    fontStyle: 'italic',
  },
  zoneItem: {
    marginTop: 12,
    backgroundColor: '#0F172A',
    borderRadius: 8,
    padding: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#38BDF8',
  },
  zoneName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#F8FAFC',
  },
  riskPill: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  pillGreen: {
    backgroundColor: 'rgba(52, 211, 153, 0.2)',
  },
  pillOrange: {
    backgroundColor: 'rgba(251, 146, 60, 0.2)',
  },
  pillRed: {
    backgroundColor: 'rgba(244, 63, 94, 0.2)',
  },
  riskPillText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  zoneDetailsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  detailText: {
    fontSize: 11,
    color: '#94A3B8',
  },
});
