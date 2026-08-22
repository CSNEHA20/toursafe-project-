import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  TextInput,
  ActivityIndicator,
  useWindowDimensions,
  Platform,
} from 'react-native';
import {
  ShieldAlert,
  ShieldCheck,
  Radio,
  Users,
  Activity,
  AlertTriangle,
  MapPin,
  Clock,
  Send,
  Eye,
  CheckCircle,
  AlertOctagon,
  RefreshCw,
  Search,
  Filter,
  Layers,
  ChevronRight,
  UserCheck,
  UserX,
  Flame,
  ArrowRight,
  X,
  Phone,
  Compass,
  Check,
  AlertCircle,
  Building,
  Cpu,
  Bell,
  SlidersHorizontal,
  Pause,
  Play,
  Trash2,
  Bot,
  Sparkles,
} from 'lucide-react-native';
import RoleSwitch from '@/components/RoleSwitch';
import { NotificationBellButton } from '@/components/NotificationBellButton';
import { ConnectionStatusBadge } from '@/components/ConnectionStatusBadge';
import RealMap, { MapMarkerProp, ZonePolygonProp } from '@/components/RealMap';
import { CopilotPanel } from '@/components/admin/CopilotPanel';
import {
  useCommandCenterStore,
  SafetyState,
  StalenessStatus,
  EventCategory,
} from '@/store/commandCenterStore';

import Toast from 'react-native-toast-message';

