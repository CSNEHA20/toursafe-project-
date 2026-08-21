import React, { useState, useEffect, useCallback } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  Platform,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import {
  MapPinned,
  Shield,
  TriangleAlert,
  Layers3,
  RefreshCw,
  AlertOctagon,
  ShieldCheck,
} from 'lucide-react-native';
import RealMap, { ZonePolygonProp } from '@/components/RealMap';
import { zoneApi } from '@/lib/api';
import type { ZoneMapItem } from '@/types';

export default function AdminMap() {
  const [zones, setZones] = useState<ZoneMapItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchZones = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await zoneApi.getAll();
      setZones(response.data?.zones || []);
    } catch (err: any) {
      console.error('Failed to fetch zones for admin map:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to load zones');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchZones();
  }, [fetchZones]);

  // Convert GeoJSON polygons to RealMap polygons
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
        name: `${z.name} (${z.risk_level.toUpperCase()})`,
        risk_level: z.risk_level,
      };
    })
    .filter((p) => p.coordinates.length > 2);

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
        title: `${z.name} [${z.type}]`,
        color,
      };
    });

  const baseRegion =
    zones.length > 0 && zones[0].center?.coordinates
      ? {
          latitude: zones[0].center.coordinates[1],
          longitude: zones[0].center.coordinates[0],
          latitudeDelta: 0.18,
          longitudeDelta: 0.18,
        }
      : { latitude: 10.22, longitude: 77.48, latitudeDelta: 0.18, longitudeDelta: 0.18 };

  const safeCount = zones.filter((z) => z.type === 'safe').length;
  const warningCount = zones.filter((z) => z.type === 'warning').length;
  const restrictedCount = zones.filter((z) => z.type === 'restricted' || z.type === 'danger').length;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <View>
            <Text style={styles.title}>Live Command Map</Text>
            <Text style={styles.subtitle}>Geospatial zone boundaries from MongoDB 2dsphere index</Text>
          </View>
          <TouchableOpacity onPress={fetchZones} style={styles.refreshBtn}>
            <RefreshCw size={16} color="#1a365d" />
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.kpiRow}>
        <MiniStat
          icon={<ShieldCheck size={16} color="#10b981" />}
          label="Safe Zones"
          value={String(safeCount)}
        />
        <MiniStat
          icon={<TriangleAlert size={16} color="#f59e0b" />}
          label="Warning Zones"
          value={String(warningCount)}
        />
        <MiniStat
          icon={<AlertOctagon size={16} color="#ef4444" />}
          label="Restricted"
          value={String(restrictedCount)}
        />
        <MiniStat
          icon={<Layers3 size={16} color="#475569" />}
          label="Map Mode"
          value={Platform.OS === 'web' ? 'OpenStreetMap' : 'Native'}
        />
      </View>

      <View style={styles.mapCard}>
        <View style={styles.mapTopRow}>
          <View style={styles.mapPill}>
            <MapPinned size={14} color="#0f172a" />
            <Text style={styles.mapPillText}>Operator View</Text>
          </View>
          <Text style={styles.mapNote}>{zones.length} active GeoJSON polygons rendered</Text>
        </View>

        {loading ? (
          <View style={styles.loadingFrame}>
            <ActivityIndicator size="large" color="#fff" />
            <Text style={styles.loadingFrameText}>Loading authoritative geospatial zones...</Text>
          </View>
        ) : error ? (
          <View style={styles.errorFrame}>
            <Text style={styles.errorFrameText}>{error}</Text>
            <TouchableOpacity onPress={fetchZones} style={styles.retryFrameBtn}>
              <Text style={styles.retryFrameBtnText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <RealMap
            region={baseRegion}
            polygons={mapPolygons}
            markers={mapMarkers}
            overlayTitle="TourSafe Live Command Geospatial Layer"
            overlayText="Authoritative GeoJSON safety polygons rendered on OpenStreetMap with risk-level color codes."
          />
        )}
      </View>

      <View style={styles.listCard}>
        <Text style={styles.listTitle}>Live Zone Registry ({zones.length})</Text>
        {zones.map((zone) => (
          <View key={zone.zone_id} style={styles.row}>
            <MapPinned
              size={16}
              color={
                zone.risk_level === 'critical' || zone.risk_level === 'high'
                  ? '#ef4444'
                  : zone.risk_level === 'medium'
                  ? '#f59e0b'
                  : '#10b981'
              }
            />
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{zone.name}</Text>
              <Text style={styles.rowMeta}>
                {zone.type.toUpperCase()} · {zone.risk_level.toUpperCase()} RISK ·{' '}
                {zone.center ? `${zone.center.coordinates[1].toFixed(3)}°N, ${zone.center.coordinates[0].toFixed(3)}°E` : ''}
              </Text>
            </View>
            <View style={[styles.statusBadge, zone.status === 'active' ? styles.statusActive : styles.statusInactive]}>
              <Text style={styles.statusText}>{zone.status.toUpperCase()}</Text>
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function MiniStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <View style={styles.kpi}>
      {icon}
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={styles.kpiValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 4, color: 'rgba(100,116,139,0.75)', lineHeight: 18, fontSize: 13 },
  refreshBtn: { padding: 8, backgroundColor: '#fff', borderRadius: 10, borderWidth: 1, borderColor: '#e2e8f0' },
  kpiRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  kpi: {
    flex: 1,
    minWidth: '22%',
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 4,
  },
  kpiLabel: {
    fontSize: 10,
    textTransform: 'uppercase',
    color: 'rgba(100,116,139,0.7)',
    fontWeight: '700',
  },
  kpiValue: { fontSize: 16, fontWeight: '800', color: '#0f172a' },
  mapCard: { backgroundColor: '#1a365d', borderRadius: 20, padding: 12 },
  mapTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  mapPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#fff',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  mapPillText: { fontSize: 11, color: '#0f172a', fontWeight: '700' },
  mapNote: { fontSize: 11, color: 'rgba(255,255,255,0.75)' },
  loadingFrame: { height: 320, alignItems: 'center', justifyContent: 'center' },
  loadingFrameText: { marginTop: 10, color: '#fff', fontSize: 13 },
  errorFrame: { height: 320, alignItems: 'center', justifyContent: 'center', padding: 20 },
  errorFrameText: { color: '#fca5a5', textAlign: 'center', marginBottom: 12 },
  retryFrameBtn: { backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 8 },
  retryFrameBtnText: { color: '#1a365d', fontWeight: '700' },
  listCard: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  listTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#eef2f7',
  },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowMeta: { marginTop: 3, fontSize: 11, color: 'rgba(100,116,139,0.8)' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  statusActive: { backgroundColor: '#dcfce7' },
  statusInactive: { backgroundColor: '#f1f5f9' },
  statusText: { fontSize: 10, fontWeight: '800', color: '#166534' },
});
