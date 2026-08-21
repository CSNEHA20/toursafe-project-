import React, { useState, useEffect, useCallback } from 'react';
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
  MapPin,
  ShieldAlert,
  Layers3,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
  Play,
  Pause,
  Square,
  Radio,
  Gauge,
} from 'lucide-react-native';
import { useRouter } from 'expo-router';
import Toast from 'react-native-toast-message';
import RealMap, { ZonePolygonProp } from '@/components/RealMap';
import { ConnectionStatusBadge } from '@/components/ConnectionStatusBadge';
import { zoneApi, geofenceApi } from '@/lib/api';
import { useLocationStore } from '@/store/locationStore';
import { useGeofenceStore } from '@/store/geofenceStore';
import { locationTrackingService } from '@/lib/location/trackingService';
import type { ZoneMapItem } from '@/types';

export default function TouristMap() {
  const router = useRouter();
  const [zones, setZones] = useState<ZoneMapItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<ZoneMapItem | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  // Real GPS Location Store
  const {
    currentLocation,
    trackingStatus,
    qualityMetrics,
  } = useLocationStore();

  // Real Geofence Store
  const {
    activeZones,
    highestRiskLevel,
    isStale,
  } = useGeofenceStore();

  const fetchZones = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [response, geoRes] = await Promise.all([
        zoneApi.getAll(),
        geofenceApi.getMyCurrentZones().catch(() => null),
      ]);
      const loadedZones = response.data?.zones || [];
      setZones(loadedZones);
      if (loadedZones.length > 0) {
        setSelectedZone(loadedZones[0]);
      }
      if (geoRes?.data) {
        useGeofenceStore.getState().setSnapshot(geoRes.data);
      }
    } catch (err: any) {
      console.error('Failed to fetch zones for tourist map:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to load safety zones. Please retry.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchZones();
    // One-shot GPS fix on mount if idle
    if (trackingStatus === 'idle') {
      locationTrackingService.getCurrentLocation().catch(() => {
        // user may grant permission via explicit start button
      });
    }
  }, [fetchZones, trackingStatus]);

  // Tracking Action Handlers
  const handleStartTracking = async () => {
    setActionLoading(true);
    try {
      await locationTrackingService.startForegroundLocationTracking();
      Toast.show({
        type: 'success',
        text1: 'GPS Tracking Active',
        text2: 'Transmitting real device location to TourSafe pipeline (~1 Hz).',
      });
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'GPS Tracking Failed',
        text2: err?.message || 'Please enable device location permissions.',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handlePauseTracking = () => {
    locationTrackingService.pauseTracking();
    Toast.show({
      type: 'info',
      text1: 'Tracking Paused',
      text2: 'GPS fix acquisition temporarily paused.',
    });
  };

  const handleResumeTracking = () => {
    locationTrackingService.resumeTracking();
    Toast.show({
      type: 'success',
      text1: 'Tracking Resumed',
      text2: 'Live GPS transmission active.',
    });
  };

  const handleStopTracking = async () => {
    setActionLoading(true);
    try {
      await locationTrackingService.stopForegroundLocationTracking();
      Toast.show({
        type: 'info',
        text1: 'Tracking Stopped',
        text2: 'GPS subscription cleanly closed.',
      });
    } catch (err: any) {
      console.error('Failed to stop tracking:', err);
    } finally {
      setActionLoading(false);
    }
  };

  // Convert GeoJSON polygons to RealMap polygon props
  const mapPolygons: ZonePolygonProp[] = zones
    .filter((z) => z.geometry && z.geometry.coordinates)
    .map((z) => {
      const coords: Array<{ latitude: number; longitude: number }> = [];
      if (z.geometry.type === 'Polygon') {
        const outerRing = z.geometry.coordinates[0] || [];
        outerRing.forEach(([lon, lat]) => {
          coords.push({ latitude: lat, longitude: lon });
        });
      }
      return {
        coordinates: coords,
        name: z.name,
        risk_level: z.risk_level,
      };
    })
    .filter((p) => p.coordinates.length > 2);

  // Markers from zone centers + real device GPS location marker
  const mapMarkers = zones
    .filter((z) => z.center && z.center.coordinates)
    .map((z) => {
      const [lon, lat] = z.center.coordinates;
      const color =
        z.risk_level === 'critical' || z.risk_level === 'high'
          ? '#ef4444'
          : z.risk_level === 'medium'
          ? '#f59e0b'
          : '#10b981';
      return {
        latitude: lat,
        longitude: lon,
        title: `${z.name} (${z.type.toUpperCase()})`,
        color,
      };
    });

  // Attach real physical device location marker
  if (currentLocation) {
    mapMarkers.push({
      latitude: currentLocation.latitude,
      longitude: currentLocation.longitude,
      title: `📍 My Physical Location (${qualityMetrics.qualityState.toUpperCase()})`,
      color: '#2563eb', // Blue marker for tourist device
    });
  }

  // Priority center: current GPS position, then selected zone, then default region
  const defaultCenter = currentLocation
    ? {
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
        latitudeDelta: 0.05,
        longitudeDelta: 0.05,
      }
    : zones.length > 0 && zones[0].center?.coordinates
    ? {
        latitude: zones[0].center.coordinates[1],
        longitude: zones[0].center.coordinates[0],
        latitudeDelta: 0.08,
        longitudeDelta: 0.08,
      }
    : { latitude: 10.2381, longitude: 77.4892, latitudeDelta: 0.08, longitudeDelta: 0.08 };

  const getQualityBadgeColor = () => {
    switch (qualityMetrics.qualityState) {
      case 'excellent':
        return '#10b981';
      case 'good':
        return '#0d9488';
      case 'degraded':
        return '#f59e0b';
      case 'poor':
      case 'stale':
        return '#ef4444';
      default:
        return '#64748b';
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>Real GPS Location Tracking</Text>
            <Text style={styles.title}>
              {selectedZone ? selectedZone.name : 'TourSafe Live Map'}
            </Text>
            <Text style={styles.subtitle}>
              Physical device location tracking at ~1 Hz connected to Redis live state.
            </Text>
          </View>
          <View style={{ alignItems: 'flex-end', gap: 8 }}>
            <ConnectionStatusBadge />
            <TouchableOpacity onPress={() => router.push('/tourist/(tabs)/sos')} style={styles.sosButton}>
              <ShieldAlert size={18} color="#fff" />
              <Text style={styles.sosText}>SOS</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* GPS Tracking Controls Panel */}
        <View style={styles.controlPanel}>
          <View style={styles.controlHeader}>
            <View style={styles.controlStatusRow}>
              <View
                style={[
                  styles.statusIndicator,
                  {
                    backgroundColor:
                      trackingStatus === 'active'
                        ? '#22c55e'
                        : trackingStatus === 'paused'
                        ? '#f59e0b'
                        : '#94a3b8',
                  },
                ]}
              />
              <Text style={styles.controlStatusText}>
                TRACKING: {trackingStatus.toUpperCase()}
              </Text>
            </View>

            <View style={styles.qualityChip}>
              <Gauge size={12} color={getQualityBadgeColor()} />
              <Text style={[styles.qualityText, { color: getQualityBadgeColor() }]}>
                {qualityMetrics.qualityState.toUpperCase()} GPS
              </Text>
            </View>
          </View>

          {/* Action Buttons */}
          <View style={styles.btnRow}>
            {trackingStatus === 'idle' || trackingStatus === 'stopped' || trackingStatus === 'error' ? (
              <TouchableOpacity
                onPress={handleStartTracking}
                disabled={actionLoading}
                style={[styles.actionBtn, styles.startBtn]}
              >
                <Play size={16} color="#fff" />
                <Text style={styles.btnText}>Start GPS Tracking</Text>
              </TouchableOpacity>
            ) : trackingStatus === 'active' ? (
              <>
                <TouchableOpacity
                  onPress={handlePauseTracking}
                  style={[styles.actionBtn, styles.pauseBtn]}
                >
                  <Pause size={16} color="#1a365d" />
                  <Text style={[styles.btnText, { color: '#1a365d' }]}>Pause</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleStopTracking}
                  disabled={actionLoading}
                  style={[styles.actionBtn, styles.stopBtn]}
                >
                  <Square size={16} color="#fff" />
                  <Text style={styles.btnText}>Stop Tracking</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <TouchableOpacity
                  onPress={handleResumeTracking}
                  style={[styles.actionBtn, styles.resumeBtn]}
                >
                  <Play size={16} color="#fff" />
                  <Text style={styles.btnText}>Resume</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleStopTracking}
                  disabled={actionLoading}
                  style={[styles.actionBtn, styles.stopBtn]}
                >
                  <Square size={16} color="#fff" />
                  <Text style={styles.btnText}>Stop</Text>
                </TouchableOpacity>
              </>
            )}
          </View>

          {/* Live Telemetry Summary */}
          {currentLocation && (
            <View style={styles.telemetryGrid}>
              <View style={styles.telemetryItem}>
                <Text style={styles.telemetryLabel}>Coordinates</Text>
                <Text style={styles.telemetryValue}>
                  {currentLocation.latitude.toFixed(4)}°, {currentLocation.longitude.toFixed(4)}°
                </Text>
              </View>
              <View style={styles.telemetryItem}>
                <Text style={styles.telemetryLabel}>Accuracy</Text>
                <Text style={styles.telemetryValue}>
                  {currentLocation.accuracy ? `±${currentLocation.accuracy.toFixed(1)}m` : 'N/A'}
                </Text>
              </View>
              <View style={styles.telemetryItem}>
                <Text style={styles.telemetryLabel}>Rate</Text>
                <Text style={styles.telemetryValue}>
                  {qualityMetrics.observedFrequencyHz > 0 ? `${qualityMetrics.observedFrequencyHz} Hz` : '~1 Hz'}
                </Text>
              </View>
            </View>
          )}
        </View>

        {/* Active Geofence Zone Membership Banner */}
        {activeZones.length > 0 && (
          <View style={[
            styles.geofenceBanner,
            highestRiskLevel === 'critical' ? styles.geofenceCritical : highestRiskLevel === 'high' ? styles.geofenceHigh : styles.geofenceSafe
          ]}>
            <View style={styles.geofenceHeader}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={16} color="#fff" />
                <Text style={styles.geofenceTitle}>Active Zone: {activeZones[0].name}</Text>
              </View>
              <View style={styles.geofenceRiskBadge}>
                <Text style={styles.geofenceRiskText}>{activeZones[0].risk_level.toUpperCase()}</Text>
              </View>
            </View>
            <Text style={styles.geofenceSubtext}>
              Dwell: {Math.floor(activeZones[0].dwell_duration_seconds / 60)}m {Math.floor(activeZones[0].dwell_duration_seconds % 60)}s | Boundary: {activeZones[0].distance_to_boundary_meters?.toFixed(0)}m {isStale ? ' (Stale GPS)' : ''}
            </Text>
          </View>
        )}

        <View style={styles.mapFrame}>
          <View style={styles.mapHeader}>
            <View style={styles.mapChip}>
              <Radio size={14} color="#2563eb" />
              <Text style={styles.mapChipText}>
                {currentLocation ? 'Live Device GPS Active' : 'Waiting for GPS Fix'}
              </Text>
            </View>
            <View style={styles.mapChip}>
              <ShieldCheck size={14} color="#1a365d" />
              <Text style={styles.mapChipText}>{zones.length} Active Zones</Text>
            </View>
            <View style={styles.mapChip}>
              <Layers3 size={14} color="#475569" />
              <Text style={styles.mapChipText}>
                {Platform.OS === 'web' ? 'OpenStreetMap' : 'Native Map'}
              </Text>
            </View>
          </View>

          {loading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color="#1a365d" />
              <Text style={styles.loadingText}>Loading real geospatial zones...</Text>
            </View>
          ) : error ? (
            <View style={styles.errorBox}>
              <AlertCircle size={28} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
              <TouchableOpacity onPress={fetchZones} style={styles.retryButton}>
                <RefreshCw size={14} color="#fff" />
                <Text style={styles.retryButtonText}>Retry Loading</Text>
              </TouchableOpacity>
            </View>
          ) : zones.length === 0 ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>No active safety zones published at this moment.</Text>
            </View>
          ) : (
            <RealMap
              region={defaultCenter}
              polygons={mapPolygons}
              markers={mapMarkers}
              overlayTitle={
                currentLocation
                  ? `Live GPS: ${currentLocation.latitude.toFixed(4)}°N, ${currentLocation.longitude.toFixed(4)}°E`
                  : selectedZone?.name || 'TourSafe Verified Zones'
              }
              overlayText={
                currentLocation
                  ? `Physical device GPS sample #${currentLocation.sequence_number} | Accuracy: ±${currentLocation.accuracy?.toFixed(1) || '0'}m`
                  : selectedZone?.description || 'Verified GeoJSON safety boundaries for Tamil Nadu.'
              }
            />
          )}
        </View>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>Active Safety Zones ({zones.length})</Text>
          <TouchableOpacity onPress={fetchZones} style={styles.refreshIconBtn}>
            <RefreshCw size={14} color="#1a365d" />
          </TouchableOpacity>
        </View>

        {zones.map((zone) => {
          const isSelected = selectedZone?.zone_id === zone.zone_id;
          return (
            <TouchableOpacity
              key={zone.zone_id}
              onPress={() => setSelectedZone(zone)}
              style={[styles.placeRow, isSelected && styles.placeRowSelected]}
            >
              <View
                style={[
                  styles.placeBadge,
                  (zone.risk_level === 'critical' || zone.risk_level === 'high' || zone.type === 'restricted' || zone.type === 'danger') &&
                    styles.dangerBadge,
                  (zone.risk_level === 'medium' || zone.type === 'warning') && styles.warningBadge,
                  (zone.risk_level === 'low' || zone.type === 'safe') && styles.safeBadge,
                ]}
              >
                <MapPin
                  size={14}
                  color={
                    zone.risk_level === 'critical' || zone.risk_level === 'high' || zone.type === 'restricted' || zone.type === 'danger'
                      ? '#fff'
                      : '#1a365d'
                  }
                />
              </View>
              <View style={styles.placeBody}>
                <Text style={styles.placeName}>{zone.name}</Text>
                <Text style={styles.placeMeta}>
                  {zone.center ? `${zone.center.coordinates[1].toFixed(4)}° N, ${zone.center.coordinates[0].toFixed(4)}° E` : ''}
                </Text>
                {zone.description ? <Text style={styles.placeDesc} numberOfLines={2}>{zone.description}</Text> : null}
              </View>
              <View style={styles.typeBadge}>
                <Text style={styles.placeType}>{zone.type.toUpperCase()}</Text>
                <Text style={styles.riskSubtype}>{zone.risk_level.toUpperCase()} RISK</Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 16 },
  hero: { backgroundColor: '#1a365d', borderRadius: 20, padding: 16 },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  kicker: { color: 'rgba(255,255,255,0.6)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 },
  title: { color: '#fff', fontSize: 22, fontWeight: '800', marginTop: 4 },
  subtitle: { color: 'rgba(255,255,255,0.72)', marginTop: 6, lineHeight: 20 },
  sosButton: {
    backgroundColor: '#ef4444',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sosText: { color: '#fff', fontWeight: '700' },
  controlPanel: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 16,
    padding: 12,
    marginTop: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
  },
  controlHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  controlStatusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusIndicator: { width: 8, height: 8, borderRadius: 4 },
  controlStatusText: { color: '#fff', fontSize: 12, fontWeight: '800', letterSpacing: 0.5 },
  qualityChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  qualityText: { fontSize: 11, fontWeight: '700' },
  btnRow: { flexDirection: 'row', gap: 8 },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 10,
    borderRadius: 10,
  },
  startBtn: { backgroundColor: '#10b981' },
  pauseBtn: { backgroundColor: '#fef08a' },
  resumeBtn: { backgroundColor: '#3b82f6' },
  stopBtn: { backgroundColor: '#ef4444' },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  telemetryGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    borderRadius: 10,
    padding: 10,
    marginTop: 10,
  },
  telemetryItem: { alignItems: 'center' },
  telemetryLabel: { color: 'rgba(255, 255, 255, 0.6)', fontSize: 10, textTransform: 'uppercase' },
  telemetryValue: { color: '#fff', fontSize: 12, fontWeight: '700', marginTop: 2 },
  mapFrame: { marginTop: 16, backgroundColor: '#fff', borderRadius: 18, padding: 12 },
  mapHeader: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  mapChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#eff6ff',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  mapChipText: { fontSize: 11, color: '#1a365d', fontWeight: '600' },
  loadingBox: { height: 320, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc', borderRadius: 14 },
  loadingText: { marginTop: 12, color: '#64748b', fontSize: 13, fontWeight: '600' },
  errorBox: { height: 320, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fef2f2', borderRadius: 14, padding: 20 },
  errorText: { color: '#b91c1c', textAlign: 'center', marginTop: 10, marginBottom: 16, fontSize: 13 },
  retryButton: {
    backgroundColor: '#1a365d',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  retryButtonText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  emptyBox: { height: 320, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc', borderRadius: 14, padding: 20 },
  emptyText: { color: '#64748b', textAlign: 'center', fontSize: 14 },
  section: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  sectionHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d' },
  refreshIconBtn: { padding: 6, backgroundColor: '#f1f5f9', borderRadius: 8 },
  placeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eef2f7',
  },
  placeRowSelected: {
    backgroundColor: '#eff6ff',
    borderRadius: 12,
    paddingHorizontal: 8,
    marginHorizontal: -8,
  },
  placeBadge: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#e2e8f0',
  },
  dangerBadge: { backgroundColor: '#ef4444' },
  warningBadge: { backgroundColor: '#f59e0b' },
  safeBadge: { backgroundColor: '#10b981' },
  placeBody: { flex: 1 },
  placeName: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  placeMeta: { fontSize: 11, color: 'rgba(100,116,139,0.75)', marginTop: 2 },
  placeDesc: { fontSize: 12, color: '#475569', marginTop: 4, lineHeight: 16 },
  typeBadge: { alignItems: 'flex-end', gap: 2 },
  placeType: { fontSize: 11, fontWeight: '800', color: '#1a365d' },
  riskSubtype: { fontSize: 9, fontWeight: '700', color: '#64748b' },
  geofenceBanner: {
    padding: 14,
    borderRadius: 14,
    marginBottom: 14,
  },
  geofenceSafe: {
    backgroundColor: '#065f46',
  },
  geofenceHigh: {
    backgroundColor: '#9a3412',
  },
  geofenceCritical: {
    backgroundColor: '#991b1b',
  },
  geofenceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  geofenceTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  geofenceRiskBadge: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  geofenceRiskText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#ffffff',
  },
  geofenceSubtext: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.85)',
  },
});

