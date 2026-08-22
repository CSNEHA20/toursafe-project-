import React, { useEffect, useState } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Switch,
  ActivityIndicator,
  Modal,
  FlatList,
} from 'react-native';
import {
  Cable,
  Activity,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RotateCcw,
  Zap,
  Globe,
  Radio,
  MapPin,
  MessageSquare,
  PhoneCall,
  Mail,
  Bell,
  Fingerprint,
  CloudSun,
  Languages,
  Landmark,
  FileCheck2,
  Building,
  RefreshCw,
  Search,
  Check,
  ShieldCheck,
  Server,
  Lock,
  Layers,
} from 'lucide-react-native';
import { useAuthStore } from '@/store/authStore';
import { useIntegrationStore } from '@/store/integrationStore';
import Toast from 'react-native-toast-message';
import { IntegrationRegistration, IntegrationType } from '@/types/integrations';

export default function AdminIntegrationsScreen() {
  const { user, accessToken, isAuthenticated } = useAuthStore();
  const {
    integrations,
    deadLetters,
    auditLogs,
    conflicts,
    selectedIntegration,
    loading,
    testingProvider,
    testResult,
    fetchIntegrations,
    fetchDeadLetters,
    fetchAuditLogs,
    fetchConflicts,
    testConnection,
    updateConfig,
    retryDeadLetter,
    resolveConflict,
    setSelectedIntegration,
    clearTestResult,
  } = useIntegrationStore();

  const [activeSubTab, setActiveSubTab] = useState<
    'providers' | 'dead_letter' | 'conflicts' | 'webhooks' | 'audit'
  >('providers');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [configModalVisible, setConfigModalVisible] = useState(false);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [editTimeout, setEditTimeout] = useState<string>('5.0');
  const [editEnabled, setEditEnabled] = useState<boolean>(true);

  useEffect(() => {
    if (isAuthenticated && accessToken) {
      fetchIntegrations(accessToken);
      fetchDeadLetters(accessToken);
      fetchAuditLogs(accessToken);
      fetchConflicts(accessToken);
    }
  }, [isAuthenticated, accessToken]);

  const handleTestConnection = async (providerName: string) => {
    if (!accessToken) return;
    setTestModalVisible(true);
    await testConnection(accessToken, providerName);
  };

  const handleSaveConfig = async () => {
    if (!selectedIntegration || !accessToken) return;
    const ok = await updateConfig(accessToken, selectedIntegration.provider_name, {
      enabled: editEnabled,
      timeout_seconds: parseFloat(editTimeout) || 5.0,
    });
    if (ok) {
      Toast.show({
        type: 'success',
        text1: 'Configuration Saved',
        text2: `Updated settings for ${selectedIntegration.provider_name}`,
      });
      setConfigModalVisible(false);
    } else {
      Toast.show({
        type: 'error',
        text1: 'Save Failed',
        text2: 'Could not update integration config.',
      });
    }
  };

  const handleRetryDLQ = async (recordId: string) => {
    if (!accessToken) return;
    const ok = await retryDeadLetter(accessToken, recordId);
    if (ok) {
      Toast.show({
        type: 'success',
        text1: 'Retry Scheduled',
        text2: `Operation re-queued from Dead-Letter Queue.`,
      });
    }
  };

  const handleResolveConflict = async (conflictId: string, policy: string, status: string) => {
    if (!accessToken) return;
    const ok = await resolveConflict(accessToken, conflictId, policy, status);
    if (ok) {
      Toast.show({
        type: 'success',
        text1: 'Conflict Resolved',
        text2: `Policy applied: ${policy}`,
      });
    }
  };

  // Metrics
  const totalProviders = integrations.length;
  const activeHealthy = integrations.filter((i) => i.health.is_healthy && i.configuration.enabled).length;
  const circuitOpenCount = integrations.filter((i) => i.health.circuit_state === 'OPEN').length;
  const dlqCount = deadLetters.filter((d) => !d.resolved).length;
  const conflictCount = conflicts.filter((c) => !c.resolved).length;

  const filteredIntegrations = integrations.filter((item) => {
    const matchesSearch =
      item.provider_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.integration_type.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filterType === 'ALL' || item.integration_type === filterType;
    return matchesSearch && matchesFilter;
  });

  const getProviderIcon = (type: IntegrationType) => {
    switch (type) {
      case 'MAPS':
      case 'ROUTING':
      case 'GEOCODING':
        return <MapPin size={18} color="#38bdf8" />;
      case 'SMS':
        return <MessageSquare size={18} color="#4ade80" />;
      case 'VOICE':
        return <PhoneCall size={18} color="#a78bfa" />;
      case 'EMAIL':
        return <Mail size={18} color="#f472b6" />;
      case 'PUSH':
        return <Bell size={18} color="#fbbf24" />;
      case 'IDENTITY':
      case 'KYC':
        return <Fingerprint size={18} color="#60a5fa" />;
      case 'WEATHER':
        return <CloudSun size={18} color="#f59e0b" />;
      case 'TRANSLATION':
        return <Languages size={18} color="#c084fc" />;
      case 'EMERGENCY_SERVICE':
        return <ShieldAlert size={18} color="#ef4444" />;
      case 'GOVERNMENT':
        return <Landmark size={18} color="#e2e8f0" />;
      case 'TOURISM':
        return <Building size={18} color="#2dd4bf" />;
      case 'DOCUMENT':
        return <FileCheck2 size={18} color="#94a3b8" />;
      default:
        return <Cable size={18} color="#cbd5e1" />;
    }
  };

  return (
    <View style={styles.container}>
      {/* Header Bar */}
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <Cable size={24} color="#38bdf8" />
          <Text style={styles.headerTitle}>External Integrations & Interoperability</Text>
        </View>
        <TouchableOpacity
          style={styles.refreshButton}
          onPress={() => accessToken && fetchIntegrations(accessToken)}
        >
          <RefreshCw size={16} color="#94a3b8" />
          <Text style={styles.refreshText}>Refresh</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* KPI Dashboard Cards */}
        <View style={styles.kpiGrid}>
          <View style={styles.kpiCard}>
            <Text style={styles.kpiLabel}>Total Adapters</Text>
            <Text style={styles.kpiValue}>{totalProviders}</Text>
            <Text style={styles.kpiSub}>Registered Providers</Text>
          </View>
          <View style={[styles.kpiCard, { borderColor: '#22c55e' }]}>
            <Text style={[styles.kpiLabel, { color: '#4ade80' }]}>Operational</Text>
            <Text style={[styles.kpiValue, { color: '#4ade80' }]}>{activeHealthy}</Text>
            <Text style={styles.kpiSub}>Healthy & Active</Text>
          </View>
          <View style={[styles.kpiCard, circuitOpenCount > 0 && { borderColor: '#ef4444' }]}>
            <Text style={[styles.kpiLabel, { color: circuitOpenCount > 0 ? '#f87171' : '#94a3b8' }]}>
              Circuits Open
            </Text>
            <Text style={[styles.kpiValue, { color: circuitOpenCount > 0 ? '#f87171' : '#f8fafc' }]}>
              {circuitOpenCount}
            </Text>
            <Text style={styles.kpiSub}>Tripped Providers</Text>
          </View>
          <View style={[styles.kpiCard, dlqCount > 0 && { borderColor: '#fbbf24' }]}>
            <Text style={[styles.kpiLabel, { color: '#fbbf24' }]}>Dead-Letter (DLQ)</Text>
            <Text style={[styles.kpiValue, { color: '#fbbf24' }]}>{dlqCount}</Text>
            <Text style={styles.kpiSub}>Unresolved Requests</Text>
          </View>
          <View style={[styles.kpiCard, conflictCount > 0 && { borderColor: '#f97316' }]}>
            <Text style={[styles.kpiLabel, { color: '#f97316' }]}>State Conflicts</Text>
            <Text style={[styles.kpiValue, { color: '#f97316' }]}>{conflictCount}</Text>
            <Text style={styles.kpiSub}>Sync Desync</Text>
          </View>
        </View>

        {/* Sub-tab Navigation */}
        <View style={styles.tabNav}>
          <TouchableOpacity
            style={[styles.tabItem, activeSubTab === 'providers' && styles.tabItemActive]}
            onPress={() => setActiveSubTab('providers')}
          >
            <Server size={16} color={activeSubTab === 'providers' ? '#38bdf8' : '#94a3b8'} />
            <Text style={[styles.tabItemText, activeSubTab === 'providers' && styles.tabItemTextActive]}>
              Adapters & Providers ({integrations.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeSubTab === 'dead_letter' && styles.tabItemActive]}
            onPress={() => setActiveSubTab('dead_letter')}
          >
            <RotateCcw size={16} color={activeSubTab === 'dead_letter' ? '#fbbf24' : '#94a3b8'} />
            <Text style={[styles.tabItemText, activeSubTab === 'dead_letter' && styles.tabItemTextActive]}>
              Dead-Letter Queue ({dlqCount})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeSubTab === 'conflicts' && styles.tabItemActive]}
            onPress={() => setActiveSubTab('conflicts')}
          >
            <AlertTriangle size={16} color={activeSubTab === 'conflicts' ? '#f97316' : '#94a3b8'} />
            <Text style={[styles.tabItemText, activeSubTab === 'conflicts' && styles.tabItemTextActive]}>
              State Conflicts ({conflictCount})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeSubTab === 'webhooks' && styles.tabItemActive]}
            onPress={() => setActiveSubTab('webhooks')}
          >
            <ShieldCheck size={16} color={activeSubTab === 'webhooks' ? '#a78bfa' : '#94a3b8'} />
            <Text style={[styles.tabItemText, activeSubTab === 'webhooks' && styles.tabItemTextActive]}>
              Webhook Security
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeSubTab === 'audit' && styles.tabItemActive]}
            onPress={() => setActiveSubTab('audit')}
          >
            <Activity size={16} color={activeSubTab === 'audit' ? '#4ade80' : '#94a3b8'} />
            <Text style={[styles.tabItemText, activeSubTab === 'audit' && styles.tabItemTextActive]}>
              Audit Logs
            </Text>
          </TouchableOpacity>
        </View>

        {/* Tab 1: Adapters & Providers */}
        {activeSubTab === 'providers' && (
          <View style={styles.section}>
            {/* Search & Filter Bar */}
            <View style={styles.filterRow}>
              <View style={styles.searchBox}>
                <Search size={16} color="#64748b" />
                <TextInput
                  style={styles.searchInput}
                  placeholder="Search provider by name or type..."
                  placeholderTextColor="#64748b"
                  value={searchQuery}
                  onChangeText={setSearchQuery}
                />
              </View>
            </View>

            {loading ? (
              <ActivityIndicator size="large" color="#38bdf8" style={{ marginTop: 40 }} />
            ) : (
              <View style={styles.adapterGrid}>
                {filteredIntegrations.map((item) => {
                  const isHealthy = item.health.is_healthy;
                  const circuitState = item.health.circuit_state;
                  return (
                    <View key={item.integration_id} style={styles.adapterCard}>
                      <View style={styles.adapterCardHeader}>
                        <View style={styles.adapterIconBox}>
                          {getProviderIcon(item.integration_type)}
                        </View>
                        <View style={{ flex: 1, marginLeft: 10 }}>
                          <Text style={styles.adapterName}>{item.provider_name}</Text>
                          <Text style={styles.adapterType}>
                            {item.integration_type} • {item.is_real_provider ? 'Real API' : 'Simulated / Dev'}
                          </Text>
                        </View>
                        <View
                          style={[
                            styles.statusPill,
                            {
                              backgroundColor:
                                circuitState === 'OPEN'
                                  ? 'rgba(239, 68, 68, 0.2)'
                                  : isHealthy
                                  ? 'rgba(34, 197, 94, 0.2)'
                                  : 'rgba(245, 158, 11, 0.2)',
                            },
                          ]}
                        >
                          <Text
                            style={[
                              styles.statusPillText,
                              {
                                color:
                                  circuitState === 'OPEN'
                                    ? '#f87171'
                                    : isHealthy
                                    ? '#4ade80'
                                    : '#fbbf24',
                              },
                            ]}
                          >
                            {circuitState === 'OPEN' ? 'CIRCUIT OPEN' : item.status}
                          </Text>
                        </View>
                      </View>

                      {/* Capabilities */}
                      <View style={styles.capabilityRow}>
                        {item.capabilities.slice(0, 3).map((cap, idx) => (
                          <View key={idx} style={styles.capBadge}>
                            <Text style={styles.capBadgeText}>{cap}</Text>
                          </View>
                        ))}
                        {item.capabilities.length > 3 && (
                          <View style={styles.capBadge}>
                            <Text style={styles.capBadgeText}>+{item.capabilities.length - 3} more</Text>
                          </View>
                        )}
                      </View>

                      {/* Metrics Summary */}
                      <View style={styles.cardMetrics}>
                        <View style={styles.metricItem}>
                          <Text style={styles.metricLabel}>Latency</Text>
                          <Text style={styles.metricValue}>{item.health.latency_ms} ms</Text>
                        </View>
                        <View style={styles.metricItem}>
                          <Text style={styles.metricLabel}>Timeout</Text>
                          <Text style={styles.metricValue}>{item.configuration.timeout_seconds}s</Text>
                        </View>
                        <View style={styles.metricItem}>
                          <Text style={styles.metricLabel}>Circuit State</Text>
                          <Text style={[styles.metricValue, { color: circuitState === 'CLOSED' ? '#4ade80' : '#f87171' }]}>
                            {circuitState}
                          </Text>
                        </View>
                        <View style={styles.metricItem}>
                          <Text style={styles.metricLabel}>Credentials</Text>
                          <Text style={[styles.metricValue, { color: '#38bdf8' }]}>
                            {item.configuration.api_key_configured ? 'CONFIGURED' : 'DEV_KEY'}
                          </Text>
                        </View>
                      </View>

                      {/* Actions */}
                      <View style={styles.cardActions}>
                        <TouchableOpacity
                          style={styles.testBtn}
                          onPress={() => handleTestConnection(item.provider_name)}
                        >
                          <Zap size={14} color="#f8fafc" />
                          <Text style={styles.testBtnText}>Test Connection</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={styles.configBtn}
                          onPress={() => {
                            setSelectedIntegration(item);
                            setEditEnabled(item.configuration.enabled);
                            setEditTimeout(String(item.configuration.timeout_seconds));
                            setConfigModalVisible(true);
                          }}
                        >
                          <Text style={styles.configBtnText}>Configure</Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </View>
        )}

        {/* Tab 2: Dead-Letter Queue */}
        {activeSubTab === 'dead_letter' && (
          <View style={styles.section}>
            <Text style={styles.sectionSubtitle}>
              Unrecoverable or retry-exhausted outbound tasks stored safely for inspection and authorized manual replay.
            </Text>
            {deadLetters.length === 0 ? (
              <View style={styles.emptyState}>
                <CheckCircle2 size={40} color="#4ade80" />
                <Text style={styles.emptyText}>Dead-Letter Queue is empty. All operations healthy.</Text>
              </View>
            ) : (
              deadLetters.map((dlq) => (
                <View key={dlq.record_id} style={styles.dlqCard}>
                  <View style={styles.dlqHeader}>
                    <View>
                      <Text style={styles.dlqTitle}>{dlq.operation_name}</Text>
                      <Text style={styles.dlqSub}>
                        Provider: {dlq.provider_name} • Key: {dlq.idempotency_key}
                      </Text>
                    </View>
                    <View style={[styles.statusPill, { backgroundColor: dlq.resolved ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)' }]}>
                      <Text style={[styles.statusPillText, { color: dlq.resolved ? '#4ade80' : '#f87171' }]}>
                        {dlq.resolved ? 'RESOLVED' : 'UNRESOLVED'}
                      </Text>
                    </View>
                  </View>
                  <Text style={styles.dlqError}>
                    [{dlq.error_code}] {dlq.error_message}
                  </Text>
                  <View style={styles.dlqFooter}>
                    <Text style={styles.dlqAttempts}>
                      Attempts: {dlq.attempt_count}/{dlq.max_attempts} • Correlation: {dlq.correlation_id}
                    </Text>
                    {!dlq.resolved && (
                      <TouchableOpacity
                        style={styles.retryBtn}
                        onPress={() => handleRetryDLQ(dlq.record_id)}
                      >
                        <RotateCcw size={14} color="#0f172a" />
                        <Text style={styles.retryBtnText}>Authorized Retry</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                </View>
              ))
            )}
          </View>
        )}

        {/* Tab 3: State Conflicts */}
        {activeSubTab === 'conflicts' && (
          <View style={styles.section}>
            <Text style={styles.sectionSubtitle}>
              Bidirectional state desynchronization detected between TourSafe and external agency systems.
            </Text>
            {conflicts.length === 0 ? (
              <View style={styles.emptyState}>
                <ShieldCheck size={40} color="#38bdf8" />
                <Text style={styles.emptyText}>No active state conflicts detected. Internal and external states in sync.</Text>
              </View>
            ) : (
              conflicts.map((conf) => (
                <View key={conf.conflict_id} style={styles.conflictCard}>
                  <View style={styles.conflictHeader}>
                    <Text style={styles.conflictTitle}>Incident: {conf.toursafe_incident_id}</Text>
                    <Text style={styles.conflictSystem}>System: {conf.external_system}</Text>
                  </View>
                  <View style={styles.conflictDiff}>
                    <View style={styles.diffBox}>
                      <Text style={styles.diffLabel}>TourSafe State</Text>
                      <Text style={styles.diffValue}>{conf.toursafe_status}</Text>
                    </View>
                    <Text style={styles.diffVs}>vs</Text>
                    <View style={styles.diffBox}>
                      <Text style={styles.diffLabel}>External State</Text>
                      <Text style={styles.diffValue}>{conf.external_status}</Text>
                    </View>
                  </View>
                  {!conf.resolved && (
                    <View style={styles.conflictActions}>
                      <TouchableOpacity
                        style={[styles.resolveBtn, { backgroundColor: '#38bdf8' }]}
                        onPress={() => handleResolveConflict(conf.conflict_id, 'TOURSAFE_WINS', conf.toursafe_status)}
                      >
                        <Text style={styles.resolveBtnText}>Enforce TourSafe State</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.resolveBtn, { backgroundColor: '#f97316' }]}
                        onPress={() => handleResolveConflict(conf.conflict_id, 'EXTERNAL_WINS', conf.external_status)}
                      >
                        <Text style={styles.resolveBtnText}>Accept External State</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              ))
            )}
          </View>
        )}

        {/* Tab 4: Webhook Security */}
        {activeSubTab === 'webhooks' && (
          <View style={styles.section}>
            <View style={styles.securityBox}>
              <View style={styles.secRow}>
                <Lock size={18} color="#38bdf8" />
                <Text style={styles.secHeading}>Cryptographic Inbound Verification</Text>
              </View>
              <Text style={styles.secDesc}>
                All incoming webhooks at <Text style={{ color: '#38bdf8' }}>/api/v1/integrations/webhooks/*</Text> require HMAC-SHA256 signatures via <Text style={{ color: '#a78bfa' }}>X-Signature-256</Text> or <Text style={{ color: '#a78bfa' }}>X-Hub-Signature-256</Text>. Unsigned or invalid requests are rejected with 401 Unauthorized.
              </Text>
            </View>

            <View style={styles.securityBox}>
              <View style={styles.secRow}>
                <RotateCcw size={18} color="#fbbf24" />
                <Text style={styles.secHeading}>Anti-Replay & Timestamp Windows</Text>
              </View>
              <Text style={styles.secDesc}>
                Webhooks exceeding the 300-second (5-minute) drift window or repeating cached event IDs/nonces are acknowledged idempotently without triggering duplicate operational dispatches.
              </Text>
            </View>

            <View style={styles.securityBox}>
              <View style={styles.secRow}>
                <ShieldCheck size={18} color="#4ade80" />
                <Text style={styles.secHeading}>SSRF & Private Network Defense</Text>
              </View>
              <Text style={styles.secDesc}>
                Outbound HTTP requests reject loopbacks (127.0.0.1), private RFC1918 networks (10.0.0.0/8, 192.168.0.0/16), and Cloud Metadata IPs (169.254.169.254). Outbound targets are restricted to configured domain allowlists.
              </Text>
            </View>
          </View>
        )}

        {/* Tab 5: Audit Logs */}
        {activeSubTab === 'audit' && (
          <View style={styles.section}>
            {auditLogs.map((log) => (
              <View key={log.audit_id} style={styles.auditRow}>
                <View style={styles.auditIconBox}>
                  <Activity size={14} color="#38bdf8" />
                </View>
                <View style={{ flex: 1, marginLeft: 10 }}>
                  <Text style={styles.auditAction}>
                    {log.action} • {log.provider_name || 'SYSTEM'}
                  </Text>
                  <Text style={styles.auditMeta}>
                    Actor: {log.actor_id} ({log.actor_role}) • CorrID: {log.correlation_id}
                  </Text>
                </View>
                <View style={styles.auditTimeBox}>
                  <Text style={styles.auditStatus}>{log.status}</Text>
                  <Text style={styles.auditTime}>
                    {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>

      {/* Test Connection Result Modal */}
      <Modal visible={testModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Integration Health Probe</Text>
              <TouchableOpacity onPress={() => setTestModalVisible(false)}>
                <XCircle size={20} color="#94a3b8" />
              </TouchableOpacity>
            </View>
            {testingProvider ? (
              <View style={{ padding: 30, alignItems: 'center' }}>
                <ActivityIndicator size="large" color="#38bdf8" />
                <Text style={{ color: '#e2e8f0', marginTop: 15 }}>Testing provider connectivity...</Text>
              </View>
            ) : testResult ? (
              <View style={{ padding: 20 }}>
                <View style={styles.testResultRow}>
                  <Text style={styles.testResultLabel}>Provider:</Text>
                  <Text style={styles.testResultVal}>{testResult.provider_name}</Text>
                </View>
                <View style={styles.testResultRow}>
                  <Text style={styles.testResultLabel}>Status:</Text>
                  <Text style={[styles.testResultVal, { color: testResult.success ? '#4ade80' : '#f87171' }]}>
                    {testResult.status}
                  </Text>
                </View>
                <View style={styles.testResultRow}>
                  <Text style={styles.testResultLabel}>Latency:</Text>
                  <Text style={styles.testResultVal}>{testResult.latency_ms} ms</Text>
                </View>
                <View style={styles.testResultRow}>
                  <Text style={styles.testResultLabel}>Circuit State:</Text>
                  <Text style={[styles.testResultVal, { color: '#38bdf8' }]}>{testResult.circuit_state}</Text>
                </View>
                <View style={styles.testResultRow}>
                  <Text style={styles.testResultLabel}>Diagnostics:</Text>
                  <Text style={styles.testResultVal}>{testResult.detail}</Text>
                </View>
              </View>
            ) : null}
            <TouchableOpacity style={styles.modalCloseBtn} onPress={() => setTestModalVisible(false)}>
              <Text style={styles.modalCloseBtnText}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Configure Provider Modal */}
      <Modal visible={configModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Configure {selectedIntegration?.provider_name}</Text>
              <TouchableOpacity onPress={() => setConfigModalVisible(false)}>
                <XCircle size={20} color="#94a3b8" />
              </TouchableOpacity>
            </View>

            <View style={{ padding: 20 }}>
              <View style={styles.formRow}>
                <Text style={styles.formLabel}>Enabled Status</Text>
                <Switch value={editEnabled} onValueChange={setEditEnabled} trackColor={{ true: '#38bdf8', false: '#334155' }} />
              </View>

              <View style={styles.formRowInput}>
                <Text style={styles.formLabel}>Timeout (Seconds)</Text>
                <TextInput
                  style={styles.modalInput}
                  keyboardType="numeric"
                  value={editTimeout}
                  onChangeText={setEditTimeout}
                />
              </View>

              <View style={styles.secretNotice}>
                <Lock size={16} color="#38bdf8" />
                <Text style={styles.secretNoticeText}>
                  API Credentials & Private Keys are safely masked and managed via backend secret environment stores.
                </Text>
              </View>
            </View>

            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setConfigModalVisible(false)}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSaveConfig}>
                <Text style={styles.saveBtnText}>Save Settings</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0f1d',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#f8fafc',
  },
  refreshButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: '#1e293b',
    borderRadius: 8,
  },
  refreshText: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '500',
  },
  scrollContent: {
    flex: 1,
    padding: 20,
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 20,
  },
  kpiCard: {
    flex: 1,
    minWidth: 140,
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 14,
  },
  kpiLabel: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '500',
  },
  kpiValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#f8fafc',
    marginVertical: 4,
  },
  kpiSub: {
    fontSize: 10,
    color: '#64748b',
  },
  tabNav: {
    flexDirection: 'row',
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 4,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#1f2937',
  },
  tabItem: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
  },
  tabItemActive: {
    backgroundColor: '#1e293b',
  },
  tabItemText: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '500',
  },
  tabItemTextActive: {
    color: '#f8fafc',
    fontWeight: '600',
  },
  section: {
    marginBottom: 40,
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#94a3b8',
    marginBottom: 16,
  },
  filterRow: {
    marginBottom: 16,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 10,
    paddingHorizontal: 14,
    height: 42,
  },
  searchInput: {
    flex: 1,
    color: '#f8fafc',
    fontSize: 13,
  },
  adapterGrid: {
    gap: 14,
  },
  adapterCard: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
  },
  adapterCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  adapterIconBox: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  adapterName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#f8fafc',
  },
  adapterType: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 2,
  },
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusPillText: {
    fontSize: 10,
    fontWeight: '700',
  },
  capabilityRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginVertical: 12,
  },
  capBadge: {
    backgroundColor: '#1e293b',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  capBadgeText: {
    fontSize: 10,
    color: '#cbd5e1',
  },
  cardMetrics: {
    flexDirection: 'row',
    backgroundColor: '#0a0f1d',
    borderRadius: 8,
    padding: 10,
    marginVertical: 10,
    justifyContent: 'space-around',
  },
  metricItem: {
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: 10,
    color: '#64748b',
  },
  metricValue: {
    fontSize: 12,
    fontWeight: '600',
    color: '#f8fafc',
    marginTop: 2,
  },
  cardActions: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 6,
  },
  testBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#0284c7',
    paddingVertical: 8,
    borderRadius: 8,
  },
  testBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#f8fafc',
  },
  configBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#1e293b',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  configBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#cbd5e1',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    backgroundColor: '#111827',
    borderRadius: 12,
    gap: 12,
  },
  emptyText: {
    fontSize: 13,
    color: '#94a3b8',
  },
  dlqCard: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  dlqHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dlqTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#f8fafc',
  },
  dlqSub: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 2,
  },
  dlqError: {
    fontSize: 12,
    color: '#f87171',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    padding: 8,
    borderRadius: 6,
    marginVertical: 10,
  },
  dlqFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dlqAttempts: {
    fontSize: 11,
    color: '#64748b',
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#fbbf24',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  retryBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0f172a',
  },
  conflictCard: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  conflictHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  conflictTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#f8fafc',
  },
  conflictSystem: {
    fontSize: 12,
    color: '#f97316',
  },
  conflictDiff: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    backgroundColor: '#0a0f1d',
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  diffBox: {
    alignItems: 'center',
  },
  diffLabel: {
    fontSize: 10,
    color: '#64748b',
  },
  diffValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#f8fafc',
    marginTop: 2,
  },
  diffVs: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '600',
  },
  conflictActions: {
    flexDirection: 'row',
    gap: 10,
  },
  resolveBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
  },
  resolveBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#f8fafc',
  },
  securityBox: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    marginBottom: 14,
  },
  secRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  secHeading: {
    fontSize: 14,
    fontWeight: '700',
    color: '#f8fafc',
  },
  secDesc: {
    fontSize: 12,
    color: '#94a3b8',
    lineHeight: 18,
  },
  auditRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#111827',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1f2937',
  },
  auditIconBox: {
    width: 28,
    height: 28,
    borderRadius: 6,
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  auditAction: {
    fontSize: 13,
    fontWeight: '600',
    color: '#f8fafc',
  },
  auditMeta: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 2,
  },
  auditTimeBox: {
    alignItems: 'flex-end',
  },
  auditStatus: {
    fontSize: 11,
    fontWeight: '700',
    color: '#4ade80',
  },
  auditTime: {
    fontSize: 10,
    color: '#64748b',
    marginTop: 2,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  modalCard: {
    width: '100%',
    maxWidth: 500,
    backgroundColor: '#111827',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1f2937',
    overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1f2937',
  },
  modalTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#f8fafc',
  },
  testResultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  testResultLabel: {
    fontSize: 13,
    color: '#94a3b8',
  },
  testResultVal: {
    fontSize: 13,
    fontWeight: '600',
    color: '#f8fafc',
  },
  modalCloseBtn: {
    backgroundColor: '#1e293b',
    padding: 12,
    alignItems: 'center',
  },
  modalCloseBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#cbd5e1',
  },
  formRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  formRowInput: {
    marginBottom: 16,
  },
  formLabel: {
    fontSize: 13,
    color: '#94a3b8',
    marginBottom: 6,
  },
  modalInput: {
    backgroundColor: '#0a0f1d',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 8,
    padding: 10,
    color: '#f8fafc',
    fontSize: 14,
  },
  secretNotice: {
    flexDirection: 'row',
    gap: 8,
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  secretNoticeText: {
    flex: 1,
    fontSize: 11,
    color: '#38bdf8',
    lineHeight: 16,
  },
  modalFooter: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#1f2937',
  },
  cancelBtn: {
    flex: 1,
    padding: 14,
    alignItems: 'center',
    backgroundColor: '#1e293b',
  },
  cancelBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#94a3b8',
  },
  saveBtn: {
    flex: 1,
    padding: 14,
    alignItems: 'center',
    backgroundColor: '#0284c7',
  },
  saveBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#f8fafc',
  },
});
