import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Filter,
  MapPin,
  MessageSquare,
  Radio,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  UserCheck,
  Users,
  X,
  XCircle,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { incidentApi, responderApi } from '@/lib/api';
import type { IncidentMetrics, IncidentRecord, Responder, TimelineEvent } from '@/types';

export default function AdminIncidentCommandCenter() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [responders, setResponders] = useState<Responder[]>([]);
  const [metrics, setMetrics] = useState<IncidentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Filters & Search
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Selected Incident Command Modal
  const [selectedIncident, setSelectedIncident] = useState<IncidentRecord | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [actionLoading, setActionLoading] = useState(false);

  // Interactive Action Sub-Modals / Inputs
  const [selectedResponderId, setSelectedResponderId] = useState<string>('');
  const [newNoteContent, setNewNoteContent] = useState<string>('');
  const [actionReason, setActionReason] = useState<string>('');
  const [actionType, setActionType] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [statusFilter, severityFilter]);

  async function loadData() {
    try {
      setLoading(true);
      const params: Record<string, any> = {};
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (severityFilter !== 'ALL') params.severity = severityFilter;

      const [incRes, respRes, metRes] = await Promise.allSettled([
        incidentApi.getAll(params),
        responderApi.getAll({ active_only: true }),
        incidentApi.getMetrics(),
      ]);

      if (incRes.status === 'fulfilled' && incRes.value?.data?.incidents) {
        setIncidents(incRes.value.data.incidents);
      }
      if (respRes.status === 'fulfilled' && Array.isArray(respRes.value?.data)) {
        setResponders(respRes.value.data);
      }
      if (metRes.status === 'fulfilled' && metRes.value?.data) {
        setMetrics(metRes.value.data);
      }
    } catch (e) {
      console.warn('Failed to load incident command center data:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function handleSelectIncident(inc: IncidentRecord) {
    setSelectedIncident(inc);
    try {
      const res = await incidentApi.getTimeline(inc.incident_id);
      if (Array.isArray(res.data)) {
        setTimeline(res.data);
      } else {
        setTimeline(inc.timeline || []);
      }
    } catch {
      setTimeline(inc.timeline || []);
    }
  }

  async function handleAcknowledge() {
    if (!selectedIncident) return;
    setActionLoading(true);
    try {
      const res = await incidentApi.acknowledge(selectedIncident.incident_id, {
        notes: 'Operator acknowledged from Command Dashboard',
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: 'Incident Acknowledged' });
      setSelectedIncident(res.data);
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Action Failed',
        text2: e.response?.data?.detail || 'Could not acknowledge incident.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAssignResponder() {
    if (!selectedIncident || !selectedResponderId) {
      Toast.show({ type: 'error', text1: 'Select a Responder' });
      return;
    }
    setActionLoading(true);
    try {
      const res = await incidentApi.assign(selectedIncident.incident_id, {
        responder_id: selectedResponderId,
        notes: actionReason || 'Dispatched by command center',
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: 'Responder Assigned' });
      setSelectedIncident(res.data);
      setActionType(null);
      setActionReason('');
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Assignment Failed',
        text2: e.response?.data?.detail || 'Could not assign responder.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStartResponse() {
    if (!selectedIncident) return;
    setActionLoading(true);
    try {
      const res = await incidentApi.startResponse(selectedIncident.incident_id, {
        notes: 'Assigned unit marked response en route',
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: 'Response Started' });
      setSelectedIncident(res.data);
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Action Failed',
        text2: e.response?.data?.detail || 'Could not mark response started.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleEscalate() {
    if (!selectedIncident || !actionReason.trim()) {
      Toast.show({ type: 'error', text1: 'Reason Required' });
      return;
    }
    setActionLoading(true);
    try {
      const res = await incidentApi.escalate(selectedIncident.incident_id, {
        reason: actionReason.trim(),
        target_severity: 'CRITICAL',
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: 'Incident Escalated' });
      setSelectedIncident(res.data);
      setActionType(null);
      setActionReason('');
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Escalation Failed',
        text2: e.response?.data?.detail || 'Could not escalate incident.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAddNote() {
    if (!selectedIncident || !newNoteContent.trim()) return;
    setActionLoading(true);
    try {
      await incidentApi.addNote(selectedIncident.incident_id, newNoteContent.trim());
      Toast.show({ type: 'success', text1: 'Note Added' });
      setNewNoteContent('');
      // Reload incident
      const incRes = await incidentApi.getById(selectedIncident.incident_id);
      setSelectedIncident(incRes.data);
      loadData();
    } catch (e: any) {
      Toast.show({ type: 'error', text1: 'Note Failed' });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleResolve() {
    if (!selectedIncident || !actionReason.trim()) {
      Toast.show({ type: 'error', text1: 'Resolution Reason Required' });
      return;
    }
    setActionLoading(true);
    try {
      const res = await incidentApi.resolve(selectedIncident.incident_id, {
        resolution_reason: actionReason.trim(),
        resolution_category: 'TOURIST_SAFE',
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: 'Incident Resolved' });
      setSelectedIncident(res.data);
      setActionType(null);
      setActionReason('');
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Resolution Failed',
        text2: e.response?.data?.detail || 'Could not resolve incident.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancelOrFalseAlarm(isFalseAlarm: boolean) {
    if (!selectedIncident || !actionReason.trim()) {
      Toast.show({ type: 'error', text1: 'Cancellation Reason Required' });
      return;
    }
    setActionLoading(true);
    try {
      const res = await incidentApi.cancel(selectedIncident.incident_id, {
        cancellation_reason: actionReason.trim(),
        is_false_alarm: isFalseAlarm,
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: isFalseAlarm ? 'Marked False Alarm' : 'Incident Cancelled' });
      setSelectedIncident(res.data);
      setActionType(null);
      setActionReason('');
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Action Failed',
        text2: e.response?.data?.detail || 'Could not cancel incident.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleClose() {
    if (!selectedIncident) return;
    setActionLoading(true);
    try {
      const res = await incidentApi.close(selectedIncident.incident_id, {
        version: selectedIncident.version,
      });
      Toast.show({ type: 'success', text1: 'Incident Closed & Archived' });
      setSelectedIncident(res.data);
      loadData();
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Closure Failed',
        text2: e.response?.data?.detail || 'Must be resolved or cancelled before closing.',
      });
    } finally {
      setActionLoading(false);
    }
  }

  const filteredIncidents = incidents.filter((inc) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      inc.incident_id.toLowerCase().includes(q) ||
      inc.tourist_id.toLowerCase().includes(q) ||
      (inc.reasons && inc.reasons.some((r) => r.toLowerCase().includes(q)))
    );
  });

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadData(); }} />}
    >
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Incident Command Center</Text>
          <Text style={styles.subtitle}>Real-time emergency response, responder coordination & audit timeline</Text>
        </View>
        <TouchableOpacity onPress={loadData} style={styles.refreshBtn}>
          <RefreshCw size={16} color="#1a365d" />
        </TouchableOpacity>
      </View>

      {/* Metrics Strip */}
      {metrics && (
        <View style={styles.metricsGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{metrics.open_incidents + metrics.escalated_incidents}</Text>
            <Text style={styles.metricLabel}>Active / Urgent</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={[styles.metricValue, { color: '#ef4444' }]}>{metrics.escalated_incidents}</Text>
            <Text style={styles.metricLabel}>Escalated</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={[styles.metricValue, { color: '#3b82f6' }]}>{metrics.acknowledged_incidents}</Text>
            <Text style={styles.metricLabel}>In Assessment</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={[styles.metricValue, { color: '#10b981' }]}>{metrics.resolved_incidents}</Text>
            <Text style={styles.metricLabel}>Resolved</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>
              {metrics.avg_time_to_acknowledge_seconds ? `${Math.round(metrics.avg_time_to_acknowledge_seconds)}s` : '—'}
            </Text>
            <Text style={styles.metricLabel}>Avg Ack Time</Text>
          </View>
        </View>
      )}

      {/* Search & Filter Bar */}
      <View style={styles.filterSection}>
        <View style={styles.searchBar}>
          <Search size={16} color="#64748b" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search incident ID, tourist ID, or reason..."
            placeholderTextColor="#94a3b8"
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <X size={16} color="#64748b" />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Status Filter Chips */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterChipsRow}>
          {['ALL', 'OPEN', 'ACKNOWLEDGED', 'ASSESSING', 'ASSIGNED', 'RESPONDING', 'ESCALATED', 'RESOLVED', 'CLOSED'].map((st) => (
            <TouchableOpacity
              key={st}
              onPress={() => setStatusFilter(st)}
              style={[styles.chip, statusFilter === st && styles.chipActive]}
            >
              <Text style={[styles.chipText, statusFilter === st && styles.chipTextActive]}>{st}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Incidents List */}
      {loading && !refreshing ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#1a365d" />
          <Text style={styles.loadingText}>Loading incident command feed...</Text>
        </View>
      ) : filteredIncidents.length === 0 ? (
        <View style={styles.emptyBox}>
          <Shield size={40} color="#94a3b8" />
          <Text style={styles.emptyTitle}>No Incidents Found</Text>
          <Text style={styles.emptySubtitle}>There are currently no incidents matching the selected filter criteria.</Text>
        </View>
      ) : (
        <View style={styles.incidentList}>
          {filteredIncidents.map((inc) => {
            const isCritical = inc.severity === 'CRITICAL' || inc.status === 'ESCALATED';
            const isManualSOS = inc.source === 'MANUAL_SOS';
            return (
              <TouchableOpacity
                key={inc.incident_id}
                onPress={() => handleSelectIncident(inc)}
                style={[
                  styles.incidentCard,
                  isCritical && styles.incidentCardCritical,
                ]}
              >
                <View style={styles.cardHeader}>
                  <View style={styles.cardHeaderLeft}>
                    {isManualSOS ? (
                      <View style={styles.sosBadge}>
                        <Radio size={12} color="#fff" />
                        <Text style={styles.sosBadgeText}>MANUAL SOS</Text>
                      </View>
                    ) : (
                      <View style={styles.aiBadge}>
                        <ShieldAlert size={12} color="#1e293b" />
                        <Text style={styles.aiBadgeText}>SAFETY ENGINE</Text>
                      </View>
                    )}
                    <Text style={styles.incidentIdText}>{inc.incident_id}</Text>
                  </View>

                  <View style={[styles.statusTag, getStatusTagStyle(inc.status)]}>
                    <Text style={styles.statusTagText}>{inc.status}</Text>
                  </View>
                </View>

                <Text style={styles.cardTourist}>
                  Tourist: <Text style={styles.cardTouristBold}>{inc.tourist_id}</Text>
                </Text>

                <Text style={styles.cardReason} numberOfLines={2}>
                  {inc.reasons?.join('; ') || 'No reason specified'}
                </Text>

                {inc.location_data && (
                  <View style={styles.cardLocationRow}>
                    <MapPin size={12} color="#64748b" />
                    <Text style={styles.cardLocationText}>
                      {inc.location_data.latitude.toFixed(4)}, {inc.location_data.longitude.toFixed(4)}
                      {inc.location_data.zone_name ? ` (${inc.location_data.zone_name})` : ''}
                    </Text>
                  </View>
                )}

                <View style={styles.cardFooter}>
                  <View style={styles.cardFooterTime}>
                    <Clock size={12} color="#94a3b8" />
                    <Text style={styles.cardTimeText}>
                      Started {new Date(inc.started_at).toLocaleTimeString()}
                    </Text>
                  </View>
                  <View style={styles.cardFooterAction}>
                    <Text style={styles.cardInspectText}>Inspect & Act</Text>
                    <ArrowUpRight size={14} color="#1a365d" />
                  </View>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      )}

      {/* INCIDENT DETAIL & COMMAND MODAL */}
      <Modal visible={!!selectedIncident} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={styles.commandModalContainer}>
            {selectedIncident && (
              <>
                {/* Modal Header */}
                <View style={styles.commandHeader}>
                  <View>
                    <View style={styles.headerRow}>
                      <Text style={styles.commandTitle}>{selectedIncident.incident_id}</Text>
                      <View style={[styles.statusTag, getStatusTagStyle(selectedIncident.status)]}>
                        <Text style={styles.statusTagText}>{selectedIncident.status}</Text>
                      </View>
                    </View>
                    <Text style={styles.commandSubtitle}>
                      Source: {selectedIncident.source} | Severity: {selectedIncident.severity} | Tourist: {selectedIncident.tourist_id}
                    </Text>
                  </View>
                  <TouchableOpacity onPress={() => setSelectedIncident(null)} style={styles.closeBtn}>
                    <X size={20} color="#64748b" />
                  </TouchableOpacity>
                </View>

                <ScrollView style={styles.commandBody} contentContainerStyle={{ paddingBottom: 24 }}>
                  {/* Action Bar (Top) */}
                  <View style={styles.actionBar}>
                    {selectedIncident.status === 'OPEN' && (
                      <TouchableOpacity
                        onPress={handleAcknowledge}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#3b82f6' }]}
                      >
                        <UserCheck size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Acknowledge</Text>
                      </TouchableOpacity>
                    )}

                    {['OPEN', 'ACKNOWLEDGED', 'ASSESSING'].includes(selectedIncident.status) && (
                      <TouchableOpacity
                        onPress={() => setActionType('ASSIGN')}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#0284c7' }]}
                      >
                        <Users size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Assign Responder</Text>
                      </TouchableOpacity>
                    )}

                    {selectedIncident.status === 'ASSIGNED' && (
                      <TouchableOpacity
                        onPress={handleStartResponse}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#8b5cf6' }]}
                      >
                        <Radio size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Start Response</Text>
                      </TouchableOpacity>
                    )}

                    {!['RESOLVED', 'CANCELLED', 'CLOSED'].includes(selectedIncident.status) && (
                      <TouchableOpacity
                        onPress={() => setActionType('ESCALATE')}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#ef4444' }]}
                      >
                        <AlertTriangle size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Escalate</Text>
                      </TouchableOpacity>
                    )}

                    {!['RESOLVED', 'CANCELLED', 'CLOSED'].includes(selectedIncident.status) && (
                      <TouchableOpacity
                        onPress={() => setActionType('RESOLVE')}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#10b981' }]}
                      >
                        <CheckCircle2 size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Resolve</Text>
                      </TouchableOpacity>
                    )}

                    {!['RESOLVED', 'CANCELLED', 'CLOSED'].includes(selectedIncident.status) && (
                      <TouchableOpacity
                        onPress={() => setActionType('CANCEL')}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#64748b' }]}
                      >
                        <XCircle size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Cancel / False Alarm</Text>
                      </TouchableOpacity>
                    )}

                    {['RESOLVED', 'CANCELLED'].includes(selectedIncident.status) && (
                      <TouchableOpacity
                        onPress={handleClose}
                        disabled={actionLoading}
                        style={[styles.cmdBtn, { backgroundColor: '#334155' }]}
                      >
                        <Shield size={16} color="#fff" />
                        <Text style={styles.cmdBtnText}>Close & Archive</Text>
                      </TouchableOpacity>
                    )}
                  </View>

                  {/* Location & Context Panel */}
                  {selectedIncident.location_data && (
                    <View style={styles.sectionCard}>
                      <Text style={styles.sectionTitle}>Authoritative GPS & Zone Context</Text>
                      <View style={styles.locationDetailGrid}>
                        <View style={styles.locItem}>
                          <Text style={styles.locItemLabel}>Coordinates</Text>
                          <Text style={styles.locItemValue}>
                            {selectedIncident.location_data.latitude.toFixed(5)}, {selectedIncident.location_data.longitude.toFixed(5)}
                          </Text>
                        </View>
                        <View style={styles.locItem}>
                          <Text style={styles.locItemLabel}>Location Status</Text>
                          <Text style={styles.locItemValue}>{selectedIncident.location_data.location_status || 'CURRENT'}</Text>
                        </View>
                        <View style={styles.locItem}>
                          <Text style={styles.locItemLabel}>Zone Context</Text>
                          <Text style={styles.locItemValue}>
                            {selectedIncident.location_data.zone_name || 'Open Area'} ({selectedIncident.location_data.zone_risk || 'LOW'})
                          </Text>
                        </View>
                      </View>
                    </View>
                  )}

                  {/* Reasons & Signals */}
                  <View style={styles.sectionCard}>
                    <Text style={styles.sectionTitle}>Incident Triggers</Text>
                    {selectedIncident.reasons?.map((r, idx) => (
                      <Text key={idx} style={styles.reasonBullet}>• {r}</Text>
                    ))}
                  </View>

                  {/* Immutable Timeline */}
                  <View style={styles.sectionCard}>
                    <Text style={styles.sectionTitle}>Chronological Audit Timeline</Text>
                    {timeline.length === 0 ? (
                      <Text style={styles.emptySub}>No timeline records available</Text>
                    ) : (
                      timeline.map((tle, i) => (
                        <View key={tle.event_id || i} style={styles.timelineRow}>
                          <View style={styles.timelineDot} />
                          <View style={styles.timelineContent}>
                            <View style={styles.timelineHeader}>
                              <Text style={styles.timelineAction}>{tle.action}</Text>
                              <Text style={styles.timelineTime}>
                                {new Date(tle.timestamp).toLocaleTimeString()}
                              </Text>
                            </View>
                            <Text style={styles.timelineActor}>
                              By: {tle.actor_type} ({tle.actor_id})
                            </Text>
                            {tle.reason && <Text style={styles.timelineReason}>{tle.reason}</Text>}
                          </View>
                        </View>
                      ))
                    )}
                  </View>

                  {/* Operational Notes */}
                  <View style={styles.sectionCard}>
                    <Text style={styles.sectionTitle}>Operational Notes</Text>
                    {selectedIncident.notes_list?.map((n, i) => (
                      <View key={n.note_id || i} style={styles.noteItem}>
                        <View style={styles.noteHeader}>
                          <Text style={styles.noteAuthor}>{n.author_role.toUpperCase()} ({n.author_id})</Text>
                          <Text style={styles.noteTime}>{new Date(n.timestamp).toLocaleTimeString()}</Text>
                        </View>
                        <Text style={styles.noteContent}>{n.content}</Text>
                      </View>
                    ))}

                    {/* Add note input */}
                    <View style={styles.addNoteRow}>
                      <TextInput
                        style={styles.addNoteInput}
                        placeholder="Add operational note..."
                        placeholderTextColor="#94a3b8"
                        value={newNoteContent}
                        onChangeText={setNewNoteContent}
                      />
                      <TouchableOpacity
                        onPress={handleAddNote}
                        disabled={actionLoading || !newNoteContent.trim()}
                        style={styles.addNoteBtn}
                      >
                        <MessageSquare size={16} color="#fff" />
                      </TouchableOpacity>
                    </View>
                  </View>
                </ScrollView>
              </>
            )}
          </View>
        </View>
      </Modal>

      {/* ACTION SUB-MODAL */}
      <Modal visible={!!actionType} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.subModalContainer}>
            <Text style={styles.subModalTitle}>
              {actionType === 'ASSIGN' && 'Assign Responder Unit'}
              {actionType === 'ESCALATE' && 'Escalate Incident Urgency'}
              {actionType === 'RESOLVE' && 'Resolve Safety Incident'}
              {actionType === 'CANCEL' && 'Cancel Incident / Mark False Alarm'}
            </Text>

            {actionType === 'ASSIGN' && (
              <View style={styles.responderPickerBox}>
                <Text style={styles.subModalLabel}>Select Available Responder:</Text>
                <ScrollView style={{ maxHeight: 180 }}>
                  {responders.map((r) => (
                    <TouchableOpacity
                      key={r.responder_id}
                      onPress={() => setSelectedResponderId(r.responder_id)}
                      style={[
                        styles.responderChoice,
                        selectedResponderId === r.responder_id && styles.responderChoiceSelected,
                      ]}
                    >
                      <Text style={styles.respChoiceName}>{r.name} ({r.type})</Text>
                      <Text style={styles.respChoiceStatus}>{r.status}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            )}

            <Text style={styles.subModalLabel}>Mandatory Explanation / Notes:</Text>
            <TextInput
              style={styles.subModalInput}
              placeholder="Provide reason for this action..."
              placeholderTextColor="#94a3b8"
              value={actionReason}
              onChangeText={setActionReason}
              multiline
              numberOfLines={3}
            />

            <View style={styles.subModalActions}>
              <TouchableOpacity
                onPress={() => { setActionType(null); setActionReason(''); }}
                style={styles.subModalBtnCancel}
                disabled={actionLoading}
              >
                <Text style={styles.subModalBtnTextCancel}>Cancel</Text>
              </TouchableOpacity>

              {actionType === 'ASSIGN' && (
                <TouchableOpacity
                  onPress={handleAssignResponder}
                  style={[styles.subModalBtnSubmit, { backgroundColor: '#0284c7' }]}
                  disabled={actionLoading || !selectedResponderId}
                >
                  <Text style={styles.subModalBtnTextSubmit}>Confirm Assignment</Text>
                </TouchableOpacity>
              )}

              {actionType === 'ESCALATE' && (
                <TouchableOpacity
                  onPress={handleEscalate}
                  style={[styles.subModalBtnSubmit, { backgroundColor: '#ef4444' }]}
                  disabled={actionLoading || !actionReason.trim()}
                >
                  <Text style={styles.subModalBtnTextSubmit}>Confirm Escalation</Text>
                </TouchableOpacity>
              )}

              {actionType === 'RESOLVE' && (
                <TouchableOpacity
                  onPress={handleResolve}
                  style={[styles.subModalBtnSubmit, { backgroundColor: '#10b981' }]}
                  disabled={actionLoading || !actionReason.trim()}
                >
                  <Text style={styles.subModalBtnTextSubmit}>Confirm Resolution</Text>
                </TouchableOpacity>
              )}

              {actionType === 'CANCEL' && (
                <>
                  <TouchableOpacity
                    onPress={() => handleCancelOrFalseAlarm(true)}
                    style={[styles.subModalBtnSubmit, { backgroundColor: '#eab308' }]}
                    disabled={actionLoading || !actionReason.trim()}
                  >
                    <Text style={styles.subModalBtnTextSubmit}>False Alarm</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => handleCancelOrFalseAlarm(false)}
                    style={[styles.subModalBtnSubmit, { backgroundColor: '#64748b' }]}
                    disabled={actionLoading || !actionReason.trim()}
                  >
                    <Text style={styles.subModalBtnTextSubmit}>Cancel</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function getStatusTagStyle(status: string) {
  switch (status) {
    case 'OPEN':
      return { backgroundColor: '#fef2f2', borderColor: '#fecdd3', color: '#b91c1c' };
    case 'ACKNOWLEDGED':
    case 'ASSESSING':
      return { backgroundColor: '#eff6ff', borderColor: '#bfdbfe', color: '#1d4ed8' };
    case 'ASSIGNED':
    case 'RESPONDING':
      return { backgroundColor: '#f5f3ff', borderColor: '#ddd6fe', color: '#6d28d9' };
    case 'ESCALATED':
      return { backgroundColor: '#450a0a', borderColor: '#ef4444', color: '#ffffff' };
    case 'RESOLVED':
    case 'CLOSED':
      return { backgroundColor: '#ecfdf5', borderColor: '#a7f3d0', color: '#047857' };
    case 'CANCELLED':
      return { backgroundColor: '#f8fafc', borderColor: '#cbd5e1', color: '#475569' };
    default:
      return { backgroundColor: '#f1f5f9', borderColor: '#e2e8f0', color: '#334155' };
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  content: { padding: 16, gap: 16 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 4, color: '#64748b', fontSize: 13 },
  refreshBtn: {
    padding: 10,
    backgroundColor: '#e2e8f0',
    borderRadius: 10,
  },
  metricsGrid: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  metricCard: {
    flex: 1,
    minWidth: 100,
    backgroundColor: '#ffffff',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    alignItems: 'center',
  },
  metricValue: { fontSize: 20, fontWeight: 'bold', color: '#1e293b' },
  metricLabel: { fontSize: 11, color: '#64748b', marginTop: 2 },
  filterSection: { gap: 10 },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
  },
  searchInput: { flex: 1, color: '#0f172a', fontSize: 14 },
  filterChipsRow: { flexDirection: 'row', gap: 6 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: '#e2e8f0',
    marginRight: 6,
  },
  chipActive: { backgroundColor: '#1a365d' },
  chipText: { fontSize: 12, fontWeight: '600', color: '#475569' },
  chipTextActive: { color: '#ffffff' },
  loadingBox: { padding: 40, alignItems: 'center', gap: 12 },
  loadingText: { color: '#64748b', fontSize: 14 },
  emptyBox: {
    padding: 40,
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 8,
  },
  emptyTitle: { fontSize: 16, fontWeight: 'bold', color: '#334155' },
  emptySubtitle: { fontSize: 13, color: '#94a3b8', textAlign: 'center' },
  incidentList: { gap: 12 },
  incidentCard: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    gap: 8,
  },
  incidentCardCritical: {
    borderColor: '#fca5a5',
    backgroundColor: '#fff1f2',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sosBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#ef4444',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  sosBadgeText: { color: '#ffffff', fontSize: 10, fontWeight: 'bold' },
  aiBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#fed7aa',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  aiBadgeText: { color: '#7c2d12', fontSize: 10, fontWeight: 'bold' },
  incidentIdText: { fontSize: 14, fontWeight: 'bold', color: '#0f172a' },
  statusTag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  statusTagText: { fontSize: 11, fontWeight: 'bold' },
  cardTourist: { fontSize: 13, color: '#475569' },
  cardTouristBold: { fontWeight: '600', color: '#0f172a' },
  cardReason: { fontSize: 13, color: '#334155', lineHeight: 18 },
  cardLocationRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  cardLocationText: { fontSize: 12, color: '#64748b' },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
  },
  cardFooterTime: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  cardTimeText: { fontSize: 11, color: '#94a3b8' },
  cardFooterAction: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  cardInspectText: { fontSize: 12, fontWeight: 'bold', color: '#1a365d' },

  // Modal Styles
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  commandModalContainer: {
    width: '100%',
    maxWidth: 720,
    maxHeight: '90%',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    overflow: 'hidden',
  },
  commandHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    backgroundColor: '#f8fafc',
  },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  commandTitle: { fontSize: 18, fontWeight: 'bold', color: '#0f172a' },
  commandSubtitle: { fontSize: 12, color: '#64748b', marginTop: 4 },
  closeBtn: { padding: 6 },
  commandBody: { padding: 16, gap: 16 },
  actionBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  cmdBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 8,
  },
  cmdBtnText: { color: '#ffffff', fontSize: 13, fontWeight: '600' },
  sectionCard: {
    backgroundColor: '#f8fafc',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 14, fontWeight: 'bold', color: '#1e293b', marginBottom: 8 },
  locationDetailGrid: { flexDirection: 'row', gap: 16, flexWrap: 'wrap' },
  locItem: { minWidth: 140 },
  locItemLabel: { fontSize: 11, color: '#64748b' },
  locItemValue: { fontSize: 13, fontWeight: '600', color: '#0f172a', marginTop: 2 },
  reasonBullet: { fontSize: 13, color: '#334155', marginBottom: 4 },
  timelineRow: {
    flexDirection: 'row',
    gap: 12,
    borderLeftWidth: 2,
    borderLeftColor: '#cbd5e1',
    paddingLeft: 12,
    paddingBottom: 14,
    marginLeft: 6,
  },
  timelineDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#1a365d',
    position: 'absolute',
    left: -6,
    top: 3,
  },
  timelineContent: { flex: 1 },
  timelineHeader: { flexDirection: 'row', justifyContent: 'space-between' },
  timelineAction: { fontSize: 13, fontWeight: 'bold', color: '#0f172a' },
  timelineTime: { fontSize: 11, color: '#94a3b8' },
  timelineActor: { fontSize: 11, color: '#64748b', marginTop: 2 },
  timelineReason: { fontSize: 12, color: '#334155', marginTop: 4 },
  emptySub: { fontSize: 12, color: '#94a3b8', fontStyle: 'italic' },
  noteItem: {
    backgroundColor: '#ffffff',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 8,
  },
  noteHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  noteAuthor: { fontSize: 11, fontWeight: 'bold', color: '#0284c7' },
  noteTime: { fontSize: 10, color: '#94a3b8' },
  noteContent: { fontSize: 13, color: '#334155' },
  addNoteRow: { flexDirection: 'row', gap: 8, marginTop: 6 },
  addNoteInput: {
    flex: 1,
    backgroundColor: '#ffffff',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
  },
  addNoteBtn: {
    backgroundColor: '#1a365d',
    borderRadius: 8,
    paddingHorizontal: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Sub Modal
  subModalContainer: {
    width: '100%',
    maxWidth: 460,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 20,
    gap: 12,
  },
  subModalTitle: { fontSize: 16, fontWeight: 'bold', color: '#0f172a' },
  subModalLabel: { fontSize: 13, fontWeight: '600', color: '#475569' },
  responderPickerBox: { maxHeight: 200, marginBottom: 8 },
  responderChoice: {
    padding: 10,
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 6,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  responderChoiceSelected: {
    borderColor: '#0284c7',
    backgroundColor: '#f0f9ff',
  },
  respChoiceName: { fontSize: 13, fontWeight: '600', color: '#0f172a' },
  respChoiceStatus: { fontSize: 11, color: '#64748b' },
  subModalInput: {
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    padding: 10,
    fontSize: 13,
    textAlignVertical: 'top',
  },
  subModalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 8,
  },
  subModalBtnCancel: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#e2e8f0',
  },
  subModalBtnTextCancel: { fontSize: 13, color: '#475569', fontWeight: '600' },
  subModalBtnSubmit: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  subModalBtnTextSubmit: { fontSize: 13, color: '#ffffff', fontWeight: '600' },
});
