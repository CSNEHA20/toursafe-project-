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
  Navigation,
  ShieldAlert,
  Clock3,
  TriangleAlert,
  Layers3,
  RefreshCw,
  AlertCircle,
  ShieldCheck,
} from 'lucide-react-native';
import { useRouter } from 'expo-router';
import RealMap, { ZonePolygonProp } from '@/components/RealMap';
import { zoneApi } from '@/lib/api';
import type { ZoneMapItem } from '@/types';

export default function TouristMap() {
  const router = useRouter();
  const [zones, setZones] = useState<ZoneMapItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<ZoneMapItem | null>(null);

  const fetchZones = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await zoneApi.getAll();
      const loadedZones = response.data?.zones || [];
      setZones(loadedZones);
      if (loadedZones.length > 0) {
        setSelectedZone(loadedZones[0]);
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
  }, [fetchZones]);

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

  // Markers from zone centers
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

  const defaultCenter =
    zones.length > 0 && zones[0].center?.coordinates
      ? {
          latitude: zones[0].center.coordinates[1],
          longitude: zones[0].center.coordinates[0],
          latitudeDelta: 0.08,
          longitudeDelta: 0.08,
        }
      : { latitude: 10.2381, longitude: 77.4892, latitudeDelta: 0.08, longitudeDelta: 0.08 };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>Geospatial Safety</Text>
            <Text style={styles.title}>
              {selectedZone ? selectedZone.name : 'TourSafe Live Map'}
            </Text>
            <Text style={styles.subtitle}>
              Real-time safety zones and boundaries backed by MongoDB geospatial foundation.
            </Text>
          </View>
          <TouchableOpacity onPress={() => router.push('/tourist/(tabs)/sos')} style={styles.sosButton}>
            <ShieldAlert size={18} color="#fff" />
            <Text style={styles.sosText}>SOS</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.mapFrame}>
          <View style={styles.mapHeader}>
            <View style={styles.mapChip}>
              <Navigation size={14} color="#0d9488" />
              <Text style={styles.mapChipText}>GPS Ready</Text>
            </View>
            <View style={styles.mapChip}>
              <ShieldCheck size={14} color="#1a365d" />
              <Text style={styles.mapChipText}>{zones.length} Active Zones</Text>
            </View>
            <View style={styles.mapChip}>
              <Layers3 size={14} color="#475569" />
              <Text style={styles.mapChipText}>{Platform.OS === 'web' ? 'OpenStreetMap' : 'Native Map'}</Text>
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
              overlayTitle={selectedZone?.name || 'TourSafe Verified Zones'}
              overlayText={
                selectedZone?.description ||
                'Verified GeoJSON safety boundaries for Tamil Nadu & Nilgiris tourist corridors.'
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

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Corridor Advisory</Text>
        <View style={styles.alertCard}>
          <TriangleAlert size={18} color="#b45309" />
          <Text style={styles.alertText}>
            Restricted zones like Guna Caves & Berijam Lake require forest permits and strict adherence to marked boundaries. Always check zone alerts before traveling.
          </Text>
        </View>
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
  alertCard: {
    backgroundColor: '#fff7ed',
    borderRadius: 14,
    padding: 14,
    flexDirection: 'row',
    gap: 10,
    borderWidth: 1,
    borderColor: '#fed7aa',
  },
  alertText: { flex: 1, color: '#7c2d12', lineHeight: 20 },
});
