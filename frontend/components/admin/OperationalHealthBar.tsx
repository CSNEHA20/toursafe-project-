import React, { useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useReliabilityStore } from '../../store/reliabilityStore';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface Props {
  onOpenDetailedMetrics?: () => void;
}

export const OperationalHealthBar: React.FC<Props> = ({ onOpenDetailedMetrics }) => {
  const { systemMode, modeReason, fetchDegradation, goldenSignals, fetchMetrics } = useReliabilityStore();

  useEffect(() => {
    fetchDegradation();
    fetchMetrics();
    const interval = setInterval(() => {
      fetchDegradation();
      fetchMetrics();
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = () => {
    switch (systemMode) {
      case 'FULL':
        return '#10B981'; // Emerald
      case 'DEGRADED':
        return '#F59E0B'; // Amber
      case 'CRITICAL_ONLY':
        return '#EF4444'; // Red
      case 'OFFLINE':
        return '#6B7280'; // Gray
      default:
        return '#10B981';
    }
  };

  const getStatusLabel = () => {
    switch (systemMode) {
      case 'FULL':
        return 'All Safety Systems Operational';
      case 'DEGRADED':
        return 'System Degraded — Auxiliary Services Fallback Active';
      case 'CRITICAL_ONLY':
        return 'CRITICAL-ONLY MODE — AI & Analytics Load-Shed Active';
      case 'OFFLINE':
        return 'Emergency Offline Mode';
    }
  };

  return (
    <View style={[styles.container, { borderLeftColor: getStatusColor() }]}>
      <View style={styles.leftRow}>
        <View style={[styles.indicatorDot, { backgroundColor: getStatusColor() }]} />
        <View>
          <Text style={styles.statusText}>{getStatusLabel()}</Text>
          <Text style={styles.reasonText}>{modeReason}</Text>
        </View>
      </View>

      <View style={styles.rightRow}>
        {goldenSignals && (
          <View style={styles.metricBadge}>
            <Text style={styles.metricLabel}>API p95:</Text>
            <Text style={styles.metricValue}>{goldenSignals.latency_ms.p95}ms</Text>
          </View>
        )}
        {onOpenDetailedMetrics && (
          <TouchableOpacity style={styles.detailsButton} onPress={onOpenDetailedMetrics}>
            <Text style={styles.detailsButtonText}>SRE Health</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0F172A',
    borderLeftWidth: 4,
    paddingVertical: 10,
    paddingHorizontal: 16,
    marginHorizontal: 16,
    marginVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  leftRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  indicatorDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 12,
  },
  statusText: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '700',
  },
  reasonText: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  rightRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  metricBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
    gap: 4,
  },
  metricLabel: {
    color: '#64748B',
    fontSize: 11,
  },
  metricValue: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: '600',
  },
  detailsButton: {
    backgroundColor: '#334155',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 6,
  },
  detailsButtonText: {
    color: '#E2E8F0',
    fontSize: 11,
    fontWeight: '600',
  },
});
