import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { router } from 'expo-router';
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  MapPin,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react-native';
import { useResponderStore } from '@/store/responderStore';
import type { ResponderHistoryItem } from '@/types';

export default function ResponderHistoryScreen() {
  const { history, historyTotal, historyLoading, loadHistory } = useResponderStore();
  const [filter, setFilter] = useState<'ALL' | 'COMPLETED' | 'CANCELLED' | 'REJECTED'>('ALL');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadHistory(50, 0);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadHistory(50, 0);
    setRefreshing(false);
  };

  const filteredHistory = history.filter((item) => {
    if (filter === 'ALL') return true;
    return item.status === filter;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return { label: 'COMPLETED', bg: '#064E3B', text: '#34D399', icon: CheckCircle2 };
      case 'CANCELLED':
        return { label: 'HANDOVER / CANCELLED', bg: '#78350F', text: '#FBBF24', icon: Clock };
      case 'REJECTED':
        return { label: 'REJECTED', bg: '#7F1D1D', text: '#F87171', icon: XCircle };
      default:
        return { label: status, bg: '#1E293B', text: '#94A3B8', icon: Clock };
    }
  };

  const renderItem = ({ item }: { item: ResponderHistoryItem }) => {
    const badge = getStatusBadge(item.status);
    const IconComponent = badge.icon;
    const inc = item.incident_summary;

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.incidentTag}>
            <ShieldAlert size={14} color="#60A5FA" />
            <Text style={styles.incidentIdText}>{item.incident_id}</Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: badge.bg }]}>
            <IconComponent size={12} color={badge.text} />
            <Text style={[styles.statusBadgeText, { color: badge.text }]}>{badge.label}</Text>
          </View>
        </View>

        {inc?.location_name || inc?.zone_name ? (
          <View style={styles.locationRow}>
            <MapPin size={13} color="#94A3B8" />
            <Text style={styles.locationText} numberOfLines={1}>
              {inc.location_name || inc.zone_name || 'Field Operations Zone'}
            </Text>
          </View>
        ) : null}

        <View style={styles.timelineRow}>
          <View style={styles.timelineCol}>
            <Text style={styles.timeLabel}>Assigned</Text>
            <Text style={styles.timeVal}>
              {item.assigned_at ? new Date(item.assigned_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
            </Text>
          </View>
          <View style={styles.timelineCol}>
            <Text style={styles.timeLabel}>Arrived</Text>
            <Text style={styles.timeVal}>
              {item.arrived_at ? new Date(item.arrived_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
            </Text>
          </View>
          <View style={styles.timelineCol}>
            <Text style={styles.timeLabel}>Closed</Text>
            <Text style={styles.timeVal}>
              {item.completed_at
                ? new Date(item.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : item.cancelled_at
                ? new Date(item.cancelled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : '—'}
            </Text>
          </View>
        </View>

        {item.completion_reason || item.cancellation_reason || item.rejection_reason ? (
          <View style={styles.outcomeBox}>
            <FileText size={13} color="#CBD5E1" />
            <Text style={styles.outcomeText} numberOfLines={2}>
              {item.completion_reason || item.cancellation_reason || item.rejection_reason}
            </Text>
          </View>
        ) : null}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <ArrowLeft size={20} color="#F8FAFC" />
        </TouchableOpacity>
        <View>
          <Text style={styles.headerTitle}>Mission History</Text>
          <Text style={styles.headerSubtitle}>{historyTotal} total logged assignments</Text>
        </View>
        <TouchableOpacity style={styles.refreshButton} onPress={handleRefresh}>
          <RefreshCw size={18} color="#94A3B8" />
        </TouchableOpacity>
      </View>

      {/* Filter Chips */}
      <View style={styles.filterRow}>
        {(['ALL', 'COMPLETED', 'CANCELLED', 'REJECTED'] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterChip, filter === f && styles.filterChipActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterChipText, filter === f && styles.filterChipTextActive]}>
              {f === 'CANCELLED' ? 'HANDOVER' : f}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* List */}
      {historyLoading && !refreshing ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3B82F6" />
          <Text style={styles.loadingText}>Loading mission logs...</Text>
        </View>
      ) : (
        <FlatList
          data={filteredHistory}
          keyExtractor={(item) => item.assignment_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor="#3B82F6" />}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Calendar size={48} color="#334155" />
              <Text style={styles.emptyTitle}>No Missions Found</Text>
              <Text style={styles.emptySubtitle}>Completed and logged assignments will appear here.</Text>
            </View>
          }
        />
      )}
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
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#1E293B',
  },
  filterChipActive: {
    backgroundColor: '#2563EB',
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#94A3B8',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  card: {
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  incidentTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#1E293B',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  incidentIdText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#93C5FD',
    fontFamily: 'monospace',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  locationText: {
    fontSize: 13,
    color: '#94A3B8',
    flex: 1,
  },
  timelineRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#0B1120',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  timelineCol: {
    alignItems: 'center',
  },
  timeLabel: {
    fontSize: 10,
    color: '#64748B',
    textTransform: 'uppercase',
    fontWeight: '600',
  },
  timeVal: {
    fontSize: 13,
    fontWeight: '700',
    color: '#E2E8F0',
    marginTop: 2,
  },
  outcomeBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#1E293B66',
    borderRadius: 6,
    padding: 8,
  },
  outcomeText: {
    fontSize: 12,
    color: '#CBD5E1',
    flex: 1,
    lineHeight: 16,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#64748B',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#94A3B8',
    marginTop: 12,
  },
  emptySubtitle: {
    fontSize: 13,
    color: '#475569',
    textAlign: 'center',
    marginTop: 4,
    paddingHorizontal: 32,
  },
});

