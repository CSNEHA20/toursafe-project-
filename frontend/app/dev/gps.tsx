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
  Radio,
  MapPin,
  Play,
  Pause,
  Square,
  ArrowLeft,
} from 'lucide-react-native';
import { useRouter } from 'expo-router';
import Toast from 'react-native-toast-message';
import { useLocationStore } from '@/store/locationStore';
import { locationTrackingService } from '@/lib/location/trackingService';
import { locationPermissionService } from '@/lib/location/permissionService';
import { realtimeClient } from '@/lib/realtimeClient';

export default function GPSDiagnosticsScreen() {
  const router = useRouter();
  const [oneshotLoading, setOneshotLoading] = useState(false);

  const {
    permissionState,
    trackingStatus,
    activeSession,
    currentLocation,
    qualityMetrics,
    recentSamples,
    lastTransmittedSequence,
    lastServerError,
    isBackgroundTracking,
  } = useLocationStore();

  const [realtimeState, setRealtimeState] = useState(realtimeClient.getConnectionState());

  useEffect(() => {
    locationPermissionService.checkPermissions().then(({ foreground }) => {
      useLocationStore.getState().setPermissionState(foreground);
    });

    const unsub = realtimeClient.onStateChange((s) => setRealtimeState(s));
    return () => unsub();
  }, []);

  const handleStartTracking = async () => {
    try {
      await locationTrackingService.startForegroundLocationTracking();
      Toast.show({ type: 'success', text1: 'GPS Tracking Started' });
    } catch (err: any) {
      Toast.show({ type: 'error', text1: 'Start Failed', text2: err?.message });
    }
  };

  const handlePauseTracking = () => {
    locationTrackingService.pauseTracking();
  };

  const handleResumeTracking = () => {
    locationTrackingService.resumeTracking();
  };

  const handleStopTracking = async () => {
    await locationTrackingService.stopForegroundLocationTracking();
    Toast.show({ type: 'info', text1: 'GPS Tracking Stopped' });
  };

  const handleOneShot = async () => {
    setOneshotLoading(true);
    try {
      const fix = await locationTrackingService.getCurrentLocation();
      if (fix) {
        Toast.show({
          type: 'success',
          text1: 'GPS Fix Acquired',
          text2: `${fix.latitude.toFixed(5)}°, ${fix.longitude.toFixed(5)}°`,
        });
      }
    } catch (err: any) {
      Toast.show({ type: 'error', text1: 'GPS Fix Failed', text2: err?.message });
    } finally {
      setOneshotLoading(false);
    }
  };

  const getQualityColor = () => {
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
        return '#94a3b8';
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <ArrowLeft size={18} color="#fff" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>GPS Diagnostics</Text>
          <Text style={styles.subtitle}>Physical sensor telemetry & pipeline validation</Text>
        </View>
      </View>

      {/* Control Strip */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Tracking Lifecycle Controls</Text>
        <View style={styles.btnRow}>
          {trackingStatus === 'idle' || trackingStatus === 'stopped' || trackingStatus === 'error' ? (
            <TouchableOpacity onPress={handleStartTracking} style={[styles.btn, styles.startBtn]}>
              <Play size={16} color="#fff" />
              <Text style={styles.btnText}>Start 1Hz Tracking</Text>
            </TouchableOpacity>
          ) : trackingStatus === 'active' ? (
            <>
              <TouchableOpacity onPress={handlePauseTracking} style={[styles.btn, styles.pauseBtn]}>
                <Pause size={16} color="#1a365d" />
                <Text style={[styles.btnText, { color: '#1a365d' }]}>Pause</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleStopTracking} style={[styles.btn, styles.stopBtn]}>
                <Square size={16} color="#fff" />
                <Text style={styles.btnText}>Stop Tracking</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <TouchableOpacity onPress={handleResumeTracking} style={[styles.btn, styles.resumeBtn]}>
                <Play size={16} color="#fff" />
                <Text style={styles.btnText}>Resume</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleStopTracking} style={[styles.btn, styles.stopBtn]}>
                <Square size={16} color="#fff" />
                <Text style={styles.btnText}>Stop Tracking</Text>
              </TouchableOpacity>
            </>
          )}

          <TouchableOpacity
            onPress={handleOneShot}
            disabled={oneshotLoading}
            style={[styles.btn, styles.secondaryBtn]}
          >
            {oneshotLoading ? (
              <ActivityIndicator size="small" color="#1a365d" />
            ) : (
              <>
                <MapPin size={16} color="#1a365d" />
                <Text style={[styles.btnText, { color: '#1a365d' }]}>One-Shot Fix</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>

      {/* System Status KPI Grid */}
      <View style={styles.grid}>
        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Tracking Status</Text>
          <Text
            style={[
              styles.kpiValue,
              {
                color:
                  trackingStatus === 'active'
                    ? '#10b981'
                    : trackingStatus === 'paused'
                    ? '#f59e0b'
                    : '#64748b',
              },
            ]}
          >
            {trackingStatus.toUpperCase()}
          </Text>
        </View>

        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Permission State</Text>
          <Text
            style={[
              styles.kpiValue,
              { color: permissionState === 'granted' ? '#10b981' : '#ef4444' },
            ]}
          >
            {permissionState.toUpperCase()}
          </Text>
        </View>

        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Quality State</Text>
          <Text style={[styles.kpiValue, { color: getQualityColor() }]}>
            {qualityMetrics.qualityState.toUpperCase()}
          </Text>
        </View>

        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Realtime WS</Text>
          <Text
            style={[
              styles.kpiValue,
              { color: realtimeState === 'connected' ? '#10b981' : '#f59e0b' },
            ]}
          >
            {realtimeState.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* Real-time Telemetry Metrics */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Live GPS Telemetry</Text>
        {currentLocation ? (
          <View style={styles.metaTable}>
            <Row label="Latitude" value={`${currentLocation.latitude.toFixed(7)}°`} />
            <Row label="Longitude" value={`${currentLocation.longitude.toFixed(7)}°`} />
            <Row
              label="Horizontal Accuracy"
              value={currentLocation.accuracy ? `±${currentLocation.accuracy.toFixed(2)} m` : 'N/A'}
            />
            <Row
              label="Altitude"
              value={currentLocation.altitude ? `${currentLocation.altitude.toFixed(1)} m` : 'N/A'}
            />
            <Row
              label="Speed"
              value={currentLocation.speed ? `${currentLocation.speed.toFixed(2)} m/s` : '0 m/s'}
            />
            <Row
              label="Heading"
              value={currentLocation.heading ? `${currentLocation.heading.toFixed(1)}°` : 'N/A'}
            />
            <Row label="Sequence Number" value={`#${currentLocation.sequence_number}`} />
            <Row label="Timestamp" value={currentLocation.timestamp} />
            <Row label="Provider" value={currentLocation.provider || 'gps'} />
            <Row label="Background Task" value={isBackgroundTracking ? 'ACTIVE' : 'INACTIVE'} />
          </View>
        ) : (
          <View style={styles.emptyBox}>
            <Radio size={32} color="#94a3b8" />
            <Text style={styles.emptyText}>No live GPS samples received yet.</Text>
          </View>
        )}
      </View>

      {/* Sampling Frequency & Interval Analysis */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Sampling Frequency & Jitter Analysis</Text>
        <View style={styles.metaTable}>
          <Row label="Total Samples Received" value={String(qualityMetrics.sampleCount)} />
          <Row
            label="Observed Update Frequency"
            value={`${qualityMetrics.observedFrequencyHz} Hz (Target: 1.00 Hz)`}
          />
          <Row label="Average Interval" value={`${qualityMetrics.averageIntervalMs} ms`} />
          <Row label="Min Interval" value={`${qualityMetrics.minIntervalMs} ms`} />
          <Row label="Max Interval" value={`${qualityMetrics.maxIntervalMs} ms`} />
          <Row label="Stale Duration" value={`${qualityMetrics.staleDurationSeconds} s`} />
          <Row label="Last Transmitted Seq" value={`#${lastTransmittedSequence}`} />
          <Row
            label="Last Server Error"
            value={lastServerError || 'None (Healthy)'}
            valueColor={lastServerError ? '#ef4444' : '#10b981'}
          />
        </View>
      </View>

      {/* Active Session Metadata */}
      {activeSession && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Active Tracking Session</Text>
          <View style={styles.metaTable}>
            <Row label="Session ID" value={activeSession.session_id} />
            <Row label="Tourist ID" value={activeSession.tourist_id} />
            <Row label="Started At" value={activeSession.started_at} />
            <Row label="Session Status" value={activeSession.status.toUpperCase()} />
            <Row label="Source" value={activeSession.source} />
          </View>
        </View>
      )}

      {/* Recent 5 Samples Breadcrumb Trail */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Recent GPS Samples Buffer ({recentSamples.length})</Text>
        {recentSamples.slice(-5).reverse().map((s) => (
          <View key={`${s.sequence_number}_${s.timestamp}`} style={styles.sampleRow}>
            <Radio size={14} color="#0d9488" />
            <View style={{ flex: 1 }}>
              <Text style={styles.sampleTitle}>
                Seq #{s.sequence_number} · {s.latitude.toFixed(5)}°, {s.longitude.toFixed(5)}°
              </Text>
              <Text style={styles.sampleMeta}>
                Acc: ±{s.accuracy?.toFixed(1) || '0'}m · {new Date(s.timestamp).toLocaleTimeString()}
              </Text>
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function Row({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, valueColor ? { color: valueColor } : null]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  header: {
    backgroundColor: '#1a365d',
    borderRadius: 16,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  backBtn: {
    padding: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    borderRadius: 10,
  },
  title: { color: '#fff', fontSize: 20, fontWeight: '800' },
  subtitle: { color: 'rgba(255, 255, 255, 0.7)', fontSize: 12, marginTop: 2 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cardTitle: { fontSize: 15, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  btnRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  btn: {
    flex: 1,
    minWidth: '45%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 10,
  },
  startBtn: { backgroundColor: '#10b981' },
  pauseBtn: { backgroundColor: '#fef08a' },
  resumeBtn: { backgroundColor: '#3b82f6' },
  stopBtn: { backgroundColor: '#ef4444' },
  secondaryBtn: { backgroundColor: '#f1f5f9', borderWidth: 1, borderColor: '#cbd5e1' },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  grid: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  kpi: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  kpiLabel: { fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: '700' },
  kpiValue: { fontSize: 15, fontWeight: '800', marginTop: 4 },
  metaTable: { gap: 8 },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  rowLabel: { fontSize: 12, color: '#64748b', fontWeight: '600' },
  rowValue: { fontSize: 12, color: '#0f172a', fontWeight: '700' },
  emptyBox: { alignItems: 'center', justifyContent: 'center', padding: 24, gap: 8 },
  emptyText: { color: '#94a3b8', fontSize: 13 },
  sampleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  sampleTitle: { fontSize: 12, fontWeight: '700', color: '#0f172a' },
  sampleMeta: { fontSize: 10, color: '#64748b', marginTop: 2 },
});
