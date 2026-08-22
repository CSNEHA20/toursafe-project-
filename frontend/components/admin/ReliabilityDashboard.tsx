import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { useReliabilityStore } from '../../store/reliabilityStore';
import { SystemMode } from '../../types/reliability';

export const ReliabilityDashboard: React.FC = () => {
  const {
    systemMode,
    modeReason,
    uptimeSeconds,
    goldenSignals,
    subsystems,
    slos,
    deadLetters,
    backups,
    fetchMetrics,
    fetchSLOs,
    fetchDegradation,
    setDegradationMode,
    fetchDeadLetters,
    replayDeadLetter,
    fetchBackups,
    createBackup,
    restoreBackup,
    runChaosDrills,
  } = useReliabilityStore();

  const [activeTab, setActiveTab] = useState<'metrics' | 'slos' | 'dlq' | 'backups' | 'chaos'>('metrics');
  const [chaosResults, setChaosResults] = useState<any>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    fetchMetrics();
    fetchSLOs();
    fetchDegradation();
    fetchDeadLetters();
    fetchBackups();

    const interval = setInterval(() => {
      fetchMetrics();
      fetchSLOs();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleModeChange = async (mode: SystemMode) => {
    const reason = `Manual operator override from Reliability Dashboard`;
    setIsProcessing(true);
    await setDegradationMode(mode, reason);
    setIsProcessing(false);
  };

  const handleReplay = async (jobId: string) => {
    setIsProcessing(true);
    const success = await replayDeadLetter(jobId);
    setIsProcessing(false);
    if (success) {
      alert('Job successfully replayed!');
    } else {
      alert('Failed to replay job.');
    }
  };

  const handleCreateBackup = async () => {
    setIsProcessing(true);
    const success = await createBackup();
    setIsProcessing(false);
    if (success) {
      alert('Snapshot backup created successfully!');
    }
  };

  const handleRestore = async (backupId: string, dryRun: boolean) => {
    setIsProcessing(true);
    const success = await restoreBackup(backupId, dryRun);
    setIsProcessing(false);
    if (success) {
      alert(`Restore ${dryRun ? '(Dry Run)' : ''} executed successfully!`);
    } else {
      alert('Restore failed.');
    }
  };

  const handleRunChaos = async () => {
    setIsProcessing(true);
    const results = await runChaosDrills();
    setIsProcessing(false);
    setChaosResults(results);
  };

  const formatUptime = (sec: number) => {
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${d}d ${h}h ${m}m`;
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header Bar */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Production Reliability & Observability</Text>
          <Text style={styles.subtitle}>
            Uptime: {formatUptime(uptimeSeconds)} | Mode: <Text style={styles.modeText}>{systemMode}</Text>
          </Text>
        </View>

        {/* Degradation Mode Selectors */}
        <View style={styles.modeButtonsRow}>
          {(['FULL', 'DEGRADED', 'CRITICAL_ONLY'] as SystemMode[]).map((m) => (
            <TouchableOpacity
              key={m}
              style={[
                styles.modeBtn,
                systemMode === m && styles.modeBtnActive,
                m === 'CRITICAL_ONLY' && styles.criticalBtn,
              ]}
              onPress={() => handleModeChange(m)}
              disabled={isProcessing}
            >
              <Text
                style={[
                  styles.modeBtnText,
                  systemMode === m && styles.modeBtnTextActive,
                ]}
              >
                {m}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Navigation Tabs */}
      <View style={styles.tabsRow}>
        {(['metrics', 'slos', 'dlq', 'backups', 'chaos'] as const).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {isProcessing && <ActivityIndicator size="small" color="#38BDF8" style={{ marginVertical: 12 }} />}

      {/* TAB 1: METRICS & GOLDEN SIGNALS */}
      {activeTab === 'metrics' && goldenSignals && subsystems && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Golden Signals</Text>
          <View style={styles.grid}>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Traffic (Requests)</Text>
              <Text style={styles.cardVal}>{goldenSignals.traffic.total_requests.toLocaleString()}</Text>
              <Text style={styles.cardSub}>2xx: {goldenSignals.traffic.requests_2xx} | 5xx: {goldenSignals.traffic.requests_5xx}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>API Latency (p95 / p99)</Text>
              <Text style={styles.cardVal}>{goldenSignals.latency_ms.p95} ms</Text>
              <Text style={styles.cardSub}>p50: {goldenSignals.latency_ms.p50}ms | p99: {goldenSignals.latency_ms.p99}ms</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>5xx Error Rate</Text>
              <Text style={[styles.cardVal, goldenSignals.errors.error_rate_5xx > 0.1 && { color: '#EF4444' }]}>
                {goldenSignals.errors.error_rate_5xx}%
              </Text>
              <Text style={styles.cardSub}>Client 4xx: {goldenSignals.errors.client_error_rate_4xx}%</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Process Saturation</Text>
              <Text style={styles.cardVal}>{goldenSignals.saturation.cpu_percent}% CPU</Text>
              <Text style={styles.cardSub}>RAM: {goldenSignals.saturation.memory_rss_mb} MB</Text>
            </View>
          </View>

          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>Safety Subsystems</Text>
          <View style={styles.grid}>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>MongoDB Core</Text>
              <Text style={styles.cardVal}>{subsystems.database.latency_ms.p50 || 0} ms</Text>
              <Text style={styles.cardSub}>Slow queries (&gt;100ms): {subsystems.database.slow_queries}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Redis Ephemeral</Text>
              <Text style={styles.cardVal}>{subsystems.redis.latency_ms.p50 || 0} ms</Text>
              <Text style={styles.cardSub}>Commands: {subsystems.redis.commands_total} | Err: {subsystems.redis.errors}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>SOS Ingestion</Text>
              <Text style={styles.cardVal}>{subsystems.incident_operations.sos_signals_received}</Text>
              <Text style={styles.cardSub}>Failures: {subsystems.incident_operations.sos_processing_failures}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Telemetry Pipeline</Text>
              <Text style={styles.cardVal}>{subsystems.telemetry.packets_ingested.toLocaleString()}</Text>
              <Text style={styles.cardSub}>Dropped: {subsystems.telemetry.packets_dropped} | Gaps: {subsystems.telemetry.sequence_gaps}</Text>
            </View>
          </View>
        </View>
      )}

      {/* TAB 2: SLOs & ERROR BUDGETS */}
      {activeTab === 'slos' && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>SLO Compliance & Error Budgets</Text>
          {slos.map((s, idx) => (
            <View key={idx} style={styles.sloCard}>
              <View style={styles.sloHeader}>
                <Text style={styles.sloName}>{s.name}</Text>
                <View style={[styles.badge, s.status === 'HEALTHY' ? styles.badgeGreen : styles.badgeRed]}>
                  <Text style={styles.badgeText}>{s.status}</Text>
                </View>
              </View>
              <Text style={styles.sloFormula}>Formula: {s.sli_formula}</Text>
              <View style={styles.sloStatsRow}>
                <Text style={styles.sloStat}>Target: {s.target ? `${s.target}%` : `${s.target_ms}ms`}</Text>
                <Text style={styles.sloStat}>Actual: {s.actual !== undefined ? `${s.actual}%` : `${s.actual_ms}ms`}</Text>
                <Text style={styles.sloStat}>Window: {s.window}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* TAB 3: DEAD-LETTER QUEUE */}
      {activeTab === 'dlq' && (
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>Dead-Letter Messages ({deadLetters.length})</Text>
            <TouchableOpacity style={styles.actionBtn} onPress={fetchDeadLetters}>
              <Text style={styles.actionBtnText}>Refresh DLQ</Text>
            </TouchableOpacity>
          </View>
          {deadLetters.length === 0 ? (
            <Text style={styles.emptyText}>Zero dead-letter messages. All async queues healthy.</Text>
          ) : (
            deadLetters.map((dl) => (
              <View key={dl.job_id} style={styles.dlqCard}>
                <View style={styles.sloHeader}>
                  <Text style={styles.dlqId}>{dl.job_id} ({dl.queue_name})</Text>
                  <TouchableOpacity
                    style={styles.replayBtn}
                    onPress={() => handleReplay(dl.job_id)}
                  >
                    <Text style={styles.replayBtnText}>Replay</Text>
                  </TouchableOpacity>
                </View>
                <Text style={styles.dlqError}>Error: {dl.error_message}</Text>
                <Text style={styles.dlqMeta}>Failed at: {dl.failed_at} | Attempts: {dl.attempts}</Text>
              </View>
            ))
          )}
        </View>
      )}

      {/* TAB 4: BACKUPS & RESTORE */}
      {activeTab === 'backups' && (
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>System Snapshots ({backups.length})</Text>
            <TouchableOpacity style={styles.actionBtn} onPress={handleCreateBackup}>
              <Text style={styles.actionBtnText}>+ Create Snapshot</Text>
            </TouchableOpacity>
          </View>
          {backups.map((b) => (
            <View key={b.backup_id} style={styles.backupCard}>
              <View style={styles.sloHeader}>
                <Text style={styles.backupId}>{b.backup_id}</Text>
                <View style={styles.backupActions}>
                  <TouchableOpacity
                    style={styles.dryRunBtn}
                    onPress={() => handleRestore(b.backup_id, true)}
                  >
                    <Text style={styles.dryRunText}>Dry Run</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.restoreBtn}
                    onPress={() => handleRestore(b.backup_id, false)}
                  >
                    <Text style={styles.restoreText}>Restore</Text>
                  </TouchableOpacity>
                </View>
              </View>
              <Text style={styles.backupMeta}>
                Docs: {b.total_documents.toLocaleString()} | Size: {(b.size_bytes / 1024).toFixed(1)} KB | SHA256: {b.checksum_sha256.slice(0, 12)}...
              </Text>
              <Text style={styles.backupMeta}>Created: {b.created_at} by {b.created_by}</Text>
            </View>
          ))}
        </View>
      )}

      {/* TAB 5: CHAOS TESTING HARNESS */}
      {activeTab === 'chaos' && (
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <View>
              <Text style={styles.sectionTitle}>Resilience & Chaos Drills</Text>
              <Text style={styles.subtext}>Execute controlled failure injections to verify safety isolation.</Text>
            </View>
            <TouchableOpacity style={styles.chaosBtn} onPress={handleRunChaos}>
              <Text style={styles.chaosBtnText}>Run All Drills</Text>
            </TouchableOpacity>
          </View>

          {chaosResults && (
            <View style={styles.chaosContainer}>
              <Text style={[styles.chaosSummary, { color: chaosResults.all_passed ? '#10B981' : '#EF4444' }]}>
                {chaosResults.all_passed ? '✓ ALL RESILIENCE DRILLS PASSED' : '⚠️ DRILL FAILURES DETECTED'}
              </Text>
              {chaosResults.drills.map((d: any, idx: number) => (
                <View key={idx} style={styles.drillCard}>
                  <View style={styles.sloHeader}>
                    <Text style={styles.drillName}>{d.scenario}</Text>
                    <Text style={{ color: d.passed ? '#10B981' : '#EF4444', fontWeight: 'bold' }}>
                      {d.passed ? 'PASSED' : 'FAILED'} ({d.duration_ms}ms)
                    </Text>
                  </View>
                  <Text style={styles.drillDetails}>{JSON.stringify(d.details)}</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  content: {
    padding: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
    flexWrap: 'wrap',
    gap: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: '#F8FAFC',
  },
  subtitle: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 4,
  },
  modeText: {
    color: '#38BDF8',
    fontWeight: '700',
  },
  modeButtonsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  modeBtn: {
    backgroundColor: '#1E293B',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  modeBtnActive: {
    backgroundColor: '#0284C7',
  },
  criticalBtn: {
    borderColor: '#EF4444',
    borderWidth: 1,
  },
  modeBtnText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  modeBtnTextActive: {
    color: '#FFFFFF',
  },
  tabsRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    marginBottom: 16,
    gap: 16,
  },
  tab: {
    paddingVertical: 8,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#38BDF8',
  },
  tabText: {
    color: '#64748B',
    fontSize: 13,
    fontWeight: '600',
  },
  tabTextActive: {
    color: '#38BDF8',
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: '#F1F5F9',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
  },
  subtext: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 2,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  card: {
    flex: 1,
    minWidth: 200,
    backgroundColor: '#0F172A',
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  cardLabel: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  cardVal: {
    color: '#F8FAFC',
    fontSize: 20,
    fontWeight: '800',
    marginVertical: 4,
  },
  cardSub: {
    color: '#94A3B8',
    fontSize: 11,
  },
  sloCard: {
    backgroundColor: '#0F172A',
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 10,
  },
  sloHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sloName: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '700',
  },
  badge: {
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  badgeGreen: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  badgeRed: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  sloFormula: {
    color: '#64748B',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    marginVertical: 6,
  },
  sloStatsRow: {
    flexDirection: 'row',
    gap: 16,
  },
  sloStat: {
    color: '#94A3B8',
    fontSize: 12,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  actionBtn: {
    backgroundColor: '#0284C7',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  emptyText: {
    color: '#64748B',
    fontSize: 13,
    fontStyle: 'italic',
    paddingVertical: 20,
    textAlign: 'center',
  },
  dlqCard: {
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 8,
  },
  dlqId: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 13,
  },
  replayBtn: {
    backgroundColor: '#3B82F6',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 4,
  },
  replayBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  dlqError: {
    color: '#EF4444',
    fontSize: 12,
    marginTop: 4,
  },
  dlqMeta: {
    color: '#64748B',
    fontSize: 11,
    marginTop: 4,
  },
  backupCard: {
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 8,
  },
  backupId: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 13,
  },
  backupActions: {
    flexDirection: 'row',
    gap: 8,
  },
  dryRunBtn: {
    backgroundColor: '#334155',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  dryRunText: {
    color: '#E2E8F0',
    fontSize: 11,
    fontWeight: '600',
  },
  restoreBtn: {
    backgroundColor: '#DC2626',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  restoreText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  backupMeta: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 3,
  },
  chaosBtn: {
    backgroundColor: '#D97706',
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 6,
  },
  chaosBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  chaosContainer: {
    marginTop: 16,
  },
  chaosSummary: {
    fontSize: 15,
    fontWeight: '800',
    marginBottom: 12,
  },
  drillCard: {
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 8,
  },
  drillName: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 13,
  },
  drillDetails: {
    color: '#64748B',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    marginTop: 4,
  },
});
