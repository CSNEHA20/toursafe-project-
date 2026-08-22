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
} from 'lucide-react-native';
import { analyticsApi } from '@/lib/api';

type TabType = 'overview' | 'incidents' | 'zones' | 'anomalies' | 'responders' | 'quality' | 'exports';
type DateRangeOption = '24h' | '7d' | '30d';
type GranularityOption = 'hour' | 'day' | 'week' | 'month';

export default function AdminAnalyticsDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [dateRange, setDateRange] = useState<DateRangeOption>('7d');
  const [granularity, setGranularity] = useState<GranularityOption>('day');
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Analytical State Datasets
  const [overviewData, setOverviewData] = useState<any>(null);
  const [incidentData, setIncidentData] = useState<any>(null);
  const [zoneData, setZoneData] = useState<any>(null);
  const [heatmapData, setHeatmapData] = useState<any>(null);
  const [anomalyData, setAnomalyData] = useState<any>(null);
  const [responderData, setResponderData] = useState<any>(null);
  const [qualityData, setQualityData] = useState<any>(null);

  // Export Modal State
  const [exportModalVisible, setExportModalVisible] = useState<boolean>(false);
  const [exportType, setExportType] = useState<string>('incidents');
  const [exportFormat, setExportFormat] = useState<string>('csv');
  const [exportJob, setExportJob] = useState<any>(null);
  const [exportLoading, setExportLoading] = useState<boolean>(false);

  // Heatmap Layer Selection
  const [heatmapLayer, setHeatmapLayer] = useState<string>('tourist_density');

  const getDateRangeParams = () => {
    const now = new Date();
    let start = new Date();
    if (dateRange === '24h') {
      start.setHours(now.getHours() - 24);
    } else if (dateRange === '30d') {
      start.setDate(now.getDate() - 30);
    } else {
      start.setDate(now.getDate() - 7);
    }
    return {
      start_time: start.toISOString(),
      end_time: now.toISOString(),
      granularity,
    };
  };

  const loadAllAnalytics = async (bypass = false) => {
    try {
      if (bypass) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const params = { ...getDateRangeParams(), bypass_cache: bypass };

      const [ovRes, incRes, znRes, hmRes, anRes, rpRes, qlRes] = await Promise.allSettled([
        analyticsApi.getOverview(params),
        analyticsApi.getIncidents(params),
        analyticsApi.getZones(params),
        analyticsApi.getHeatmaps({ ...params, layer: heatmapLayer }),
        analyticsApi.getAnomalies(params),
        analyticsApi.getResponders(params),
        analyticsApi.getDataQuality(),
      ]);

      if (ovRes.status === 'fulfilled') setOverviewData(ovRes.value.data);
      if (incRes.status === 'fulfilled') setIncidentData(incRes.value.data);
      if (znRes.status === 'fulfilled') setZoneData(znRes.value.data);
      if (hmRes.status === 'fulfilled') setHeatmapData(hmRes.value.data);
      if (anRes.status === 'fulfilled') setAnomalyData(anRes.value.data);
      if (rpRes.status === 'fulfilled') setResponderData(rpRes.value.data);
      if (qlRes.status === 'fulfilled') setQualityData(qlRes.value.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch operational analytics');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAllAnalytics(false);
  }, [dateRange, granularity, heatmapLayer]);

  const handleCreateExport = async () => {
    try {
      setExportLoading(true);
      const res = await analyticsApi.createExport({
        export_type: exportType,
        format: exportFormat,
        filters: getDateRangeParams(),
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
            <Text style={styles.title}>Authority Intelligence & Safety Analytics</Text>
            <Text style={styles.subtitle}>
              Authoritative decision support derived from real operational records
            </Text>
          </View>
          <View style={styles.headerActions}>
            <TouchableOpacity
              style={styles.exportBtn}
              onPress={() => setExportModalVisible(true)}
            >
              <Download size={14} color="#0f766e" />
              <Text style={styles.exportBtnText}>Export Data</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.refreshBtn, refreshing && styles.refreshBtnActive]}
              onPress={() => loadAllAnalytics(true)}
              disabled={refreshing}
            >
              <RefreshCw size={14} color="#334155" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Filter Controls Row */}
        <View style={styles.filterRow}>
          <View style={styles.filterGroup}>
            <Text style={styles.filterLabel}>Range:</Text>
            {(['24h', '7d', '30d'] as DateRangeOption[]).map((r) => (
              <TouchableOpacity
                key={r}
                style={[styles.filterChip, dateRange === r && styles.filterChipActive]}
                onPress={() => setDateRange(r)}
              >
                <Text style={[styles.filterChipText, dateRange === r && styles.filterChipTextActive]}>
                  {r.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.filterGroup}>
            <Text style={styles.filterLabel}>Granularity:</Text>
            {(['hour', 'day', 'week', 'month'] as GranularityOption[]).map((g) => (
              <TouchableOpacity
                key={g}
                style={[styles.filterChip, granularity === g && styles.filterChipActive]}
                onPress={() => setGranularity(g)}
              >
                <Text style={[styles.filterChipText, granularity === g && styles.filterChipTextActive]}>
                  {g.charAt(0).toUpperCase() + g.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Freshness Badge */}
          <View style={styles.freshnessBadge}>
            <View style={styles.freshnessDot} />
            <Text style={styles.freshnessText}>
              {overviewData?.freshness?.is_cached ? 'Cached' : 'Live Canonical Pipeline'}
            </Text>
          </View>
        </View>
      </View>

      {/* Top Level Operational KPI Row */}
      <View style={styles.kpiRow}>
        <KpiCard
          icon={<Users size={16} color="#1a365d" />}
          label="Active Tourists"
          value={overviewData ? `${overviewData.active_tourists}` : '—'}
          subtext="Currently tracked"
        />
        <KpiCard
          icon={<ShieldAlert size={16} color="#dc2626" />}
          label="Open Incidents"
          value={overviewData ? `${overviewData.open_incidents}` : '—'}
          subtext="Active emergency ops"
          alert={overviewData?.open_incidents > 0}
        />
        <KpiCard
          icon={<Clock size={16} color="#0d9488" />}
          label="Median Response (P50)"
          value={formatSeconds(overviewData?.median_response_time_seconds)}
          subtext={`P90: ${formatSeconds(overviewData?.p90_response_time_seconds)}`}
        />
        <KpiCard
          icon={<AlertTriangle size={16} color="#b45309" />}
          label="SOS Alerts Today"
          value={overviewData ? `${overviewData.sos_events_today}` : '—'}
          subtext="Manual SOS triggers"
        />
        <KpiCard
          icon={<ShieldCheck size={16} color="#059669" />}
          label="Data Quality"
          value={qualityData?.overall_health || 'GOOD'}
          subtext="Sensor & pipeline health"
        />
      </View>

      {/* Navigation Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar}>
        <TabButton label="Operations Overview" icon={<Gauge size={14} />} active={activeTab === 'overview'} onPress={() => setActiveTab('overview')} />
        <TabButton label="Incidents & SLA" icon={<ShieldAlert size={14} />} active={activeTab === 'incidents'} onPress={() => setActiveTab('incidents')} />
        <TabButton label="Zones & Heatmap" icon={<MapPinned size={14} />} active={activeTab === 'zones'} onPress={() => setActiveTab('zones')} />
        <TabButton label="Anomaly Intelligence" icon={<Zap size={14} />} active={activeTab === 'anomalies'} onPress={() => setActiveTab('anomalies')} />
        <TabButton label="Responder Operations" icon={<Users size={14} />} active={activeTab === 'responders'} onPress={() => setActiveTab('responders')} />
        <TabButton label="Data Quality" icon={<ShieldCheck size={14} />} active={activeTab === 'quality'} onPress={() => setActiveTab('quality')} />
      </ScrollView>

      {loading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#0d9488" />
          <Text style={styles.loadingBoxText}>Computing canonical aggregations...</Text>
        </View>
      ) : error ? (
        <View style={styles.errorBox}>
          <AlertTriangle size={24} color="#dc2626" />
          <Text style={styles.errorBoxTitle}>Analytics Temporarily Unavailable</Text>
          <Text style={styles.errorBoxDesc}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => loadAllAnalytics(true)}>
            <Text style={styles.retryBtnText}>Retry Aggregation</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          {/* TAB 1: OPERATIONS OVERVIEW */}
          {activeTab === 'overview' && (
            <View style={styles.tabContent}>
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Incident Volume Over Time</Text>
                <Text style={styles.panelSubtitle}>Aggregated chronological incident distribution</Text>
                {overviewData?.incident_trend?.length > 0 ? (
                  <View style={styles.trendList}>
                    {overviewData.incident_trend.map((pt: any) => (
                      <View key={pt.timestamp} style={styles.trendRow}>
                        <Text style={styles.trendLabel}>{pt.timestamp.slice(5, 16).replace('T', ' ')}</Text>
                        <View style={styles.barTrack}>
                          <View
                            style={[
                              styles.barFill,
                              { width: `${Math.min(100, (pt.count / Math.max(1, ...overviewData.incident_trend.map((x: any) => x.count))) * 100)}%` },
                            ]}
                          />
                        </View>
                        <Text style={styles.trendVal}>{pt.count}</Text>
                      </View>
                    ))}
                  </View>
                ) : (
                  <EmptyState text="No incident events recorded in this time window." />
                )}
              </View>

              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Safety State Distribution</Text>
                <Text style={styles.panelSubtitle}>TourSafe deterministic safety engine state records</Text>
                {overviewData?.safety_state_distribution && Object.keys(overviewData.safety_state_distribution).length > 0 ? (
                  <View style={styles.stateGrid}>
                    {Object.entries(overviewData.safety_state_distribution).map(([st, cnt]: [string, any]) => (
                      <View key={st} style={styles.stateCard}>
                        <Text style={styles.stateCardLabel}>{st}</Text>
                        <Text style={styles.stateCardVal}>{cnt}</Text>
                      </View>
                    ))}
                  </View>
                ) : (
                  <EmptyState text="No safety state transitions evaluated yet." />
                )}
              </View>
            </View>
          )}

          {/* TAB 2: INCIDENTS & SLA */}
          {activeTab === 'incidents' && (
            <View style={styles.tabContent}>
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Incident Response Lifecycle Percentiles</Text>
                <Text style={styles.panelSubtitle}>
                  Authoritative duration percentiles from incident initiation to resolution
                </Text>
                <View style={styles.percentileTable}>
                  <LifecycleRow label="Time to Acknowledge" metrics={incidentData?.time_to_acknowledge} />
                  <LifecycleRow label="Time to Assign" metrics={incidentData?.time_to_assign} />
                  <LifecycleRow label="Time to Response" metrics={incidentData?.time_to_response} />
                  <LifecycleRow label="Time to Arrival" metrics={incidentData?.time_to_arrival} />
                  <LifecycleRow label="Time to Resolution" metrics={incidentData?.time_to_resolution} />
                </View>
              </View>

              <View style={styles.panelRow}>
                <View style={[styles.panel, { flex: 1 }]}>
                  <Text style={styles.panelTitle}>SLA Target Compliance</Text>
                  <Text style={styles.panelSubtitle}>Target: &le; 15 minutes resolution</Text>
                  <View style={styles.slaBox}>
                    <Text style={styles.slaRate}>
                      {incidentData?.sla_compliance_rate !== null && incidentData?.sla_compliance_rate !== undefined
                        ? `${incidentData.sla_compliance_rate}%`
                        : 'N/A'}
                    </Text>
                    <Text style={styles.slaDetails}>
                      {incidentData?.within_sla_count || 0} within SLA · {incidentData?.outside_sla_count || 0} outside SLA
                    </Text>
                  </View>
                </View>

                <View style={[styles.panel, { flex: 1 }]}>
                  <Text style={styles.panelTitle}>False Alarm Rate</Text>
                  <Text style={styles.panelSubtitle}>Classified upon on-scene verification</Text>
                  <View style={styles.slaBox}>
                    <Text style={[styles.slaRate, { color: '#0f766e' }]}>
                      {incidentData ? `${(incidentData.false_alarm_rate * 100).toFixed(1)}%` : '0%'}
                    </Text>
                    <Text style={styles.slaDetails}>
                      {incidentData?.false_alarms || 0} false alarms of {incidentData?.total_incidents || 0} total
                    </Text>
                  </View>
                </View>
              </View>

              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Incidents by Source & Severity</Text>
                <View style={styles.sourceGrid}>
                  <View style={styles.subCol}>
                    <Text style={styles.subColTitle}>By Source</Text>
                    {incidentData?.by_source && Object.keys(incidentData.by_source).length > 0 ? (
                      Object.entries(incidentData.by_source).map(([k, v]: [string, any]) => (
                        <View key={k} style={styles.metaRow}>
                          <Text style={styles.metaLabel}>{k}</Text>
                          <Text style={styles.metaVal}>{v}</Text>
                        </View>
                      ))
                    ) : (
                      <Text style={styles.emptyInline}>No source records</Text>
                    )}
                  </View>
                  <View style={styles.subCol}>
                    <Text style={styles.subColTitle}>By Severity</Text>
                    {incidentData?.by_severity && Object.keys(incidentData.by_severity).length > 0 ? (
                      Object.entries(incidentData.by_severity).map(([k, v]: [string, any]) => (
                        <View key={k} style={styles.metaRow}>
                          <Text style={styles.metaLabel}>{k}</Text>
                          <Text style={styles.metaVal}>{v}</Text>
                        </View>
                      ))
                    ) : (
                      <Text style={styles.emptyInline}>No severity records</Text>
                    )}
                  </View>
                </View>
              </View>
            </View>
          )}

          {/* TAB 3: ZONES & SPATIAL HEATMAP */}
          {activeTab === 'zones' && (
            <View style={styles.tabContent}>
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Spatial Grid Heatmap (Privacy Protected)</Text>
                <Text style={styles.panelSubtitle}>
                  Cells with fewer than 3 unique tourists are automatically suppressed for privacy.
                </Text>

                {/* Heatmap Layer Selector */}
                <View style={styles.layerRow}>
                  {[
                    { id: 'tourist_density', label: 'Tourist Density' },
                    { id: 'incidents', label: 'Incidents' },
                    { id: 'sos_events', label: 'SOS Alerts' },
                    { id: 'anomalies', label: 'Anomalies' },
                    { id: 'response_activity', label: 'Responder Ops' },
                  ].map((l) => (
                    <TouchableOpacity
                      key={l.id}
                      style={[styles.layerChip, heatmapLayer === l.id && styles.layerChipActive]}
                      onPress={() => setHeatmapLayer(l.id)}
                    >
                      <Text style={[styles.layerChipText, heatmapLayer === l.id && styles.layerChipTextActive]}>
                        {l.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {heatmapData?.cells?.length > 0 ? (
                  <View style={styles.heatmapList}>
                    {heatmapData.cells.slice(0, 8).map((cell: any, idx: number) => (
                      <View key={cell.geohash || idx} style={styles.heatRow}>
                        <View style={styles.heatGeohash}>
                          <Text style={styles.heatGeohashText}>Grid {cell.geohash}</Text>
                          <Text style={styles.heatCoordText}>
                            [{cell.latitude}, {cell.longitude}]
                          </Text>
                        </View>
                        {cell.is_suppressed ? (
                          <View style={styles.suppressedBadge}>
                            <Text style={styles.suppressedText}>Suppressed (&lt;3 samples)</Text>
                          </View>
                        ) : (
                          <View style={styles.heatScoreWrap}>
                            <Text style={styles.heatScore}>{cell.sample_count} events</Text>
                          </View>
                        )}
                      </View>
                    ))}
                  </View>
                ) : (
                  <EmptyState text="No spatial coordinates found for selected layer and time range." />
                )}
              </View>

              {/* Zone Risk & Dwell Table */}
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Active Safety Zones & Dwell Analysis</Text>
                {zoneData?.zones?.length > 0 ? (
                  zoneData.zones.map((z: any) => (
                    <View key={z.zone_id} style={styles.zoneCard}>
                      <View style={styles.zoneHeader}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                          <MapPinned
                            size={16}
                            color={
                              z.risk_level === 'critical'
                                ? '#dc2626'
                                : z.risk_level === 'high'
                                ? '#ea580c'
                                : z.risk_level === 'medium'
                                ? '#b45309'
                                : '#0d9488'
                            }
                          />
                          <Text style={styles.zoneName}>{z.name}</Text>
                        </View>
                        <View style={[styles.riskTag, { backgroundColor: z.risk_level === 'high' ? '#fee2e2' : '#f1f5f9' }]}>
                          <Text style={styles.riskTagText}>{z.risk_level.toUpperCase()}</Text>
                        </View>
                      </View>

                      <View style={styles.zoneStatsGrid}>
                        <View style={styles.zoneStatCol}>
                          <Text style={styles.zStatLabel}>Unique Tourists</Text>
                          <Text style={styles.zStatVal}>{z.unique_tourists}</Text>
                        </View>
                        <View style={styles.zoneStatCol}>
                          <Text style={styles.zStatLabel}>Entries / Exits</Text>
                          <Text style={styles.zStatVal}>{z.total_entries} / {z.total_exits}</Text>
                        </View>
                        <View style={styles.zoneStatCol}>
                          <Text style={styles.zStatLabel}>Avg Dwell</Text>
                          <Text style={styles.zStatVal}>{formatSeconds(z.avg_dwell_seconds)}</Text>
                        </View>
                        <View style={styles.zoneStatCol}>
                          <Text style={styles.zStatLabel}>Incidents</Text>
                          <Text style={styles.zStatVal}>{z.incident_count}</Text>
                        </View>
                      </View>
                    </View>
                  ))
                ) : (
                  <EmptyState text="No active geospatial zones configured." />
                )}
              </View>
            </View>
          )}

          {/* TAB 4: ANOMALY INTELLIGENCE */}
          {activeTab === 'anomalies' && (
            <View style={styles.tabContent}>
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>LSTM Autoencoder Anomaly Episode Analytics</Text>
                <Text style={styles.panelSubtitle}>
                  Model operational telemetry without automated safety engine override
                </Text>

                <View style={styles.kpiRow}>
                  <KpiCard label="Total Episodes" value={anomalyData?.total_anomalies ?? 0} subtext="Observed episodes" />
                  <KpiCard
                    label="Incident Conversion"
                    value={anomalyData ? `${(anomalyData.operational_conversion_rate * 100).toFixed(1)}%` : '0%'}
                    subtext={`${anomalyData?.incident_conversion_count || 0} escalated to incidents`}
                  />
                  <KpiCard
                    label="Cleared Normal"
                    value={anomalyData?.cleared_without_incident_count ?? 0}
                    subtext="Self-resolved / safe"
                  />
                  <KpiCard
                    label="Inference Latency"
                    value={anomalyData?.inference_latency_avg_ms ? `${anomalyData.inference_latency_avg_ms} ms` : 'N/A'}
                    subtext="Avg model latency"
                  />
                </View>
              </View>

              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Reconstruction Error Score Distribution</Text>
                <Text style={styles.panelSubtitle}>Distribution of normalized loss across telemetry windows</Text>
                {anomalyData?.score_distribution ? (
                  <View style={styles.scoreDistWrap}>
                    {Object.entries(anomalyData.score_distribution).map(([range, count]: [string, any]) => (
                      <View key={range} style={styles.scoreRow}>
                        <Text style={styles.scoreRangeLabel}>{range}</Text>
                        <View style={styles.barTrack}>
                          <View
                            style={[
                              styles.barFill,
                              {
                                backgroundColor: range === '>1.0' ? '#dc2626' : range === '0.9-1.0' ? '#ea580c' : '#0d9488',
                                width: `${Math.min(100, (count / Math.max(1, anomalyData.total_anomalies)) * 100)}%`,
                              },
                            ]}
                          />
                        </View>
                        <Text style={styles.trendVal}>{count}</Text>
                      </View>
                    ))}
                  </View>
                ) : (
                  <EmptyState text="No anomaly episodes recorded in this window." />
                )}
              </View>
            </View>
          )}

          {/* TAB 5: RESPONDER OPERATIONS */}
          {activeTab === 'responders' && (
            <View style={styles.tabContent}>
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>Responder Unit & Field Performance</Text>
                <Text style={styles.panelSubtitle}>
                  Aggregated operational metrics for field coordination
                </Text>

                <View style={styles.kpiRow}>
                  <KpiCard label="Active Responders" value={responderData?.active_responders ?? 0} subtext="Registered field units" />
                  <KpiCard label="Total Assignments" value={responderData?.total_assignments ?? 0} subtext="Assigned dispatches" />
                  <KpiCard
                    label="Acceptance Rate"
                    value={responderData ? `${(responderData.acceptance_rate * 100).toFixed(1)}%` : '100%'}
                    subtext={`Rejection: ${(responderData?.rejection_rate || 0) * 100}%`}
                  />
                  <KpiCard
                    label="Avg Arrival (P50)"
                    value={formatSeconds(responderData?.p50_arrival_time_seconds)}
                    subtext={`P90: ${formatSeconds(responderData?.p90_arrival_time_seconds)}`}
                  />
                </View>
              </View>

              {responderData?.unit_performance?.length > 0 && (
                <View style={styles.panel}>
                  <Text style={styles.panelTitle}>Unit Performance Breakdown</Text>
                  {responderData.unit_performance.map((unit: any) => (
                    <View key={unit.unit_id} style={styles.unitRow}>
                      <Text style={styles.unitName}>{unit.unit_name}</Text>
                      <Text style={styles.unitMeta}>
                        {unit.completed} / {unit.total_assignments} completed · {unit.active_responders} responders
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}

          {/* TAB 6: DATA QUALITY */}
          {activeTab === 'quality' && (
            <View style={styles.tabContent}>
              <View style={styles.panel}>
                <Text style={styles.panelTitle}>System Data Quality & Integrity Monitor</Text>
                <Text style={styles.panelSubtitle}>
                  Continuous automated evaluation of incoming sensor feeds and timestamps
                </Text>

                <View style={styles.qualityList}>
                  {qualityData ? (
                    [
                      qualityData.gps_quality,
                      qualityData.telemetry_quality,
                      qualityData.ml_inference_quality,
                      qualityData.zone_geometry_validity,
                      qualityData.incident_completeness,
                      qualityData.notification_delivery_health,
                    ]
                      .filter(Boolean)
                      .map((q: any) => (
                        <View key={q.domain} style={styles.qualityRow}>
                          <View style={{ flex: 1 }}>
                            <Text style={styles.qualityDomain}>{q.domain}</Text>
                            <Text style={styles.qualityDetails}>{JSON.stringify(q.details || {})}</Text>
                          </View>
                          <View
                            style={[
                              styles.qualityBadge,
                              q.status === 'GOOD' ? styles.qGood : q.status === 'DEGRADED' ? styles.qDegraded : styles.qPoor,
                            ]}
                          >
                            <Text
                              style={[
                                styles.qualityBadgeText,
                                q.status === 'GOOD' ? styles.qGoodText : q.status === 'DEGRADED' ? styles.qDegradedText : styles.qPoorText,
                              ]}
                            >
                              {q.status} ({q.score}%)
                            </Text>
                          </View>
                        </View>
                      ))
                  ) : (
                    <EmptyState text="Data quality evaluation unavailable." />
                  )}
                </View>
              </View>
            </View>
          )}
        </>
      )}

      {/* Export Modal */}
      <Modal visible={exportModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <Text style={styles.modalTitle}>Generate Analytical Export</Text>
            <Text style={styles.modalSubtitle}>
              Export structured datasets for official audit and external analysis
            </Text>

            <View style={styles.exportSection}>
              <Text style={styles.exportSectionLabel}>Dataset Category:</Text>
              <View style={styles.exportOptionRow}>
                {['incidents', 'zones', 'responders', 'overview'].map((t) => (
                  <TouchableOpacity
                    key={t}
                    style={[styles.exportOptChip, exportType === t && styles.exportOptChipActive]}
                    onPress={() => setExportType(t)}
                  >
                    <Text style={[styles.exportOptText, exportType === t && styles.exportOptTextActive]}>
                      {t.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={styles.exportSection}>
              <Text style={styles.exportSectionLabel}>File Format:</Text>
              <View style={styles.exportOptionRow}>
                {['csv', 'json'].map((f) => (
                  <TouchableOpacity
                    key={f}
                    style={[styles.exportOptChip, exportFormat === f && styles.exportOptChipActive]}
                    onPress={() => setExportFormat(f)}
                  >
                    <Text style={[styles.exportOptText, exportFormat === f && styles.exportOptTextActive]}>
                      {f.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {exportJob && (
              <View style={styles.jobStatusBox}>
                <CheckCircle2 size={16} color="#059669" />
                <View style={{ flex: 1 }}>
                  <Text style={styles.jobSuccessText}>Export Ready ({exportJob.record_count} records)</Text>
                  <Text style={styles.jobRefText}>{exportJob.file_reference}</Text>
                </View>
              </View>
            )}

            <View style={styles.modalActionRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => {
                  setExportModalVisible(false);
                  setExportJob(null);
                }}
              >
                <Text style={styles.modalCancelText}>Close</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSubmitBtn}
                onPress={handleCreateExport}
                disabled={exportLoading}
              >
                {exportLoading ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <Text style={styles.modalSubmitText}>Generate Export</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function KpiCard({ icon, label, value, subtext, alert = false }: any) {
  return (
    <View style={[styles.kpi, alert && styles.kpiAlert]}>
      <View style={styles.kpiHeader}>
        {icon}
        <Text style={styles.kpiLabel}>{label}</Text>
      </View>
      <Text style={[styles.kpiValue, alert && styles.kpiValueAlert]}>{value}</Text>
      {subtext && <Text style={styles.kpiSubtext}>{subtext}</Text>}
    </View>
  );
}

function LifecycleRow({ label, metrics }: { label: string; metrics?: any }) {
  return (
    <View style={styles.lcRow}>
      <Text style={styles.lcLabel}>{label}</Text>
      <View style={styles.lcMetrics}>
        <Text style={styles.lcP50}>P50: {metrics?.p50_seconds !== undefined && metrics?.p50_seconds !== null ? `${metrics.p50_seconds}s` : 'N/A'}</Text>
        <Text style={styles.lcP90}>P90: {metrics?.p90_seconds !== undefined && metrics?.p90_seconds !== null ? `${metrics.p90_seconds}s` : 'N/A'}</Text>
        <Text style={styles.lcMean}>Avg: {metrics?.mean_seconds !== undefined && metrics?.mean_seconds !== null ? `${metrics.mean_seconds}s` : 'N/A'}</Text>
      </View>
    </View>
  );
}

function TabButton({ label, icon, active, onPress }: { label: string; icon: React.ReactNode; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={[styles.tabBtn, active && styles.tabBtnActive]} onPress={onPress}>
      {React.cloneElement(icon as React.ReactElement, { color: active ? '#0f766e' : '#64748b' })}
      <Text style={[styles.tabBtnText, active && styles.tabBtnTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <View style={styles.emptyWrap}>
      <Compass size={20} color="#94a3b8" />
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  header: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 12,
  },
  headerTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  title: { fontSize: 20, fontWeight: '800', color: '#0f172a' },
  subtitle: { fontSize: 13, color: '#64748b', marginTop: 2 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  exportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#f0fdfa',
    borderWidth: 1,
    borderColor: '#ccfbf1',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  exportBtnText: { fontSize: 12, fontWeight: '700', color: '#0f766e' },
  refreshBtn: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  refreshBtnActive: { opacity: 0.5 },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 14,
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
    paddingTop: 10,
  },
  filterGroup: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  filterLabel: { fontSize: 12, fontWeight: '700', color: '#64748b' },
  filterChip: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: '#f1f5f9',
  },
  filterChipActive: { backgroundColor: '#0f766e' },
  filterChipText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  filterChipTextActive: { color: '#ffffff' },
  freshnessBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginLeft: 'auto',
    backgroundColor: '#f8fafc',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  freshnessDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#059669' },
  freshnessText: { fontSize: 11, fontWeight: '600', color: '#64748b' },
  kpiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  kpi: {
    flex: 1,
    minWidth: '18%',
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 4,
  },
  kpiAlert: { borderColor: '#fca5a5', backgroundColor: '#fef2f2' },
  kpiHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  kpiLabel: { fontSize: 11, fontWeight: '700', color: '#64748b', textTransform: 'uppercase' },
  kpiValue: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  kpiValueAlert: { color: '#dc2626' },
  kpiSubtext: { fontSize: 10, color: '#94a3b8' },
  tabBar: { flexDirection: 'row', marginBottom: 2 },
  tabBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginRight: 8,
  },
  tabBtnActive: {
    backgroundColor: '#f0fdfa',
    borderColor: '#0f766e',
  },
  tabBtnText: { fontSize: 12, fontWeight: '700', color: '#64748b' },
  tabBtnTextActive: { color: '#0f766e' },
  tabContent: { gap: 14 },
  panel: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 12,
  },
  panelRow: { flexDirection: 'row', gap: 12 },
  panelTitle: { fontSize: 15, fontWeight: '800', color: '#0f172a' },
  panelSubtitle: { fontSize: 12, color: '#64748b', marginTop: -6 },
  trendList: { gap: 8 },
  trendRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  trendLabel: { width: 100, fontSize: 11, color: '#64748b' },
  barTrack: { flex: 1, height: 10, backgroundColor: '#f1f5f9', borderRadius: 999, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: '#0d9488' },
  trendVal: { width: 32, textAlign: 'right', fontSize: 12, fontWeight: '700', color: '#0f172a' },
  stateGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  stateCard: {
    flex: 1,
    minWidth: '28%',
    backgroundColor: '#f8fafc',
    padding: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  stateCardLabel: { fontSize: 11, fontWeight: '700', color: '#64748b' },
  stateCardVal: { fontSize: 16, fontWeight: '800', color: '#0f172a', marginTop: 4 },
  percentileTable: { gap: 8 },
  lcRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  lcLabel: { fontSize: 13, fontWeight: '600', color: '#334155' },
  lcMetrics: { flexDirection: 'row', gap: 12 },
  lcP50: { fontSize: 12, fontWeight: '700', color: '#0f766e' },
  lcP90: { fontSize: 12, fontWeight: '700', color: '#b45309' },
  lcMean: { fontSize: 12, color: '#64748b' },
  slaBox: {
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  slaRate: { fontSize: 24, fontWeight: '800', color: '#059669' },
  slaDetails: { fontSize: 11, color: '#64748b' },
  sourceGrid: { flexDirection: 'row', gap: 16 },
  subCol: { flex: 1, gap: 6 },
  subColTitle: { fontSize: 12, fontWeight: '700', color: '#475569', textTransform: 'uppercase' },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: '#f8fafc' },
  metaLabel: { fontSize: 12, color: '#64748b' },
  metaVal: { fontSize: 12, fontWeight: '700', color: '#0f172a' },
  emptyInline: { fontSize: 11, color: '#94a3b8' },
  layerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  layerChip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, backgroundColor: '#f1f5f9' },
  layerChipActive: { backgroundColor: '#0f766e' },
  layerChipText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  layerChipTextActive: { color: '#ffffff' },
  heatmapList: { gap: 6 },
  heatRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 10,
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  heatGeohash: { gap: 2 },
  heatGeohashText: { fontSize: 12, fontWeight: '700', color: '#0f172a' },
  heatCoordText: { fontSize: 10, color: '#64748b' },
  suppressedBadge: { backgroundColor: '#fee2e2', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  suppressedText: { fontSize: 10, fontWeight: '700', color: '#dc2626' },
  heatScoreWrap: { backgroundColor: '#ccfbf1', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  heatScore: { fontSize: 11, fontWeight: '700', color: '#0f766e' },
  zoneCard: {
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 8,
  },
  zoneHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  zoneName: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  riskTag: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  riskTagText: { fontSize: 10, fontWeight: '800', color: '#475569' },
  zoneStatsGrid: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: '#e2e8f0', paddingTop: 6 },
  zoneStatCol: { alignItems: 'center' },
  zStatLabel: { fontSize: 10, color: '#64748b' },
  zStatVal: { fontSize: 12, fontWeight: '700', color: '#0f172a', marginTop: 2 },
  scoreDistWrap: { gap: 8 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  scoreRangeLabel: { width: 60, fontSize: 11, color: '#64748b' },
  unitRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  unitName: { fontSize: 13, fontWeight: '700', color: '#0f172a' },
  unitMeta: { fontSize: 12, color: '#64748b' },
  qualityList: { gap: 8 },
  qualityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 10,
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  qualityDomain: { fontSize: 13, fontWeight: '700', color: '#0f172a' },
  qualityDetails: { fontSize: 10, color: '#64748b', marginTop: 2 },
  qualityBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  qGood: { backgroundColor: '#dcfce7' },
  qDegraded: { backgroundColor: '#fef3c7' },
  qPoor: { backgroundColor: '#fee2e2' },
  qualityBadgeText: { fontSize: 11, fontWeight: '800' },
  qGoodText: { color: '#15803d' },
  qDegradedText: { color: '#b45309' },
  qPoorText: { color: '#dc2626' },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContainer: {
    width: '100%',
    maxWidth: 480,
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 20,
    gap: 14,
  },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#0f172a' },
  modalSubtitle: { fontSize: 12, color: '#64748b', marginTop: -8 },
  exportSection: { gap: 6 },
  exportSectionLabel: { fontSize: 11, fontWeight: '700', color: '#475569' },
  exportOptionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  exportOptChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: '#f1f5f9' },
  exportOptChipActive: { backgroundColor: '#0f766e' },
  exportOptText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  exportOptTextActive: { color: '#ffffff' },
  jobStatusBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 10,
    backgroundColor: '#f0fdf4',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  jobSuccessText: { fontSize: 12, fontWeight: '700', color: '#15803d' },
  jobRefText: { fontSize: 10, color: '#64748b' },
  modalActionRow: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 6 },
  modalCancelBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: '#f1f5f9' },
  modalCancelText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  modalSubmitBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: '#0f766e' },
  modalSubmitText: { fontSize: 12, fontWeight: '700', color: '#ffffff' },
  loadingBox: { padding: 40, alignItems: 'center', gap: 10 },
  loadingBoxText: { fontSize: 13, color: '#64748b' },
  errorBox: {
    padding: 24,
    backgroundColor: '#fef2f2',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#fca5a5',
    alignItems: 'center',
    gap: 8,
  },
  errorBoxTitle: { fontSize: 14, fontWeight: '800', color: '#dc2626' },
  errorBoxDesc: { fontSize: 12, color: '#991b1b', textAlign: 'center' },
  retryBtn: {
    marginTop: 6,
    backgroundColor: '#dc2626',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
  },
  retryBtnText: { fontSize: 12, fontWeight: '700', color: '#ffffff' },
  emptyWrap: { padding: 24, alignItems: 'center', gap: 6 },
  emptyText: { fontSize: 12, color: '#94a3b8', textAlign: 'center' },
});
