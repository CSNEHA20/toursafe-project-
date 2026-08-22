import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { MapPin, Navigation, ShieldCheck, AlertTriangle, RefreshCw, Compass } from 'lucide-react-native';
import { analyticsApi } from '@/lib/api';

interface TouristTrip {
  trip_id: string;
  title: string;
  status: string;
  started_at?: string;
  ended_at?: string;
  distance_km: number;
  zones_visited_count: number;
  zones_visited_names: string[];
  total_dwell_seconds: number;
  gps_accuracy_avg_meters?: number;
  safety_events_count: number;
  incidents_count: number;
  sos_count: number;
  tracking_gaps_count: number;
}

interface TouristAnalyticsData {
  tourist_id: string;
  total_trips: number;
  completed_trips: number;
  total_distance_km: number;
  total_duration_hours: number;
  unique_zones_visited: number;
  trips: TouristTrip[];
}

export default function TouristTripAnalytics() {
  const [data, setData] = useState<TouristAnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await analyticsApi.getMyStats();
      setData(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Unable to load trip analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color="#0d9488" />
        <Text style={styles.loadingText}>Loading your travel insights...</Text>
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.errorContainer}>
        <AlertTriangle size={20} color="#b45309" />
        <Text style={styles.errorText}>{error || 'No analytics data available'}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={fetchStats}>
          <RefreshCw size={14} color="#0d9488" />
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.title}>My Travel & Safety Summary</Text>
          <Text style={styles.subtitle}>Authoritative personal telemetry & route insights</Text>
        </View>
        <TouchableOpacity style={styles.refreshIconBtn} onPress={fetchStats}>
          <RefreshCw size={16} color="#64748b" />
        </TouchableOpacity>
      </View>

      {/* KPI Cards */}
      <View style={styles.kpiGrid}>
        <View style={styles.kpiCard}>
          <Navigation size={18} color="#0d9488" />
          <Text style={styles.kpiLabel}>Total Distance</Text>
          <Text style={styles.kpiValue}>{data.total_distance_km} km</Text>
        </View>
        <View style={styles.kpiCard}>
          <Compass size={18} color="#2563eb" />
          <Text style={styles.kpiLabel}>Trips Recorded</Text>
          <Text style={styles.kpiValue}>{data.total_trips}</Text>
        </View>
        <View style={styles.kpiCard}>
          <MapPin size={18} color="#7c3aed" />
          <Text style={styles.kpiLabel}>Zones Visited</Text>
          <Text style={styles.kpiValue}>{data.unique_zones_visited}</Text>
        </View>
        <View style={styles.kpiCard}>
          <ShieldCheck size={18} color="#059669" />
          <Text style={styles.kpiLabel}>Safety Status</Text>
          <Text style={styles.kpiValue}>Protected</Text>
        </View>
      </View>

      {/* Trip List */}
      <Text style={styles.sectionHeading}>Trip History & Route Quality</Text>
      {data.trips.length === 0 ? (
        <View style={styles.emptyCard}>
          <Compass size={24} color="#94a3b8" />
          <Text style={styles.emptyTitle}>No Recorded Trips Yet</Text>
          <Text style={styles.emptyDesc}>Start your tracking session to record distances and safety zones.</Text>
        </View>
      ) : (
        data.trips.map((trip) => (
          <View key={trip.trip_id} style={styles.tripCard}>
            <View style={styles.tripHeader}>
              <Text style={styles.tripTitle}>{trip.title || 'Trip'}</Text>
              <View style={[styles.statusBadge, trip.status === 'completed' ? styles.statusBadgeCompleted : styles.statusBadgeActive]}>
                <Text style={[styles.statusText, trip.status === 'completed' ? styles.statusTextCompleted : styles.statusTextActive]}>
                  {trip.status.toUpperCase()}
                </Text>
              </View>
            </View>

            <View style={styles.tripStatsRow}>
              <View style={styles.tripStat}>
                <Text style={styles.tripStatLabel}>Distance</Text>
                <Text style={styles.tripStatVal}>{trip.distance_km} km</Text>
              </View>
              <View style={styles.tripStat}>
                <Text style={styles.tripStatLabel}>Zones</Text>
                <Text style={styles.tripStatVal}>{trip.zones_visited_count}</Text>
              </View>
              <View style={styles.tripStat}>
                <Text style={styles.tripStatLabel}>GPS Accuracy</Text>
                <Text style={styles.tripStatVal}>{trip.gps_accuracy_avg_meters ? `±${trip.gps_accuracy_avg_meters}m` : 'Normal'}</Text>
              </View>
              <View style={styles.tripStat}>
                <Text style={styles.tripStatLabel}>Safety Alerts</Text>
                <Text style={styles.tripStatVal}>{trip.safety_events_count}</Text>
              </View>
            </View>

            {trip.zones_visited_names.length > 0 && (
              <View style={styles.zoneBadgesRow}>
                {trip.zones_visited_names.map((name, idx) => (
                  <View key={idx} style={styles.zoneTag}>
                    <MapPin size={10} color="#0d9488" />
                    <Text style={styles.zoneTagText}>{name}</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 14,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  title: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0f172a',
  },
  subtitle: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  refreshIconBtn: {
    padding: 6,
    borderRadius: 8,
    backgroundColor: '#f8fafc',
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  kpiCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 4,
  },
  kpiLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748b',
    textTransform: 'uppercase',
  },
  kpiValue: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0f172a',
  },
  sectionHeading: {
    fontSize: 14,
    fontWeight: '700',
    color: '#334155',
    marginTop: 6,
  },
  tripCard: {
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 10,
  },
  tripHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tripTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0f172a',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  statusBadgeCompleted: {
    backgroundColor: '#dcfce7',
  },
  statusBadgeActive: {
    backgroundColor: '#ccfbf1',
  },
  statusText: {
    fontSize: 10,
    fontWeight: '800',
  },
  statusTextCompleted: {
    color: '#15803d',
  },
  statusTextActive: {
    color: '#0f766e',
  },
  tripStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    paddingTop: 8,
  },
  tripStat: {
    alignItems: 'center',
  },
  tripStatLabel: {
    fontSize: 10,
    color: '#64748b',
  },
  tripStatVal: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
    marginTop: 2,
  },
  zoneBadgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  zoneTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#e0f2fe',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  zoneTagText: {
    fontSize: 10,
    color: '#0369a1',
    fontWeight: '600',
  },
  loadingContainer: {
    padding: 24,
    alignItems: 'center',
    gap: 8,
  },
  loadingText: {
    fontSize: 12,
    color: '#64748b',
  },
  errorContainer: {
    padding: 16,
    backgroundColor: '#fffbeb',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#fef3c7',
    alignItems: 'center',
    gap: 8,
  },
  errorText: {
    fontSize: 12,
    color: '#b45309',
    textAlign: 'center',
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#ffffff',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  retryText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0d9488',
  },
  emptyCard: {
    padding: 20,
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#475569',
  },
  emptyDesc: {
    fontSize: 12,
    color: '#94a3b8',
    textAlign: 'center',
  },
});
