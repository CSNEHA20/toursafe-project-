import React, { useEffect, useState } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  Platform,
} from 'react-native';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  Download,
  FileSpreadsheet,
  Gauge,
  Layers,
  MapPin,
  MapPinned,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Users,
  Zap,
  Radio,
  Cpu,
  Sparkles,
  Server,
  FileText,
  ChevronRight,
  TrendingDown,
  Info,
} from 'lucide-react-native';
import { analyticsApi } from '@/lib/api';

type TabType =
  | 'executive'
  | 'incidents'
  | 'safety'
  | 'geospatial'
  | 'responders'
  | 'escalations'
  | 'models'
  | 'forecasting'
  | 'quality'
  | 'system';

type TimeWindowOption = 'LIVE' | 'TODAY' | 'LAST_24_HOURS' | 'LAST_7_DAYS' | 'LAST_30_DAYS';

export default function AdminAnalyticsDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('executive');
  const [timeWindow, setTimeWindow] = useState<TimeWindowOption>('LAST_7_DAYS');
  const [timezone, setTimezone] = useState<string>('UTC');
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Analytical State Datasets
  const [executiveData, setExecutiveData] = useState<any>(null);
  const [incidentData, setIncidentData] = useState<any>(null);
  const [safetyData, setSafetyData] = useState<any>(null);
  const [zoneData, setZoneData] = useState<any>(null);
  const [hotspotData, setHotspotData] = useState<any>(null);
  const [heatmapData, setHeatmapData] = useState<any>(null);
  const [flowData, setFlowData] = useState<any>(null);
  const [responderData, setResponderData] = useState<any>(null);
  const [escalationData, setEscalationData] = useState<any>(null);
  const [anomalyData, setAnomalyData] = useState<any>(null);
  const [modelReport, setModelReport] = useState<any>(null);
  const [forecastData, setForecastData] = useState<any>(null);
  const [recommendationsData, setRecommendationsData] = useState<any>(null);
  const [qualityData, setQualityData] = useState<any>(null);
  const [systemData, setSystemData] = useState<any>(null);
  const [metricCatalog, setMetricCatalog] = useState<any>(null);

  // Heatmap layer selection
  const [heatmapLayer, setHeatmapLayer] = useState<string>('tourist_density');
  const [forecastHorizon, setForecastHorizon] = useState<string>('next_day');

  // Export modal state
  const [exportModalVisible, setExportModalVisible] = useState<boolean>(false);
  const [exportType, setExportType] = useState<string>('incidents');
  const [exportFormat, setExportFormat] = useState<string>('csv');
  const [exportJob, setExportJob] = useState<any>(null);
  const [exportLoading, setExportLoading] = useState<boolean>(false);

  // Connection & freshness state
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  const getFilterParams = (bypass = false) => {
    return {
      time_window: timeWindow,
      timezone,
      bypass_cache: bypass,
    };
  };

  const loadAllAnalytics = async (bypass = false) => {
    try {
      if (bypass) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const params = getFilterParams(bypass);

      const [
        execRes,
        incRes,
        sftRes,
        znRes,
        hsRes,
        hmRes,
        flwRes,
        rspRes,
        escRes,
        anmRes,
        mdlRes,
        fcRes,
        recRes,
        qlRes,
        sysRes,
        catRes,
      ] = await Promise.allSettled([
        analyticsApi.getExecutive(params),
        analyticsApi.getIncidents(params),
        analyticsApi.getSafety(params),
        analyticsApi.getZones(params),
        analyticsApi.getHotspots(params),
        analyticsApi.getHeatmaps({ ...params, layer: heatmapLayer }),
        analyticsApi.getFlow(params),
        analyticsApi.getResponders(params),
        analyticsApi.getEscalations(params),
        analyticsApi.getAnomalies(params),
        analyticsApi.getModelsPerformance(),
        analyticsApi.getForecasts({ metric_name: 'incident_volume', horizon: forecastHorizon }),
        analyticsApi.getRecommendations(),
        analyticsApi.getDataQuality(),
        analyticsApi.getSystem(),
        analyticsApi.getMetricCatalog(),
      ]);

      if (execRes.status === 'fulfilled') setExecutiveData(execRes.value.data);
      if (incRes.status === 'fulfilled') setIncidentData(incRes.value.data);
      if (sftRes.status === 'fulfilled') setSafetyData(sftRes.value.data);
      if (znRes.status === 'fulfilled') setZoneData(znRes.value.data);
      if (hsRes.status === 'fulfilled') setHotspotData(hsRes.value.data);
      if (hmRes.status === 'fulfilled') setHeatmapData(hmRes.value.data);
      if (flwRes.status === 'fulfilled') setFlowData(flwRes.value.data);
      if (rspRes.status === 'fulfilled') setResponderData(rspRes.value.data);
      if (escRes.status === 'fulfilled') setEscalationData(escRes.value.data);
      if (anmRes.status === 'fulfilled') setAnomalyData(anmRes.value.data);
      if (mdlRes.status === 'fulfilled') setModelReport(mdlRes.value.data);
      if (fcRes.status === 'fulfilled') setForecastData(fcRes.value.data);
      if (recRes.status === 'fulfilled') setRecommendationsData(recRes.value.data);
      if (qlRes.status === 'fulfilled') setQualityData(qlRes.value.data);
      if (sysRes.status === 'fulfilled') setSystemData(sysRes.value.data);
      if (catRes.status === 'fulfilled') setMetricCatalog(catRes.value.data);

      setLastRefreshedAt(new Date());
      setIsOnline(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch operational intelligence');
      setIsOnline(false);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAllAnalytics(false);
  }, [timeWindow, timezone, heatmapLayer, forecastHorizon]);

  const handleCreateExport = async () => {
    try {
      setExportLoading(true);
      const res = await analyticsApi.createExport({
        export_type: exportType,
        format: exportFormat,
        filters: getFilterParams(),
      });
      setExportJob(res.data);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Export initiation failed');
    } finally {
      setExportLoading(false);
    }
  };

  const formatSeconds = (sec?: number) => {
    if (sec === undefined || sec === null) return 'N/A';
    if (sec < 60) return `${Math.round(sec)}s`;
    if (sec < 3600) return `${(sec / 60).toFixed(1)}m`;
    return `${(sec / 3600).toFixed(1)}h`;
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header & Controls Bar */}
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <View>
            <Text style={styles.title}>Authority Operational Analytics & Intelligence</Text>
            <Text style={styles.subtitle}>
              Deterministic decision support derived from real operational telemetry & incident lifecycles
            </Text>
          </View>
          <View style={styles.headerActions}>
            <View style={[styles.freshnessBadge, isOnline ? styles.freshnessOnline : styles.freshnessStale]}>
              <Radio size={14} color={isOnline ? '#10B981' : '#EF4444'} />
              <Text style={styles.freshnessText}>
                {isOnline ? 'LIVE TELEMETRY' : 'CONNECTION LOST'}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.actionBtn}
              onPress={() => loadAllAnalytics(true)}
              disabled={refreshing}
            >
              <RefreshCw size={16} color="#94A3B8" />
              <Text style={styles.actionBtnText}>{refreshing ? 'Refreshing...' : 'Refresh'}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionBtn, styles.exportBtn]}
              onPress={() => setExportModalVisible(true)}
            >
              <Download size={16} color="#FFFFFF" />
              <Text style={[styles.actionBtnText, { color: '#FFFFFF' }]}>Export</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Time Window & Timezone Filter Bar */}
        <View style={styles.filterRow}>
          <View style={styles.timeWindowGroup}>
            {(['LIVE', 'TODAY', 'LAST_24_HOURS', 'LAST_7_DAYS', 'LAST_30_DAYS'] as TimeWindowOption[]).map(
              (w) => (
                <TouchableOpacity
                  key={w}
                  style={[styles.filterChip, timeWindow === w && styles.filterChipActive]}
                  onPress={() => setTimeWindow(w)}
                >
                  <Text style={[styles.filterChipText, timeWindow === w && styles.filterChipTextActive]}>
                    {w.replace('LAST_', '').replace('_', ' ')}
                  </Text>
                </TouchableOpacity>
              )
            )}
          </View>

          <View style={styles.tzGroup}>
            <Clock size={14} color="#64748B" />
            <Text style={styles.tzText}>Timezone: {timezone}</Text>
          </View>
        </View>

        {/* Sub-Navigation Tabs */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabsScroll}>
          {[
            { id: 'executive', label: 'Executive Overview', icon: Gauge },
            { id: 'incidents', label: 'Incident Intelligence', icon: AlertTriangle },
            { id: 'safety', label: 'Safety & Risk Episodes', icon: Shield },
            { id: 'geospatial', label: 'Geospatial & Hotspots', icon: MapPinned },
            { id: 'responders', label: 'Responder Workload & SLA', icon: Users },
            { id: 'escalations', label: 'Escalation Analytics', icon: TrendingUp },
            { id: 'models', label: 'ML Models & Drift', icon: Cpu },
            { id: 'forecasting', label: 'Demand Forecasts & AI', icon: Sparkles },
            { id: 'quality', label: 'Data Quality Health', icon: CheckCircle2 },
            { id: 'system', label: 'System Health & Catalog', icon: Server },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <TouchableOpacity
                key={tab.id}
                style={[styles.tabBtn, isActive && styles.tabBtnActive]}
                onPress={() => setActiveTab(tab.id as TabType)}
              >
                <Icon size={16} color={isActive ? '#38BDF8' : '#64748B'} />
                <Text style={[styles.tabBtnText, isActive && styles.tabBtnTextActive]}>
                  {tab.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Main Body View */}
      {loading ? (
        <View style={styles.loaderContainer}>
          <ActivityIndicator size="large" color="#38BDF8" />
          <Text style={styles.loaderText}>Synthesizing canonical operational analytics...</Text>
        </View>
      ) : error ? (
        <View style={styles.errorContainer}>
          <AlertTriangle size={32} color="#EF4444" />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.actionBtn} onPress={() => loadAllAnalytics(true)}>
            <Text style={styles.actionBtnText}>Retry Analysis</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.dashboardBody}>
          {/* TAB 1: EXECUTIVE OVERVIEW */}
          {activeTab === 'executive' && (
            <View style={styles.tabContent}>
              {/* Critical KPIs 4-Card Grid */}
              <View style={styles.kpiGrid}>
                <View style={styles.kpiCard}>
                  <View style={styles.kpiIconWrapper}>
                    <Users size={20} color="#38BDF8" />
                  </View>
                  <Text style={styles.kpiValue}>{executiveData?.active_tourists ?? 0}</Text>
                  <Text style={styles.kpiLabel}>Active Tourists</Text>
                  <Text style={styles.kpiSub}>
                    {executiveData?.active_tracking_sessions ?? 0} active GPS sessions
                  </Text>
                </View>

                <View style={styles.kpiCard}>
                  <View style={[styles.kpiIconWrapper, { backgroundColor: '#7F1D1D30' }]}>
                    <AlertTriangle size={20} color="#EF4444" />
                  </View>
                  <Text style={[styles.kpiValue, { color: '#EF4444' }]}>
                    {executiveData?.active_incidents ?? 0}
                  </Text>
                  <Text style={styles.kpiLabel}>Active Incidents</Text>
                  <Text style={styles.kpiSub}>
                    {executiveData?.open_sos_count ?? 0} open SOS alerts
                  </Text>
                </View>

                <View style={styles.kpiCard}>
                  <View style={[styles.kpiIconWrapper, { backgroundColor: '#065F4630' }]}>
                    <ShieldCheck size={20} color="#10B981" />
                  </View>
                  <Text style={styles.kpiValue}>
                    {executiveData?.responders?.available_for_dispatch ?? 0} /{' '}
                    {executiveData?.responders?.active_on_shift ?? 0}
                  </Text>
                  <Text style={styles.kpiLabel}>Responders Available</Text>
                  <Text style={styles.kpiSub}>
                    {executiveData?.responders?.assigned_or_responding ?? 0} currently dispatched
                  </Text>
                </View>

                <View style={styles.kpiCard}>
                  <View style={[styles.kpiIconWrapper, { backgroundColor: '#78350F30' }]}>
                    <Clock size={20} color="#F59E0B" />
                  </View>
                  <Text style={styles.kpiValue}>
                    {formatSeconds(executiveData?.response_times?.median_seconds)}
                  </Text>
                  <Text style={styles.kpiLabel}>Median Response Time</Text>
                  <Text style={styles.kpiSub}>
                    P90: {formatSeconds(executiveData?.response_times?.p90_seconds)} (P95:{' '}
                    {formatSeconds(executiveData?.response_times?.p95_seconds)})
                  </Text>
                </View>
              </View>

              {/* Safety State Pulse & Escalation Rate Banner */}
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Jurisdiction Safety State Distribution</Text>
                <View style={styles.safetyDistributionRow}>
                  {Object.entries(executiveData?.safety_state_distribution || {}).map(
                    ([state, count]: [string, any]) => (
                      <View key={state} style={styles.stateChip}>
                        <Text style={styles.stateChipCount}>{count}</Text>
                        <Text style={styles.stateChipLabel}>{state}</Text>
                      </View>
                    )
                  )}
                </View>
                <View style={styles.metaRow}>
                  <Text style={styles.metaText}>
                    Escalation Rate:{' '}
                    <Text style={{ fontWeight: '700', color: '#F59E0B' }}>
                      {((executiveData?.escalation_rate || 0) * 100).toFixed(1)}%
                    </Text>
                  </Text>
                  <Text style={styles.metaText}>
                    System Reliability: <Text style={{ color: '#10B981' }}>{executiveData?.system_health?.status || 'GOOD'}</Text>
                  </Text>
                </View>
              </View>
            </View>
          )}

          {/* TAB 2: INCIDENT INTELLIGENCE */}
          {activeTab === 'incidents' && (
            <View style={styles.tabContent}>
              <View style={styles.kpiGrid}>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>{incidentData?.total_incidents ?? 0}</Text>
                  <Text style={styles.kpiLabel}>Total Incidents</Text>
                  <Text style={styles.kpiSub}>{incidentData?.open_incidents ?? 0} currently open</Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>{incidentData?.escalated_incidents ?? 0}</Text>
                  <Text style={styles.kpiLabel}>Escalated</Text>
                  <Text style={styles.kpiSub}>{incidentData?.sla_compliance_rate ?? 100}% within SLA</Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {formatSeconds(incidentData?.time_to_acknowledge?.median_seconds)}
                  </Text>
                  <Text style={styles.kpiLabel}>Time to Acknowledge</Text>
                  <Text style={styles.kpiSub}>
                    P95: {formatSeconds(incidentData?.time_to_acknowledge?.p95_seconds)}
                  </Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {formatSeconds(incidentData?.time_to_resolution?.median_seconds)}
                  </Text>
                  <Text style={styles.kpiLabel}>Time to Resolution</Text>
                  <Text style={styles.kpiSub}>
                    P95: {formatSeconds(incidentData?.time_to_resolution?.p95_seconds)}
                  </Text>
                </View>
              </View>

              {/* Aging Buckets & Backlog */}
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Incident Backlog Aging Analysis</Text>
                <View style={styles.agingGrid}>
                  {(incidentData?.aging_analysis?.aging_buckets || []).map((b: any) => (
                    <View key={b.bucket_label} style={styles.agingCard}>
                      <Text style={styles.agingCount}>{b.incident_count}</Text>
                      <Text style={styles.agingLabel}>{b.bucket_label}</Text>
                    </View>
                  ))}
                </View>
                {incidentData?.aging_analysis?.oldest_open_incident_id && (
                  <Text style={[styles.metaText, { marginTop: 12, color: '#EF4444' }]}>
                    Oldest open incident: #{incidentData.aging_analysis.oldest_open_incident_id} (aging{' '}
                    {incidentData.aging_analysis.oldest_open_duration_minutes} min)
                  </Text>
                )}
              </View>

              {/* Categorization Breakdown */}
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Incident Classification & Sources</Text>
                <View style={styles.breakdownGrid}>
                  <View style={styles.breakdownCol}>
                    <Text style={styles.colHeader}>By Source</Text>
                    {Object.entries(incidentData?.by_source || {}).map(([k, v]: [string, any]) => (
                      <Text key={k} style={styles.breakdownItem}>
                        {k}: <Text style={styles.bold}>{v}</Text>
                      </Text>
                    ))}
                  </View>
                  <View style={styles.breakdownCol}>
                    <Text style={styles.colHeader}>By Severity</Text>
                    {Object.entries(incidentData?.by_severity || {}).map(([k, v]: [string, any]) => (
                      <Text key={k} style={styles.breakdownItem}>
                        {k}: <Text style={styles.bold}>{v}</Text>
                      </Text>
                    ))}
                  </View>
                  <View style={styles.breakdownCol}>
                    <Text style={styles.colHeader}>By Category</Text>
                    {Object.entries(incidentData?.by_category || {}).map(([k, v]: [string, any]) => (
                      <Text key={k} style={styles.breakdownItem}>
                        {k}: <Text style={styles.bold}>{v}</Text>
                      </Text>
                    ))}
                  </View>
                </View>
              </View>
            </View>
          )}

          {/* TAB 3: SAFETY & RISK INTELLIGENCE */}
          {activeTab === 'safety' && (
            <View style={styles.tabContent}>
              <View style={styles.kpiGrid}>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>{safetyData?.risk_episodes?.total_episodes ?? 0}</Text>
                  <Text style={styles.kpiLabel}>Risk Episodes</Text>
                  <Text style={styles.kpiSub}>
                    {safetyData?.risk_episodes?.active_episodes ?? 0} active now
                  </Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((safetyData?.risk_episodes?.peak_risk_avg || 0) * 100).toFixed(0)}%
                  </Text>
                  <Text style={styles.kpiLabel}>Avg Peak Risk</Text>
                  <Text style={styles.kpiSub}>
                    Avg Conf: {((safetyData?.risk_episodes?.peak_confidence_avg || 0) * 100).toFixed(0)}%
                  </Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((safetyData?.risk_episodes?.recovery_rate || 0) * 100).toFixed(1)}%
                  </Text>
                  <Text style={styles.kpiLabel}>Recovery Rate</Text>
                  <Text style={styles.kpiSub}>Cleared without escalation</Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((safetyData?.unknown_state_rate || 0) * 100).toFixed(2)}%
                  </Text>
                  <Text style={styles.kpiLabel}>UNKNOWN State Rate</Text>
                  <Text style={styles.kpiSub}>Core system reliability indicator</Text>
                </View>
              </View>

              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Unknown State Root Causes</Text>
                {Object.entries(safetyData?.unknown_state_causes || {}).map(([cause, cnt]: [string, any]) => (
                  <View key={cause} style={styles.causeRow}>
                    <Text style={styles.causeText}>{cause}</Text>
                    <Text style={styles.causeCount}>{cnt} events</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* TAB 4: GEOSPATIAL INTELLIGENCE & HOTSPOTS */}
          {activeTab === 'geospatial' && (
            <View style={styles.tabContent}>
              <View style={styles.sectionCard}>
                <View style={styles.cardHeaderRow}>
                  <Text style={styles.sectionTitle}>Operational Hotspot Clusters</Text>
                  <Text style={styles.metaText}>
                    Overall Hotspot Density: {hotspotData?.hotspot_density_score ?? 0}
                  </Text>
                </View>

                {(hotspotData?.hotspots || []).map((h: any) => (
                  <View key={h.cluster_id} style={styles.hotspotItem}>
                    <View>
                      <Text style={styles.hotspotTitle}>
                        Cluster {h.cluster_id} ({h.primary_incident_type})
                      </Text>
                      <Text style={styles.hotspotSub}>
                        Lat: {h.latitude.toFixed(4)}, Lon: {h.longitude.toFixed(4)} | Zone: {h.zone_name || 'General Area'}
                      </Text>
                    </View>
                    <View style={styles.hotspotScoreBox}>
                      <Text style={styles.hotspotScore}>{h.intensity_score}</Text>
                      <Text style={styles.hotspotScoreLabel}>Intensity</Text>
                    </View>
                  </View>
                ))}
              </View>

              {/* Tourist Flow Corridors */}
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Key Zone Movement Corridors</Text>
                {(flowData?.edges || []).slice(0, 5).map((edge: any, idx: number) => (
                  <View key={idx} style={styles.flowRow}>
                    <Text style={styles.flowEdge}>
                      {edge.from_zone_name} → {edge.to_zone_name}
                    </Text>
                    <Text style={styles.flowTransitions}>{edge.transition_count} transitions</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* TAB 5: RESPONDER & SLA PERFORMANCE */}
          {activeTab === 'responders' && (
            <View style={styles.tabContent}>
              <View style={styles.kpiGrid}>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((responderData?.acceptance_rate || 0) * 100).toFixed(1)}%
                  </Text>
                  <Text style={styles.kpiLabel}>Acceptance Rate</Text>
                  <Text style={styles.kpiSub}>
                    Rejections: {((responderData?.rejection_rate || 0) * 100).toFixed(1)}%
                  </Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((responderData?.utilization_rate || 0) * 100).toFixed(1)}%
                  </Text>
                  <Text style={styles.kpiLabel}>Utilization Rate</Text>
                  <Text style={styles.kpiSub}>Active vs assigned ratio</Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {formatSeconds(responderData?.median_response_time_seconds)}
                  </Text>
                  <Text style={styles.kpiLabel}>Response Time</Text>
                  <Text style={styles.kpiSub}>
                    P90: {formatSeconds(responderData?.p90_response_time_seconds)}
                  </Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {formatSeconds(responderData?.p50_arrival_time_seconds)}
                  </Text>
                  <Text style={styles.kpiLabel}>Arrival Time</Text>
                  <Text style={styles.kpiSub}>
                    P90: {formatSeconds(responderData?.p90_arrival_time_seconds)}
                  </Text>
                </View>
              </View>

              {/* Capability Demand Breakdown */}
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Capability Demand Breakdown</Text>
                {Object.entries(responderData?.capability_demand || {}).map(([cap, cnt]: [string, any]) => (
                  <View key={cap} style={styles.causeRow}>
                    <Text style={styles.causeText}>{cap}</Text>
                    <Text style={styles.causeCount}>{cnt} dispatches</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* TAB 6: ESCALATION ANALYTICS */}
          {activeTab === 'escalations' && (
            <View style={styles.tabContent}>
              <View style={styles.kpiGrid}>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>{escalationData?.total_escalated_incidents ?? 0}</Text>
                  <Text style={styles.kpiLabel}>Total Escalated</Text>
                  <Text style={styles.kpiSub}>
                    Out of {escalationData?.total_eligible_incidents ?? 0} eligible incidents
                  </Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((escalationData?.escalation_rate || 0) * 100).toFixed(1)}%
                  </Text>
                  <Text style={styles.kpiLabel}>Escalation Rate</Text>
                  <Text style={styles.kpiSub}>Incident escalation frequency</Text>
                </View>
                <View style={styles.kpiCard}>
                  <Text style={styles.kpiValue}>
                    {((escalationData?.resolution_post_escalation_rate || 0) * 100).toFixed(1)}%
                  </Text>
                  <Text style={styles.kpiLabel}>Post-Escalation Resolution</Text>
                  <Text style={styles.kpiSub}>Resolved successfully</Text>
                </View>
              </View>

              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Escalation Level Distribution</Text>
                {(escalationData?.levels || []).map((lvl: any) => (
                  <View key={lvl.level} style={styles.causeRow}>
                    <Text style={styles.causeText}>{lvl.level_name}</Text>
                    <Text style={styles.causeCount}>{lvl.count} incidents</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* TAB 7: ML MODELS & DRIFT */}
          {activeTab === 'models' && (
            <View style={styles.tabContent}>
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Active Production ML Models</Text>
                {(modelReport?.active_production_models || []).map((m: any) => (
                  <View key={m.model_version} style={styles.modelCard}>
                    <View style={styles.cardHeaderRow}>
                      <Text style={styles.modelTitle}>{m.model_version}</Text>
                      <View style={[styles.statusTag, { backgroundColor: '#065F4630' }]}>
                        <Text style={[styles.statusTagText, { color: '#10B981' }]}>{m.status}</Text>
                      </View>
                    </View>
                    <View style={styles.modelMetricsGrid}>
                      <Text style={styles.metaText}>Precision: {((m.precision || 0) * 100).toFixed(1)}%</Text>
                      <Text style={styles.metaText}>Recall: {((m.recall || 0) * 100).toFixed(1)}%</Text>
                      <Text style={styles.metaText}>F1-Score: {((m.f1_score || 0) * 100).toFixed(1)}%</Text>
                      <Text style={styles.metaText}>ROC-AUC: {((m.roc_auc || 0) * 100).toFixed(1)}%</Text>
                      <Text style={styles.metaText}>P95 Latency: {m.inference_latency_p95_ms}ms</Text>
                      <Text style={styles.metaText}>
                        Drift: {m.drift_detected ? 'DRIFT DETECTED' : 'NO DRIFT'}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* TAB 8: FORECASTING & RECOMMENDATIONS */}
          {activeTab === 'forecasting' && (
            <View style={styles.tabContent}>
              <View style={styles.sectionCard}>
                <View style={styles.cardHeaderRow}>
                  <Text style={styles.sectionTitle}>Demand Forecast & Resource Pressure</Text>
                  <View style={styles.horizonGroup}>
                    {['next_hour', 'next_day', 'next_week'].map((h) => (
                      <TouchableOpacity
                        key={h}
                        style={[styles.filterChip, forecastHorizon === h && styles.filterChipActive]}
                        onPress={() => setForecastHorizon(h)}
                      >
                        <Text style={[styles.filterChipText, forecastHorizon === h && styles.filterChipTextActive]}>
                          {h.replace('_', ' ')}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                {forecastData?.status === 'INSUFFICIENT_DATA' ? (
                  <View style={styles.insufficientDataBox}>
                    <Info size={20} color="#F59E0B" />
                    <Text style={styles.insufficientDataText}>{forecastData.message}</Text>
                  </View>
                ) : (
                  <View>
                    <View style={styles.metaRow}>
                      <Text style={styles.metaText}>
                        Resource Pressure:{' '}
                        <Text style={{ fontWeight: '700', color: '#10B981' }}>
                          {forecastData?.resource_pressure_level || 'NORMAL'}
                        </Text>
                      </Text>
                      <Text style={styles.metaText}>
                        Peak Expected Demand: {forecastData?.expected_peak_demand} incidents
                      </Text>
                    </View>

                    <View style={styles.forecastList}>
                      {(forecastData?.forecast_points || []).map((pt: any, idx: number) => (
                        <View key={idx} style={styles.forecastItem}>
                          <Text style={styles.forecastTime}>{pt.timestamp.split('T')[1] || pt.timestamp}</Text>
                          <Text style={styles.forecastValue}>{pt.predicted_value} exp</Text>
                          <Text style={styles.forecastInterval}>
                            [{pt.lower_bound_p10} – {pt.upper_bound_p90}] (80% CI)
                          </Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}
              </View>

              {/* Operational Recommendations */}
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Explainable Operational Recommendations</Text>
                {(recommendationsData?.recommendations || []).map((r: any) => (
                  <View key={r.recommendation_id} style={styles.recCard}>
                    <View style={styles.cardHeaderRow}>
                      <Text style={styles.recTitle}>{r.title}</Text>
                      <View
                        style={[
                          styles.statusTag,
                          { backgroundColor: r.urgency === 'HIGH' ? '#7F1D1D30' : '#78350F30' },
                        ]}
                      >
                        <Text
                          style={[
                            styles.statusTagText,
                            { color: r.urgency === 'HIGH' ? '#EF4444' : '#F59E0B' },
                          ]}
                        >
                          {r.urgency} URGENCY
                        </Text>
                      </View>
                    </View>
                    <Text style={styles.recObservation}>
                      <Text style={styles.bold}>Observation: </Text>
                      {r.observation}
                    </Text>
                    <Text style={styles.recEvidence}>
                      <Text style={styles.bold}>Evidence: </Text>
                      {r.evidence}
                    </Text>
                    <Text style={styles.recAction}>
                      <Text style={styles.bold}>Suggested Action: </Text>
                      {r.possible_action}
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* TAB 9: DATA QUALITY HEALTH */}
          {activeTab === 'quality' && (
            <View style={styles.tabContent}>
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Data Quality Score: {qualityData?.composite_quality_score ?? 100}%</Text>
                <View style={styles.qualityList}>
                  {[
                    qualityData?.gps_quality,
                    qualityData?.telemetry_quality,
                    qualityData?.imu_quality,
                    qualityData?.device_health,
                    qualityData?.ml_inference_quality,
                    qualityData?.notification_delivery_health,
                  ]
                    .filter(Boolean)
                    .map((q: any, idx: number) => (
                      <View key={idx} style={styles.causeRow}>
                        <Text style={styles.causeText}>{q.domain}</Text>
                        <Text style={[styles.causeCount, { color: '#10B981' }]}>{q.score}% ({q.status})</Text>
                      </View>
                    ))}
                </View>
              </View>
            </View>
          )}

          {/* TAB 10: SYSTEM HEALTH & CATALOG */}
          {activeTab === 'system' && (
            <View style={styles.tabContent}>
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>System Performance & Microservices</Text>
                <View style={styles.breakdownGrid}>
                  <View style={styles.breakdownCol}>
                    <Text style={styles.colHeader}>Latency (ms)</Text>
                    <Text style={styles.breakdownItem}>API P50: {systemData?.api_p50_ms}ms</Text>
                    <Text style={styles.breakdownItem}>API P95: {systemData?.api_p95_ms}ms</Text>
                    <Text style={styles.breakdownItem}>DB Query P95: {systemData?.db_query_p95_ms}ms</Text>
                    <Text style={styles.breakdownItem}>Redis: {systemData?.redis_latency_ms}ms</Text>
                  </View>
                  <View style={styles.breakdownCol}>
                    <Text style={styles.colHeader}>Services Status</Text>
                    {Object.entries(systemData?.services_status || {}).map(([s, st]: [string, any]) => (
                      <Text key={s} style={styles.breakdownItem}>
                        {s}: <Text style={{ color: '#10B981' }}>{st}</Text>
                      </Text>
                    ))}
                  </View>
                </View>
              </View>

              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>Analytical Metric Catalog</Text>
                {(metricCatalog?.metrics || []).map((m: any) => (
                  <View key={m.metric_key} style={styles.catalogItem}>
                    <Text style={styles.catalogName}>{m.name} ({m.metric_key})</Text>
                    <Text style={styles.catalogDef}>{m.definition}</Text>
                    <Text style={styles.catalogFormula}>Formula: {m.formula}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
        </View>
      )}

      {/* Export Modal */}
      <Modal visible={exportModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>Initiate Analytical Data Export</Text>
            <Text style={styles.modalSub}>
              Exports are authenticated, PII-redacted, and logged to the analytics audit trail.
            </Text>

            <View style={styles.modalGroup}>
              <Text style={styles.modalLabel}>Export Domain Dataset</Text>
              <View style={styles.modalChoices}>
                {['incidents', 'zones', 'responders', 'escalations'].map((t) => (
                  <TouchableOpacity
                    key={t}
                    style={[styles.modalChoiceBtn, exportType === t && styles.modalChoiceBtnActive]}
                    onPress={() => setExportType(t)}
                  >
                    <Text
                      style={[
                        styles.modalChoiceBtnText,
                        exportType === t && styles.modalChoiceBtnTextActive,
                      ]}
                    >
                      {t.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={styles.modalGroup}>
              <Text style={styles.modalLabel}>File Format</Text>
              <View style={styles.modalChoices}>
                {['csv', 'json', 'pdf'].map((f) => (
                  <TouchableOpacity
                    key={f}
                    style={[styles.modalChoiceBtn, exportFormat === f && styles.modalChoiceBtnActive]}
                    onPress={() => setExportFormat(f)}
                  >
                    <Text
                      style={[
                        styles.modalChoiceBtnText,
                        exportFormat === f && styles.modalChoiceBtnTextActive,
                      ]}
                    >
                      {f.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {exportJob && (
              <View style={styles.exportResultBox}>
                <Text style={styles.metaText}>Export Job Status: {exportJob.status}</Text>
                {exportJob.download_url && (
                  <Text style={[styles.metaText, { color: '#38BDF8', marginTop: 4 }]}>
                    Download Ready: {exportJob.file_reference} ({exportJob.record_count} records)
                  </Text>
                )}
              </View>
            )}

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => {
                  setExportModalVisible(false);
                  setExportJob(null);
                }}
              >
                <Text style={styles.modalCloseBtnText}>Close</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSubmitBtn}
                onPress={handleCreateExport}
                disabled={exportLoading}
              >
                <Text style={styles.modalSubmitBtnText}>
                  {exportLoading ? 'Generating...' : 'Generate Export'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  content: {
    padding: 20,
    paddingBottom: 60,
  },
  header: {
    marginBottom: 20,
  },
  headerTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: '#F8FAFC',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 13,
    color: '#94A3B8',
    marginTop: 4,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  freshnessBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    gap: 6,
  },
  freshnessOnline: {
    backgroundColor: '#065F4625',
    borderColor: '#10B98140',
    borderWidth: 1,
  },
  freshnessStale: {
    backgroundColor: '#7F1D1D25',
    borderColor: '#EF444440',
    borderWidth: 1,
  },
  freshnessText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#E2E8F0',
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    gap: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  actionBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#94A3B8',
  },
  exportBtn: {
    backgroundColor: '#0284C7',
    borderColor: '#38BDF8',
  },
  filterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
    flexWrap: 'wrap',
    gap: 12,
  },
  timeWindowGroup: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  filterChip: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  filterChipActive: {
    backgroundColor: '#0284C7',
    borderColor: '#38BDF8',
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#94A3B8',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
  },
  tzGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  tzText: {
    fontSize: 12,
    color: '#64748B',
  },
  tabsScroll: {
    marginTop: 16,
  },
  tabBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
    marginRight: 8,
    gap: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  tabBtnActive: {
    backgroundColor: '#0F172A',
    borderColor: '#38BDF8',
  },
  tabBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748B',
  },
  tabBtnTextActive: {
    color: '#38BDF8',
  },
  loaderContainer: {
    padding: 60,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loaderText: {
    fontSize: 14,
    color: '#94A3B8',
    marginTop: 12,
  },
  errorContainer: {
    padding: 40,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  errorText: {
    fontSize: 14,
    color: '#EF4444',
    textAlign: 'center',
  },
  dashboardBody: {
    marginTop: 10,
  },
  tabContent: {
    gap: 16,
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  kpiCard: {
    flex: 1,
    minWidth: 200,
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  kpiIconWrapper: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#0284C720',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  kpiValue: {
    fontSize: 26,
    fontWeight: '800',
    color: '#F8FAFC',
    letterSpacing: -0.5,
  },
  kpiLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#94A3B8',
    marginTop: 2,
  },
  kpiSub: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 4,
  },
  sectionCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 18,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#F8FAFC',
    marginBottom: 12,
  },
  safetyDistributionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  stateChip: {
    backgroundColor: '#0F172A',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
  },
  stateChipCount: {
    fontSize: 16,
    fontWeight: '800',
    color: '#38BDF8',
  },
  stateChipLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#94A3B8',
    marginTop: 2,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 14,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#334155',
  },
  metaText: {
    fontSize: 12,
    color: '#94A3B8',
  },
  agingGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  agingCard: {
    flex: 1,
    minWidth: 100,
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
  },
  agingCount: {
    fontSize: 20,
    fontWeight: '800',
    color: '#F8FAFC',
  },
  agingLabel: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 2,
  },
  breakdownGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
  },
  breakdownCol: {
    flex: 1,
    minWidth: 160,
  },
  colHeader: {
    fontSize: 13,
    fontWeight: '700',
    color: '#38BDF8',
    marginBottom: 8,
  },
  breakdownItem: {
    fontSize: 12,
    color: '#CBD5E1',
    marginBottom: 4,
  },
  bold: {
    fontWeight: '700',
    color: '#F8FAFC',
  },
  causeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  causeText: {
    fontSize: 13,
    color: '#E2E8F0',
  },
  causeCount: {
    fontSize: 13,
    fontWeight: '700',
    color: '#94A3B8',
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  hotspotItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  hotspotTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  hotspotSub: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  hotspotScoreBox: {
    alignItems: 'center',
  },
  hotspotScore: {
    fontSize: 16,
    fontWeight: '800',
    color: '#EF4444',
  },
  hotspotScoreLabel: {
    fontSize: 10,
    color: '#64748B',
  },
  flowRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  flowEdge: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E2E8F0',
  },
  flowTransitions: {
    fontSize: 13,
    fontWeight: '700',
    color: '#38BDF8',
  },
  modelCard: {
    backgroundColor: '#0F172A',
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 10,
  },
  modelTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  statusTag: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusTagText: {
    fontSize: 10,
    fontWeight: '700',
  },
  modelMetricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 8,
  },
  horizonGroup: {
    flexDirection: 'row',
    gap: 6,
  },
  insufficientDataBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#78350F25',
    padding: 12,
    borderRadius: 8,
    gap: 10,
    borderWidth: 1,
    borderColor: '#F59E0B40',
  },
  insufficientDataText: {
    fontSize: 13,
    color: '#FCD34D',
    flex: 1,
  },
  forecastList: {
    marginTop: 10,
    gap: 6,
  },
  forecastItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  forecastTime: {
    fontSize: 12,
    color: '#94A3B8',
  },
  forecastValue: {
    fontSize: 12,
    fontWeight: '700',
    color: '#38BDF8',
  },
  forecastInterval: {
    fontSize: 11,
    color: '#64748B',
  },
  recCard: {
    backgroundColor: '#0F172A',
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 10,
  },
  recTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  recObservation: {
    fontSize: 12,
    color: '#CBD5E1',
    marginTop: 6,
  },
  recEvidence: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 2,
  },
  recAction: {
    fontSize: 12,
    color: '#38BDF8',
    marginTop: 4,
  },
  qualityList: {
    gap: 4,
  },
  catalogItem: {
    backgroundColor: '#0F172A',
    padding: 10,
    borderRadius: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  catalogName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#38BDF8',
  },
  catalogDef: {
    fontSize: 12,
    color: '#CBD5E1',
    marginTop: 2,
  },
  catalogFormula: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  modalBox: {
    width: '100%',
    maxWidth: 500,
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#F8FAFC',
  },
  modalSub: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 4,
    marginBottom: 16,
  },
  modalGroup: {
    marginBottom: 14,
  },
  modalLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#CBD5E1',
    marginBottom: 6,
  },
  modalChoices: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  modalChoiceBtn: {
    backgroundColor: '#0F172A',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalChoiceBtnActive: {
    backgroundColor: '#0284C7',
    borderColor: '#38BDF8',
  },
  modalChoiceBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#94A3B8',
  },
  modalChoiceBtnTextActive: {
    color: '#FFFFFF',
  },
  exportResultBox: {
    backgroundColor: '#0F172A',
    padding: 12,
    borderRadius: 6,
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 16,
  },
  modalCloseBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: '#334155',
  },
  modalCloseBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E2E8F0',
  },
  modalSubmitBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: '#0284C7',
  },
  modalSubmitBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