export default function AuthorityCommandCenter() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 1024;
  const isTablet = width >= 768 && width < 1024;

  // Store state
  const {
    isLoading,
    isRefreshing,
    error,
    connectionState,
    authorityScope,
    incidents,
    tourists,
    responders,
    zones,
    kpis,
    systemHealth,
    eventStream,
    isStreamPaused,
    selectedIncidentId,
    selectedTouristId,
    selectedResponderId,
    selectedZoneId,
    mapFocusCoordinates,
    activeQueueTab,
    activeEventCategory,
    incidentSeverityFilter,
    incidentStatusFilter,
    searchQuery,
    activeLayers,
    fetchSnapshot,
    reconcileSnapshot,
    evaluateStaleness,
    toggleStreamPause,
    clearEventStream,
    selectIncident,
    selectTourist,
    selectResponder,
    selectZone,
    setMapFocus,
    setActiveQueueTab,
    setActiveEventCategory,
    setIncidentSeverityFilter,
    setIncidentStatusFilter,
    setSearchQuery,
    toggleLayer,
    acknowledgeIncident,
    assignResponder,
    escalateIncident,
    resolveIncident,
    closeIncident,
  } = useCommandCenterStore();

  // Modals state
  const [assignModalVisible, setAssignModalVisible] = useState(false);
  const [escalateModalVisible, setEscalateModalVisible] = useState(false);
  const [resolveModalVisible, setResolveModalVisible] = useState(false);
  const [healthModalVisible, setHealthModalVisible] = useState(false);
  const [copilotVisible, setCopilotVisible] = useState(false);

  // Form states for modals
  const [selectedResponderForAssign, setSelectedResponderForAssign] = useState<string>('');
  const [assignNotes, setAssignNotes] = useState('');
  const [escalateReason, setEscalateReason] = useState('');
  const [escalateSeverity, setEscalateSeverity] = useState<'HIGH' | 'CRITICAL'>('CRITICAL');
  const [resolveReason, setResolveReason] = useState('');
  const [resolveCategory, setResolveCategory] = useState('ASSISTANCE_RENDERED');
  const [actionLoading, setActionLoading] = useState(false);

  // Initial load and periodic staleness check
  useEffect(() => {
    fetchSnapshot();

    const stalenessInterval = setInterval(() => {
      evaluateStaleness();
    }, 15000);

    return () => clearInterval(stalenessInterval);
  }, [fetchSnapshot, evaluateStaleness]);

  // Derive Lists
  const incidentList = useMemo(() => {
    let list = Object.values(incidents);
    if (incidentSeverityFilter) {
      list = list.filter((i) => i.severity === incidentSeverityFilter);
    }
    if (incidentStatusFilter) {
      list = list.filter((i) => i.status === incidentStatusFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (i) =>
          i.incident_id.toLowerCase().includes(q) ||
          i.tourist_name?.toLowerCase().includes(q) ||
          i.reasons?.some((r) => r.toLowerCase().includes(q))
      );
    }
    // Sort by operational urgency (CRITICAL first, then age)
    return list.sort((a, b) => {
      const score = (sev: string) => (sev === 'CRITICAL' ? 4 : sev === 'HIGH' ? 3 : sev === 'MEDIUM' ? 2 : 1);
      if (score(b.severity) !== score(a.severity)) {
        return score(b.severity) - score(a.severity);
      }
      return (b.age_seconds || 0) - (a.age_seconds || 0);
    });
  }, [incidents, incidentSeverityFilter, incidentStatusFilter, searchQuery]);

  const sosList = useMemo(() => {
    return incidentList.filter((i) => i.is_sos || i.severity === 'CRITICAL');
  }, [incidentList]);

  const responderList = useMemo(() => {
    let list = Object.values(responders);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((r) => r.full_name.toLowerCase().includes(q) || r.unit_name?.toLowerCase().includes(q));
    }
    return list;
  }, [responders, searchQuery]);

  const zoneList = useMemo(() => {
    let list = Object.values(zones);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((z) => z.name.toLowerCase().includes(q));
    }
    return list;
  }, [zones, searchQuery]);

  const touristList = useMemo(() => Object.values(tourists), [tourists]);

  // Selected Entities
  const activeIncident = selectedIncidentId ? incidents[selectedIncidentId] : null;
  const activeTourist = selectedTouristId
    ? tourists[selectedTouristId]
    : activeIncident
    ? tourists[activeIncident.tourist_id]
    : null;
  const activeResponder = selectedResponderId
    ? responders[selectedResponderId]
    : activeIncident?.assigned_responder_id
    ? responders[activeIncident.assigned_responder_id]
    : null;
  const activeZone = selectedZoneId
    ? zones[selectedZoneId]
    : activeIncident?.zone_id
    ? zones[activeIncident.zone_id]
    : null;

  // Filtered Event Stream
  const filteredEvents = useMemo(() => {
    if (activeEventCategory === 'ALL') return eventStream;
    return eventStream.filter((e) => e.category === activeEventCategory);
  }, [eventStream, activeEventCategory]);

  // Build Map Markers & Polygons
  const mapRegion = useMemo(() => {
    if (mapFocusCoordinates) {
      return {
        latitude: mapFocusCoordinates.latitude,
        longitude: mapFocusCoordinates.longitude,
        zoom: mapFocusCoordinates.zoom || 14,
      };
    }
    if (activeIncident?.latitude && activeIncident?.longitude) {
      return {
        latitude: activeIncident.latitude,
        longitude: activeIncident.longitude,
        zoom: 15,
      };
    }
    return {
      latitude: 15.4989,
      longitude: 73.8278,
      zoom: 13,
    };
  }, [mapFocusCoordinates, activeIncident]);

  const mapPolygons: ZonePolygonProp[] = useMemo(() => {
    if (!activeLayers.zones) return [];
    return zoneList
      .filter((z) => z.boundary && z.boundary.coordinates)
      .map((z) => {
        const coords: Array<{ latitude: number; longitude: number }> = [];
        if (z.boundary.type === 'Polygon') {
          const outerRing = z.boundary.coordinates[0] || [];
          outerRing.forEach(([lon, lat]: [number, number]) => {
            coords.push({ latitude: lat, longitude: lon });
          });
        }
        return {
          coordinates: coords,
          name: `${z.name} (${z.risk_level.toUpperCase()}) • Occupancy: ${z.active_tourists_count}`,
          risk_level: z.risk_level,
        };
      })
      .filter((p) => p.coordinates.length > 2);
  }, [zoneList, activeLayers.zones]);

  const mapMarkers: MapMarkerProp[] = useMemo(() => {
    const markers: MapMarkerProp[] = [];

    // 1. Incidents
    if (activeLayers.incidents) {
      incidentList.forEach((inc) => {
        if (inc.latitude && inc.longitude) {
          const color = inc.severity === 'CRITICAL' ? '#ef4444' : inc.severity === 'HIGH' ? '#f97316' : '#eab308';
          markers.push({
            latitude: inc.latitude,
            longitude: inc.longitude,
            title: `[INCIDENT] ${inc.tourist_name || inc.incident_id.slice(0, 8)}`,
            subtitle: `${inc.severity} • ${inc.status} • ${inc.reasons?.[0] || 'Alert'}`,
            color,
            icon: '!',
          });
        }
      });
    }

    // 2. Responders
    if (activeLayers.responders) {
      responderList.forEach((r) => {
        if (r.latitude && r.longitude) {
          const color = r.status === 'AVAILABLE' ? '#10b981' : r.status === 'ASSIGNED' ? '#3b82f6' : '#64748b';
          markers.push({
            latitude: r.latitude,
            longitude: r.longitude,
            title: `[UNIT] ${r.unit_name || r.full_name}`,
            subtitle: `${r.unit_type} • Status: ${r.status}`,
            color,
            icon: 'R',
          });
        }
      });
    }

    // 3. Tourists
    if (activeLayers.tourists) {
      touristList.forEach((t) => {
        if (t.latitude && t.longitude) {
          let color = '#38bdf8';
          if (t.safety_state === 'INCIDENT') color = '#ef4444';
          else if (t.safety_state === 'ELEVATED' || t.safety_state === 'INCIDENT_CANDIDATE') color = '#f97316';
          else if (t.safety_state === 'WATCH') color = '#facc15';
          else if (t.staleness === 'STALE' || t.staleness === 'UNKNOWN') color = '#94a3b8';

          markers.push({
            latitude: t.latitude,
            longitude: t.longitude,
            title: `[TOURIST] ${t.full_name}`,
            subtitle: `Safety: ${t.safety_state} • Staleness: ${t.staleness}`,
            color,
            icon: 'T',
          });
        }
      });
    }

    return markers;
  }, [activeLayers, incidentList, responderList, touristList]);

  // Modal Submissions
  const handleAssignSubmit = async () => {
    if (!selectedIncidentId || !selectedResponderForAssign) {
      Toast.show({ type: 'error', text1: 'Validation Error', text2: 'Please select a responder' });
      return;
    }
    setActionLoading(true);
    const resp = responders[selectedResponderForAssign];
    const success = await assignResponder(
      selectedIncidentId,
      selectedResponderForAssign,
      resp?.unit_id,
      assignNotes
    );
    setActionLoading(false);
    if (success) {
      setAssignModalVisible(false);
      setAssignNotes('');
      setSelectedResponderForAssign('');
    }
  };

  const handleEscalateSubmit = async () => {
    if (!selectedIncidentId || !escalateReason.trim()) {
      Toast.show({ type: 'error', text1: 'Validation Error', text2: 'Please enter escalation reason' });
      return;
    }
    setActionLoading(true);
    const success = await escalateIncident(selectedIncidentId, escalateReason, escalateSeverity);
    setActionLoading(false);
    if (success) {
      setEscalateModalVisible(false);
      setEscalateReason('');
    }
  };

  const handleResolveSubmit = async () => {
    if (!selectedIncidentId || !resolveReason.trim()) {
      Toast.show({ type: 'error', text1: 'Validation Error', text2: 'Please enter resolution notes' });
      return;
    }
    setActionLoading(true);
    const success = await resolveIncident(selectedIncidentId, resolveReason, resolveCategory);
    setActionLoading(false);
    if (success) {
      setResolveModalVisible(false);
      setResolveReason('');
    }
  };

  // Helper Badge Color Calculators
  const getSafetyBadge = (state: SafetyState) => {
    switch (state) {
      case 'NORMAL':
        return { bg: '#064e3b', text: '#34d399', border: '#059669' };
      case 'WATCH':
        return { bg: '#451a03', text: '#fde047', border: '#ca8a04' };
      case 'ELEVATED':
        return { bg: '#7c2d12', text: '#fdba74', border: '#ea580c' };
      case 'INCIDENT_CANDIDATE':
      case 'INCIDENT':
        return { bg: '#7f1d1d', text: '#fca5a5', border: '#dc2626' };
      case 'RECOVERING':
        return { bg: '#1e1b4b', text: '#c7d2fe', border: '#6366f1' };
      case 'UNKNOWN':
      default:
        return { bg: '#334155', text: '#94a3b8', border: '#64748b' };
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'CRITICAL':
        return { bg: '#7f1d1d', text: '#fecaca', border: '#ef4444' };
      case 'HIGH':
        return { bg: '#7c2d12', text: '#ffedd5', border: '#f97316' };
      case 'MEDIUM':
        return { bg: '#713f12', text: '#fef08a', border: '#eab308' };
      case 'LOW':
      default:
        return { bg: '#14532d', text: '#bbf7d0', border: '#22c55e' };
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* ── TOP MISSION CONTROL HEADER ────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.badgeRow}>
            <View style={styles.commandPill}>
              <Radio size={12} color="#38bdf8" />
              <Text style={styles.commandPillText}>AUTHORITY COMMAND CENTER</Text>
            </View>
            <View style={styles.jurisdictionPill}>
              <Building size={12} color="#94a3b8" />
              <Text style={styles.jurisdictionText}>
                {authorityScope?.organization_name || 'Goa Police Department'} • {authorityScope?.jurisdiction_code || 'IN-GOA'}
              </Text>
            </View>
          </View>
          <Text style={styles.headerTitle}>Live Operational Incident & Safety Command</Text>
          <Text style={styles.headerSubtitle}>
            Authoritative multisignal intelligence fusion: Realtime GPS, IMU kinematic anomaly inference, GeoJSON geofences, and Responder dispatch.
          </Text>
        </View>

        <View style={styles.headerRight}>
          <View style={styles.headerControlRow}>
            <TouchableOpacity
              style={[styles.healthButton, { backgroundColor: '#082f49', borderColor: '#0284c7' }]}
              onPress={() => setCopilotVisible(true)}
            >
              <Bot size={14} color="#38bdf8" />
              <Text style={[styles.healthButtonText, { color: '#38bdf8' }]}>AI COPILOT</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.healthButton}
              onPress={() => setHealthModalVisible(true)}
            >
              <Cpu size={14} color="#38bdf8" />
              <Text style={styles.healthButtonText}>SYSTEM STATUS</Text>
            </TouchableOpacity>
            <ConnectionStatusBadge />
            <NotificationBellButton />
            <TouchableOpacity
              style={styles.refreshButton}
              onPress={() => reconcileSnapshot()}
              disabled={isRefreshing}
            >
              <RefreshCw size={15} color="#94a3b8" />
            </TouchableOpacity>
          </View>
          <View style={{ marginTop: 8 }}>
            <RoleSwitch currentRole="authority" />
          </View>
        </View>
      </View>

      {/* ── OPERATIONAL KPI BAR (7 LIVE METRICS) ─────────────────────────── */}
      <View style={styles.kpiContainer}>
        <KpiCard
          label="Active Tourists"
          value={kpis.active_tourists}
          icon={<Users size={16} color="#38bdf8" />}
          accentColor="#0284c7"
        />
        <KpiCard
          label="Open Incidents"
          value={kpis.open_incidents}
          icon={<AlertTriangle size={16} color="#f97316" />}
          accentColor="#ea580c"
          highlight={kpis.open_incidents > 0}
        />
        <KpiCard
          label="Active SOS"
          value={kpis.sos_incidents}
          icon={<ShieldAlert size={16} color="#ef4444" />}
          accentColor="#dc2626"
          highlight={kpis.sos_incidents > 0}
        />
        <KpiCard
          label="Active Responders"
          value={kpis.active_responders}
          icon={<ShieldCheck size={16} color="#10b981" />}
          accentColor="#059669"
        />
        <KpiCard
          label="Unassigned"
          value={kpis.unassigned_incidents}
          icon={<Clock size={16} color="#eab308" />}
          accentColor="#ca8a04"
          highlight={kpis.unassigned_incidents > 0}
        />
        <KpiCard
          label="Elevated Risk"
          value={kpis.elevated_safety_states}
          icon={<Activity size={16} color="#f43f5e" />}
          accentColor="#e11d48"
        />
        <KpiCard
          label="Stale / Offline"
          value={kpis.stale_tracking_tourists}
          icon={<Radio size={16} color="#94a3b8" />}
          accentColor="#64748b"
        />
      </View>

      {/* ── SEARCH & MAP LAYER CONTROLS ───────────────────────────────────── */}
      <View style={styles.searchFilterRow}>
        <View style={styles.searchBox}>
          <Search size={16} color="#64748b" style={{ marginRight: 8 }} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search incident ID, tourist, responder, or zone..."
            placeholderTextColor="#64748b"
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <X size={16} color="#94a3b8" />
            </TouchableOpacity>
          ) : null}
        </View>

        <View style={styles.layerToggles}>
          <Text style={styles.layerLabel}>Layers:</Text>
          <LayerButton
            label="Tourists"
            active={activeLayers.tourists}
            onPress={() => toggleLayer('tourists')}
            color="#38bdf8"
          />
          <LayerButton
            label="Responders"
            active={activeLayers.responders}
            onPress={() => toggleLayer('responders')}
            color="#10b981"
          />
          <LayerButton
            label="Incidents"
            active={activeLayers.incidents}
            onPress={() => toggleLayer('incidents')}
            color="#ef4444"
          />
          <LayerButton
            label="Zones"
            active={activeLayers.zones}
            onPress={() => toggleLayer('zones')}
            color="#f59e0b"
          />
        </View>
      </View>

      {/* ── MULTI-PANEL OPERATIONAL WORKSPACE ─────────────────────────────── */}
      <View style={[styles.mainWorkspace, isDesktop ? styles.rowLayout : styles.columnLayout]}>
        {/* ── LEFT PANEL: QUEUES & LISTS ─────────────────────────────────── */}
        <View style={[styles.panel, isDesktop ? { width: '32%' } : { width: '100%' }]}>
          {/* Tab Navigation */}
          <View style={styles.queueTabs}>
            <TouchableOpacity
              style={[styles.queueTab, activeQueueTab === 'incidents' && styles.activeQueueTab]}
              onPress={() => setActiveQueueTab('incidents')}
            >
              <Text style={[styles.queueTabText, activeQueueTab === 'incidents' && styles.activeQueueTabText]}>
                Incidents ({incidentList.length})
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.queueTab, activeQueueTab === 'sos' && styles.activeQueueTab]}
              onPress={() => setActiveQueueTab('sos')}
            >
              <Text style={[styles.queueTabText, activeQueueTab === 'sos' && styles.activeQueueTabText, sosList.length > 0 && { color: '#ef4444' }]}>
                SOS ({sosList.length})
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.queueTab, activeQueueTab === 'responders' && styles.activeQueueTab]}
              onPress={() => setActiveQueueTab('responders')}
            >
              <Text style={[styles.queueTabText, activeQueueTab === 'responders' && styles.activeQueueTabText]}>
                Units ({responderList.length})
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.queueTab, activeQueueTab === 'zones' && styles.activeQueueTab]}
              onPress={() => setActiveQueueTab('zones')}
            >
              <Text style={[styles.queueTabText, activeQueueTab === 'zones' && styles.activeQueueTabText]}>
                Zones ({zoneList.length})
              </Text>
            </TouchableOpacity>
          </View>

          {/* List Content */}
          <ScrollView style={styles.queueListScroll} nestedScrollEnabled>
            {activeQueueTab === 'incidents' && (
              <View>
                {incidentList.length === 0 ? (
                  <EmptyState text="No active incidents in queue. All tourists safe." icon={<ShieldCheck size={32} color="#10b981" />} />
                ) : (
                  incidentList.map((inc) => (
                    <IncidentCard
                      key={inc.incident_id}
                      incident={inc}
                      isSelected={selectedIncidentId === inc.incident_id}
                      onSelect={() => selectIncident(inc.incident_id)}
                      onFocusMap={() => {
                        selectIncident(inc.incident_id);
                        if (inc.latitude && inc.longitude) {
                          setMapFocus({ latitude: inc.latitude, longitude: inc.longitude, zoom: 16 });
                        }
                      }}
                      getSeverityBadge={getSeverityBadge}
                    />
                  ))
                )}
              </View>
            )}

            {activeQueueTab === 'sos' && (
              <View>
                {sosList.length === 0 ? (
                  <EmptyState text="No manual SOS events pending response." icon={<ShieldCheck size={32} color="#10b981" />} />
                ) : (
                  sosList.map((inc) => (
                    <IncidentCard
                      key={inc.incident_id}
                      incident={inc}
                      isSelected={selectedIncidentId === inc.incident_id}
                      onSelect={() => selectIncident(inc.incident_id)}
                      onFocusMap={() => {
                        selectIncident(inc.incident_id);
                        if (inc.latitude && inc.longitude) {
                          setMapFocus({ latitude: inc.latitude, longitude: inc.longitude, zoom: 16 });
                        }
                      }}
                      getSeverityBadge={getSeverityBadge}
                    />
                  ))
                )}
              </View>
            )}

            {activeQueueTab === 'responders' && (
              <View>
                {responderList.length === 0 ? (
                  <EmptyState text="No responders registered." icon={<Users size={32} color="#64748b" />} />
                ) : (
                  responderList.map((r) => (
                    <TouchableOpacity
                      key={r.responder_id}
                      style={[styles.entityCard, selectedResponderId === r.responder_id && styles.selectedEntityCard]}
                      onPress={() => selectResponder(r.responder_id)}
                    >
                      <View style={styles.entityHeader}>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.entityTitle}>{r.unit_name || r.full_name}</Text>
                          <Text style={styles.entitySubtitle}>{r.unit_type} • Capabilities: {r.capabilities.join(', ')}</Text>
                        </View>
                        <View style={[styles.statusPill, r.status === 'AVAILABLE' ? styles.statusAvailable : styles.statusAssigned]}>
                          <Text style={styles.statusPillText}>{r.status}</Text>
                        </View>
                      </View>
                    </TouchableOpacity>
                  ))
                )}
              </View>
            )}

            {activeQueueTab === 'zones' && (
              <View>
                {zoneList.length === 0 ? (
                  <EmptyState text="No zones configured." icon={<MapPin size={32} color="#64748b" />} />
                ) : (
                  zoneList.map((z) => (
                    <TouchableOpacity
                      key={z.zone_id}
                      style={[styles.entityCard, selectedZoneId === z.zone_id && styles.selectedEntityCard]}
                      onPress={() => selectZone(z.zone_id)}
                    >
                      <View style={styles.entityHeader}>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.entityTitle}>{z.name}</Text>
                          <Text style={styles.entitySubtitle}>Type: {z.zone_type} • Risk: {z.risk_level.toUpperCase()}</Text>
                        </View>
                        <View style={styles.occupancyBadge}>
                          <Users size={12} color="#38bdf8" />
                          <Text style={styles.occupancyText}>{z.active_tourists_count}</Text>
                        </View>
                      </View>
                    </TouchableOpacity>
                  ))
                )}
              </View>
            )}
          </ScrollView>
        </View>

        {/* ── CENTER PANEL: LIVE OPERATIONAL MAP ──────────────────────────── */}
        <View style={[styles.panel, isDesktop ? { width: '38%' } : { width: '100%' }]}>
          <View style={styles.mapHeader}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <MapPin size={16} color="#38bdf8" />
              <Text style={styles.panelTitle}>Live Geospatial Operations Map</Text>
            </View>
            <Text style={styles.mapLegend}>
              {mapMarkers.length} Active Pins • {mapPolygons.length} Zones
            </Text>
          </View>

          <View style={styles.mapWrapper}>
            <RealMap
              region={mapRegion}
              markers={mapMarkers}
              polygons={mapPolygons}
              height={440}
            />
          </View>
        </View>

        {/* ── RIGHT PANEL: INCIDENT COMMAND & DETAIL DRAWER ───────────────── */}
        <View style={[styles.panel, isDesktop ? { width: '28%' } : { width: '100%' }]}>
          {activeIncident ? (
            <View style={styles.commandPanel}>
              <View style={styles.commandHeader}>
                <View>
                  <Text style={styles.commandKicker}>INCIDENT COMMAND PANEL</Text>
                  <Text style={styles.commandIncidentId}>ID: {activeIncident.incident_id.slice(0, 12)}</Text>
                </View>
                <TouchableOpacity onPress={() => selectIncident(null)}>
                  <X size={18} color="#94a3b8" />
                </TouchableOpacity>
              </View>

              {/* Status & Severity Bar */}
              <View style={styles.commandStatusRow}>
                <View style={[styles.severityTag, { backgroundColor: getSeverityBadge(activeIncident.severity).bg, borderColor: getSeverityBadge(activeIncident.severity).border }]}>
                  <Text style={[styles.severityTagText, { color: getSeverityBadge(activeIncident.severity).text }]}>
                    {activeIncident.severity}
                  </Text>
                </View>
                <View style={styles.statusTag}>
                  <Text style={styles.statusTagText}>{activeIncident.status}</Text>
                </View>
                <View style={styles.ageTag}>
                  <Clock size={12} color="#94a3b8" />
                  <Text style={styles.ageTagText}>{Math.floor(activeIncident.age_seconds / 60)}m ago</Text>
                </View>
              </View>

              {/* Tourist Overview */}
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>TOURIST DETAILS</Text>
                <Text style={styles.detailMain}>{activeIncident.tourist_name || 'Alice Smith'}</Text>
                <Text style={styles.detailSub}>ID: {activeIncident.tourist_id.slice(0, 10)} • Verification: Verified Credential</Text>
              </View>

              {/* Assigned Responder */}
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>ASSIGNED UNIT</Text>
                <Text style={styles.detailMain}>
                  {activeIncident.assigned_responder_name || (activeIncident.assigned_responder_id ? `Unit ${activeIncident.assigned_responder_id}` : 'UNASSIGNED')}
                </Text>
                {activeIncident.assigned_responder_id ? (
                  <Text style={styles.detailSub}>Unit ID: {activeIncident.assigned_unit_id || activeIncident.assigned_responder_id}</Text>
                ) : (
                  <Text style={[styles.detailSub, { color: '#f59e0b' }]}>Immediate unit dispatch recommended</Text>
                )}
              </View>

              {/* Trigger Reasons */}
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>TRIGGER SIGNALS & REASONS</Text>
                {activeIncident.reasons.map((r, idx) => (
                  <Text key={idx} style={styles.reasonBullet}>• {r}</Text>
                ))}
              </View>

              {/* Operational Command Actions */}
              <View style={styles.actionGrid}>
                {activeIncident.status === 'OPEN' && (
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.btnAcknowledge]}
                    onPress={() => acknowledgeIncident(activeIncident.incident_id)}
                  >
                    <CheckCircle size={14} color="#fff" />
                    <Text style={styles.actionBtnText}>ACKNOWLEDGE</Text>
                  </TouchableOpacity>
                )}

                <TouchableOpacity
                  style={[styles.actionBtn, styles.btnAssign]}
                  onPress={() => {
                    setSelectedResponderForAssign(activeIncident.assigned_responder_id || '');
                    setAssignModalVisible(true);
                  }}
                >
                  <Users size={14} color="#fff" />
                  <Text style={styles.actionBtnText}>
                    {activeIncident.assigned_responder_id ? 'REASSIGN UNIT' : 'ASSIGN UNIT'}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.actionBtn, styles.btnEscalate]}
                  onPress={() => setEscalateModalVisible(true)}
                >
                  <Flame size={14} color="#fff" />
                  <Text style={styles.actionBtnText}>ESCALATE</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.actionBtn, styles.btnResolve]}
                  onPress={() => setResolveModalVisible(true)}
                >
                  <Check size={14} color="#fff" />
                  <Text style={styles.actionBtnText}>RESOLVE</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.actionBtn, styles.btnClose]}
                  onPress={() => closeIncident(activeIncident.incident_id)}
                >
                  <X size={14} color="#94a3b8" />
                  <Text style={[styles.actionBtnText, { color: '#94a3b8' }]}>CLOSE</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : activeTourist ? (
            <View style={styles.commandPanel}>
              <View style={styles.commandHeader}>
                <View>
                  <Text style={styles.commandKicker}>TOURIST OPERATIONAL CONTEXT</Text>
                  <Text style={styles.commandIncidentId}>{activeTourist.full_name}</Text>
                </View>
                <TouchableOpacity onPress={() => selectTourist(null)}>
                  <X size={18} color="#94a3b8" />
                </TouchableOpacity>
              </View>
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>SAFETY STATE</Text>
                <View style={[styles.severityTag, { backgroundColor: getSafetyBadge(activeTourist.safety_state).bg, borderColor: getSafetyBadge(activeTourist.safety_state).border }]}>
                  <Text style={[styles.severityTagText, { color: getSafetyBadge(activeTourist.safety_state).text }]}>
                    {activeTourist.safety_state}
                  </Text>
                </View>
              </View>
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>TRACKING STATUS</Text>
                <Text style={styles.detailMain}>Status: {activeTourist.tracking_status} • Staleness: {activeTourist.staleness}</Text>
                <Text style={styles.detailSub}>Battery: {activeTourist.battery_pct}% • GPS Accuracy: {activeTourist.accuracy_m || 5}m</Text>
              </View>
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>IDENTITY & CREDENTIAL</Text>
                <Text style={styles.detailMain}>Verification: {activeTourist.verification_status.toUpperCase()}</Text>
                <Text style={styles.detailSub}>Credential: {activeTourist.credential_status.toUpperCase()}</Text>
              </View>
            </View>
          ) : (
            <View style={styles.commandPanelEmpty}>
              <ShieldAlert size={36} color="#475569" />
              <Text style={styles.emptyCommandTitle}>No Entity Selected</Text>
              <Text style={styles.emptyCommandSub}>
                Select an incident from the queue, a tourist marker, or a responder unit to inspect timeline events and trigger command actions.
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* ── BOTTOM PANEL: REALTIME EVENT STREAM ──────────────────────────── */}
      <View style={styles.eventStreamPanel}>
        <View style={styles.eventStreamHeader}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Activity size={16} color="#38bdf8" />
            <Text style={styles.panelTitle}>Authoritative Realtime Operational Event Stream</Text>
            <View style={[styles.liveDot, isStreamPaused && { backgroundColor: '#eab308' }]} />
            <Text style={styles.streamCountText}>{filteredEvents.length} events</Text>
          </View>

          <View style={styles.streamActions}>
            <TouchableOpacity style={styles.streamActionBtn} onPress={toggleStreamPause}>
              {isStreamPaused ? <Play size={13} color="#38bdf8" /> : <Pause size={13} color="#94a3b8" />}
              <Text style={styles.streamActionText}>{isStreamPaused ? 'RESUME' : 'PAUSE'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.streamActionBtn} onPress={clearEventStream}>
              <Trash2 size={13} color="#94a3b8" />
              <Text style={styles.streamActionText}>CLEAR</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Category Filters */}
        <View style={styles.eventCategoryRow}>
          {(['ALL', 'INCIDENTS', 'SOS', 'SAFETY', 'ZONES', 'RESPONDERS', 'TOURISTS', 'SYSTEM'] as EventCategory[]).map((cat) => (
            <TouchableOpacity
              key={cat}
              style={[styles.eventCatPill, activeEventCategory === cat && styles.activeEventCatPill]}
              onPress={() => setActiveEventCategory(cat)}
            >
              <Text style={[styles.eventCatText, activeEventCategory === cat && styles.activeEventCatText]}>
                {cat}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Event List */}
        <ScrollView style={styles.eventScroll} horizontal={false} nestedScrollEnabled>
          {filteredEvents.length === 0 ? (
            <Text style={styles.emptyEventText}>Awaiting realtime operational events...</Text>
          ) : (
            filteredEvents.map((evt) => (
              <View key={evt.event_id} style={styles.eventRow}>
                <View style={styles.eventTimeCol}>
                  <Text style={styles.eventTimeText}>
                    {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </Text>
                </View>
                <View style={[styles.eventBadge, { backgroundColor: evt.severity === 'CRITICAL' ? '#7f1d1d' : evt.severity === 'HIGH' ? '#7c2d12' : '#1e293b' }]}>
                  <Text style={styles.eventBadgeText}>{evt.event_type}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.eventTitleText}>{evt.title}</Text>
                  <Text style={styles.eventDescText} numberOfLines={1}>
                    {evt.description}
                  </Text>
                </View>
              </View>
            ))
          )}
        </ScrollView>
      </View>

      {/* ── MODALS: ASSIGN RESPONDER ──────────────────────────────────────── */}
      <Modal visible={assignModalVisible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Assign Operational Unit</Text>
            <Text style={styles.modalSubtitle}>Select an active, eligible responder unit for this incident.</Text>

            <ScrollView style={{ maxHeight: 200, marginVertical: 12 }}>
              {responderList.map((r) => (
                <TouchableOpacity
                  key={r.responder_id}
                  style={[
                    styles.modalResponderItem,
                    selectedResponderForAssign === r.responder_id && styles.modalResponderItemSelected,
                  ]}
                  onPress={() => setSelectedResponderForAssign(r.responder_id)}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={styles.modalRespTitle}>{r.unit_name || r.full_name}</Text>
                    <Text style={styles.modalRespSub}>{r.unit_type} • Status: {r.status}</Text>
                  </View>
                  {selectedResponderForAssign === r.responder_id && <Check size={16} color="#38bdf8" />}
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TextInput
              style={styles.modalInput}
              placeholder="Dispatch instructions / notes..."
              placeholderTextColor="#64748b"
              value={assignNotes}
              onChangeText={setAssignNotes}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setAssignModalVisible(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalConfirmBtn} onPress={handleAssignSubmit} disabled={actionLoading}>
                {actionLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.modalConfirmText}>Confirm Dispatch</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── MODALS: ESCALATE INCIDENT ─────────────────────────────────────── */}
      <Modal visible={escalateModalVisible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Escalate Incident</Text>
            <Text style={styles.modalSubtitle}>Elevate incident priority to notify emergency command supervisors.</Text>

            <TextInput
              style={[styles.modalInput, { minHeight: 80 }]}
              placeholder="Mandatory escalation justification..."
              placeholderTextColor="#64748b"
              multiline
              value={escalateReason}
              onChangeText={setEscalateReason}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setEscalateModalVisible(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.modalConfirmBtn, { backgroundColor: '#dc2626' }]} onPress={handleEscalateSubmit} disabled={actionLoading}>
                {actionLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.modalConfirmText}>Confirm Escalation</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── MODALS: RESOLVE INCIDENT ──────────────────────────────────────── */}
      <Modal visible={resolveModalVisible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Resolve Incident</Text>
            <Text style={styles.modalSubtitle}>Record resolution actions before archiving.</Text>

            <TextInput
              style={[styles.modalInput, { minHeight: 80 }]}
              placeholder="Resolution summary / debrief notes..."
              placeholderTextColor="#64748b"
              multiline
              value={resolveReason}
              onChangeText={setResolveReason}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setResolveModalVisible(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.modalConfirmBtn, { backgroundColor: '#15803d' }]} onPress={handleResolveSubmit} disabled={actionLoading}>
                {actionLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.modalConfirmText}>Confirm Resolution</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── MODALS: SYSTEM HEALTH DIAGNOSTICS ─────────────────────────────── */}
      <Modal visible={healthModalVisible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Subsystem Health Diagnostics</Text>
            <Text style={styles.modalSubtitle}>Operational readiness status for all platform services.</Text>

            <View style={{ marginVertical: 12, gap: 8 }}>
              <HealthRow label="Realtime WebSocket Cluster" status={systemHealth.realtime} />
              <HealthRow label="Sensor Telemetry Ingestion" status={systemHealth.telemetry} />
              <HealthRow label="ML Anomaly Engine" status={systemHealth.ml} />
              <HealthRow label="Notification & Dispatch Service" status={systemHealth.notifications} />
              <HealthRow label="Geospatial Map Tile Service" status={systemHealth.map} />
              <HealthRow label="Core Backend API" status={systemHealth.backend} />
            </View>

            <TouchableOpacity style={[styles.modalCancelBtn, { marginTop: 8 }]} onPress={() => setHealthModalVisible(false)}>
              <Text style={styles.modalCancelText}>Close Diagnostics</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* AI Copilot Operational Decision Support Panel */}
      <CopilotPanel
        visible={copilotVisible}
        onClose={() => setCopilotVisible(false)}
        activeIncidentId={selectedIncidentId || undefined}
        activeZoneId={selectedZoneId || undefined}
        activeResponderId={selectedResponderId || undefined}
      />
    </ScrollView>
  );
}


// ── COMPONENT HELPERS ────────────────────────────────────────────────────────

function KpiCard({ label, value, icon, accentColor, highlight }: any) {
  return (
    <View style={[styles.kpiCard, highlight && { borderColor: accentColor }]}>
      <View style={styles.kpiHeader}>
        <Text style={styles.kpiLabel}>{label}</Text>
        {icon}
      </View>
      <Text style={[styles.kpiValue, highlight && { color: accentColor }]}>{value}</Text>
    </View>
  );
}

function LayerButton({ label, active, onPress, color }: any) {
  return (
    <TouchableOpacity
      style={[styles.layerBtn, active && { backgroundColor: '#1e293b', borderColor: color }]}
      onPress={onPress}
    >
      <View style={[styles.layerDot, { backgroundColor: active ? color : '#475569' }]} />
      <Text style={[styles.layerBtnText, active && { color: '#f8fafc' }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function IncidentCard({ incident, isSelected, onSelect, onFocusMap, getSeverityBadge }: any) {
  const sevStyle = getSeverityBadge(incident.severity);

  return (
    <TouchableOpacity
      style={[styles.incidentCard, isSelected && styles.selectedIncidentCard]}
      onPress={onSelect}
    >
      <View style={styles.incidentCardHeader}>
        <View style={[styles.severityBadge, { backgroundColor: sevStyle.bg, borderColor: sevStyle.border }]}>
          <Text style={[styles.severityBadgeText, { color: sevStyle.text }]}>{incident.severity}</Text>
        </View>
        <Text style={styles.incidentAge}>{Math.floor((incident.age_seconds || 0) / 60)}m ago</Text>
      </View>

      <Text style={styles.incidentTitle}>{incident.tourist_name || 'Tourist Incident'}</Text>
      <Text style={styles.incidentReason} numberOfLines={2}>
        {incident.reasons?.[0] || 'Safety signal threshold exceeded'}
      </Text>

      <View style={styles.incidentFooter}>
        <Text style={styles.incidentStatus}>{incident.status}</Text>
        <TouchableOpacity style={styles.focusMapBtn} onPress={onFocusMap}>
          <MapPin size={12} color="#38bdf8" />
          <Text style={styles.focusMapText}>Focus</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

function HealthRow({ label, status }: { label: string; status: string }) {
  const isHealthy = status === 'HEALTHY';
  return (
    <View style={styles.healthRow}>
      <Text style={styles.healthLabel}>{label}</Text>
      <View style={[styles.healthBadge, isHealthy ? styles.healthHealthy : styles.healthDegraded]}>
        <Text style={styles.healthBadgeText}>{status}</Text>
      </View>
    </View>
  );
}

function EmptyState({ text, icon }: { text: string; icon: any }) {
  return (
    <View style={styles.emptyState}>
      {icon}
      <Text style={styles.emptyStateText}>{text}</Text>
    </View>
  );
}

// ── STYLES ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090d16',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 48,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    marginBottom: 16,
    gap: 12,
  },
  headerLeft: {
    flex: 1,
    minWidth: 280,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  commandPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#0c4a6e',
    borderColor: '#0284c7',
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  commandPillText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#38bdf8',
    letterSpacing: 0.5,
  },
  jurisdictionPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#1e293b',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  jurisdictionText: {
    fontSize: 11,
    color: '#94a3b8',
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#f8fafc',
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 4,
    maxWidth: 680,
    lineHeight: 18,
  },
  headerRight: {
    alignItems: 'flex-end',
  },
  headerControlRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  healthButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#0f172a',
    borderColor: '#334155',
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  healthButtonText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#38bdf8',
  },
  refreshButton: {
    padding: 7,
    backgroundColor: '#1e293b',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  kpiContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 16,
  },
  kpiCard: {
    flex: 1,
    minWidth: 120,
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 10,
    padding: 12,
  },
  kpiHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  kpiLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#9ca3af',
  },
  kpiValue: {
    fontSize: 20,
    fontWeight: '800',
    color: '#f9fafb',
    marginTop: 6,
  },
  searchFilterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  searchBox: {
    flex: 1,
    minWidth: 260,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  searchInput: {
    flex: 1,
    color: '#f9fafb',
    fontSize: 13,
    padding: 0,
  },
  layerToggles: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  layerLabel: {
    fontSize: 12,
    color: '#6b7280',
    fontWeight: '600',
    marginRight: 4,
  },
  layerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  layerDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  layerBtnText: {
    fontSize: 12,
    color: '#9ca3af',
    fontWeight: '600',
  },
  mainWorkspace: {
    gap: 14,
    marginBottom: 16,
  },
  rowLayout: {
    flexDirection: 'row',
    alignItems: 'stretch',
  },
  columnLayout: {
    flexDirection: 'column',
  },
  panel: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 14,
  },
  queueTabs: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderColor: '#1f2937',
    paddingBottom: 8,
    marginBottom: 10,
    gap: 6,
  },
  queueTab: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  activeQueueTab: {
    backgroundColor: '#1e293b',
  },
  queueTabText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9ca3af',
  },
  activeQueueTabText: {
    color: '#38bdf8',
    fontWeight: '700',
  },
  queueListScroll: {
    maxHeight: 440,
  },
  incidentCard: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  selectedIncidentCard: {
    borderColor: '#38bdf8',
    backgroundColor: '#082f49',
  },
  incidentCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  severityBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
  },
  severityBadgeText: {
    fontSize: 10,
    fontWeight: '800',
  },
  incidentAge: {
    fontSize: 10,
    color: '#6b7280',
  },
  incidentTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#f9fafb',
    marginTop: 2,
  },
  incidentReason: {
    fontSize: 11,
    color: '#9ca3af',
    marginTop: 2,
  },
  incidentFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
  incidentStatus: {
    fontSize: 10,
    fontWeight: '700',
    color: '#38bdf8',
  },
  focusMapBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#1e293b',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  focusMapText: {
    fontSize: 10,
    color: '#38bdf8',
    fontWeight: '600',
  },
  entityCard: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  selectedEntityCard: {
    borderColor: '#38bdf8',
  },
  entityHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  entityTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#f9fafb',
  },
  entitySubtitle: {
    fontSize: 11,
    color: '#9ca3af',
    marginTop: 2,
  },
  statusPill: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusAvailable: {
    backgroundColor: '#064e3b',
  },
  statusAssigned: {
    backgroundColor: '#1e3a8a',
  },
  statusPillText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#fff',
  },
  occupancyBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#0c4a6e',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  occupancyText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#38bdf8',
  },
  mapHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  panelTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#f8fafc',
  },
  mapLegend: {
    fontSize: 11,
    color: '#94a3b8',
  },
  mapWrapper: {
    borderRadius: 10,
    overflow: 'hidden',
  },
  commandPanel: {
    flex: 1,
  },
  commandHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  commandKicker: {
    fontSize: 10,
    fontWeight: '800',
    color: '#38bdf8',
  },
  commandIncidentId: {
    fontSize: 14,
    fontWeight: '700',
    color: '#f8fafc',
    marginTop: 2,
  },
  commandStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  severityTag: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
  },
  severityTagText: {
    fontSize: 11,
    fontWeight: '800',
  },
  statusTag: {
    backgroundColor: '#1e293b',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusTagText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#94a3b8',
  },
  ageTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  ageTagText: {
    fontSize: 11,
    color: '#64748b',
  },
  detailSection: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#64748b',
    marginBottom: 4,
  },
  detailMain: {
    fontSize: 13,
    fontWeight: '700',
    color: '#f8fafc',
  },
  detailSub: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 2,
  },
  reasonBullet: {
    fontSize: 11,
    color: '#cbd5e1',
    marginTop: 2,
  },
  actionGrid: {
    gap: 6,
    marginTop: 4,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
    borderRadius: 6,
  },
  btnAcknowledge: {
    backgroundColor: '#0284c7',
  },
  btnAssign: {
    backgroundColor: '#2563eb',
  },
  btnEscalate: {
    backgroundColor: '#dc2626',
  },
  btnResolve: {
    backgroundColor: '#16a34a',
  },
  btnClose: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
  },
  actionBtnText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: 0.5,
  },
  commandPanelEmpty: {
    flex: 1,
    minHeight: 280,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
  },
  emptyCommandTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#cbd5e1',
    marginTop: 12,
  },
  emptyCommandSub: {
    fontSize: 11,
    color: '#64748b',
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 16,
  },
  eventStreamPanel: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 14,
  },
  eventStreamHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#10b981',
  },
  streamCountText: {
    fontSize: 11,
    color: '#64748b',
  },
  streamActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  streamActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#1e293b',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  streamActionText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#94a3b8',
  },
  eventCategoryRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  eventCatPill: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  activeEventCatPill: {
    backgroundColor: '#0284c7',
    borderColor: '#38bdf8',
  },
  eventCatText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#94a3b8',
  },
  activeEventCatText: {
    color: '#fff',
  },
  eventScroll: {
    maxHeight: 180,
  },
  eventRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderColor: '#1e293b',
  },
  eventTimeCol: {
    width: 60,
  },
  eventTimeText: {
    fontSize: 10,
    color: '#64748b',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  eventBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  eventBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#f8fafc',
  },
  eventTitleText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#f1f5f9',
  },
  eventDescText: {
    fontSize: 10,
    color: '#94a3b8',
  },
  emptyEventText: {
    fontSize: 11,
    color: '#64748b',
    paddingVertical: 12,
    textAlign: 'center',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  emptyStateText: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 8,
    textAlign: 'center',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#f8fafc',
  },
  modalSubtitle: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 2,
  },
  modalResponderItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 6,
    padding: 8,
    marginBottom: 6,
  },
  modalResponderItemSelected: {
    borderColor: '#38bdf8',
    backgroundColor: '#082f49',
  },
  modalRespTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#f8fafc',
  },
  modalRespSub: {
    fontSize: 10,
    color: '#94a3b8',
  },
  modalInput: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: '#f8fafc',
    fontSize: 12,
    marginVertical: 8,
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 10,
  },
  modalCancelBtn: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: '#1e293b',
  },
  modalCancelText: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '600',
  },
  modalConfirmBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: '#0284c7',
  },
  modalConfirmText: {
    fontSize: 12,
    color: '#fff',
    fontWeight: '700',
  },
  healthRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderColor: '#1e293b',
  },
  healthLabel: {
    fontSize: 12,
    color: '#cbd5e1',
  },
  healthBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  healthHealthy: {
    backgroundColor: '#064e3b',
  },
  healthDegraded: {
    backgroundColor: '#7c2d12',
  },
  healthBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#fff',
  },
});
