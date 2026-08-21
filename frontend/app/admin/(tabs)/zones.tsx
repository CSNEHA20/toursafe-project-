import React, { useState, useEffect, useCallback } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Modal,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import {
  MapPinned,
  Plus,
  Search,
  Filter,
  Eye,
  Edit3,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  History,
  X,
  RefreshCw,
  Layers,
  Sparkles,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { zoneApi } from '@/lib/api';
import type { Zone, ZoneType, ZoneRiskLevel, ZoneStatus, ZoneAudit } from '@/types';

// Preset boundary geometries for quick development testing
const TEMPLATE_PRESETS = [
  {
    name: 'Kodaikanal Corridor Template',
    lon: 77.4892,
    lat: 10.2381,
    coordinates: [
      [77.483, 10.243],
      [77.495, 10.243],
      [77.496, 10.232],
      [77.484, 10.231],
      [77.483, 10.243],
    ],
  },
  {
    name: 'Ooty Nilgiris Template',
    lon: 76.695,
    lat: 11.4102,
    coordinates: [
      [76.689, 11.415],
      [76.701, 11.415],
      [76.701, 11.405],
      [76.689, 11.405],
      [76.689, 11.415],
    ],
  },
  {
    name: 'Munnar High-Range Template',
    lon: 77.0595,
    lat: 10.0892,
    coordinates: [
      [77.05, 10.095],
      [77.065, 10.095],
      [77.065, 10.082],
      [77.05, 10.082],
      [77.05, 10.095],
    ],
  },
];

export default function AdminZones() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');

  // Modals
  const [detailModalVisible, setDetailModalVisible] = useState<boolean>(false);
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);
  const [zoneAudits, setZoneAudits] = useState<ZoneAudit[]>([]);
  const [loadingAudits, setLoadingAudits] = useState<boolean>(false);

  const [createModalVisible, setCreateModalVisible] = useState<boolean>(false);
  const [editModalVisible, setEditModalVisible] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Form State
  const [formName, setFormName] = useState<string>('');
  const [formDescription, setFormDescription] = useState<string>('');
  const [formType, setFormType] = useState<ZoneType>('safe');
  const [formRisk, setFormRisk] = useState<ZoneRiskLevel>('low');
  const [formStatus, setFormStatus] = useState<ZoneStatus>('active');
  const [formCenterLon, setFormCenterLon] = useState<string>('77.4892');
  const [formCenterLat, setFormCenterLat] = useState<string>('10.2381');
  const [formGeoJsonText, setFormGeoJsonText] = useState<string>('');

  const fetchZones = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = {};
      if (searchQuery.trim()) params.q = searchQuery.trim();
      if (statusFilter !== 'all') params.status = statusFilter;
      if (typeFilter !== 'all') params.zone_type = typeFilter;
      if (riskFilter !== 'all') params.risk_level = riskFilter;

      const response = await zoneApi.getAuthorityZones(params);
      setZones(response.data?.items || []);
    } catch (err: any) {
      console.error('Failed to load authority zones:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to fetch zones');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, statusFilter, typeFilter, riskFilter]);

  useEffect(() => {
    fetchZones();
  }, [fetchZones]);

  const openDetails = async (zone: Zone) => {
    setSelectedZone(zone);
    setDetailModalVisible(true);
    setLoadingAudits(true);
    try {
      const resp = await zoneApi.getAudits(zone.id || zone.zone_id);
      setZoneAudits(resp.data || []);
    } catch (e) {
      console.error('Failed to load audits:', e);
      setZoneAudits([]);
    } finally {
      setLoadingAudits(false);
    }
  };

  const openCreateModal = () => {
    setFormName('');
    setFormDescription('');
    setFormType('safe');
    setFormRisk('low');
    setFormStatus('active');
    setFormCenterLon('77.4892');
    setFormCenterLat('10.2381');
    setFormGeoJsonText(
      JSON.stringify(
        {
          type: 'Polygon',
          coordinates: [TEMPLATE_PRESETS[0].coordinates],
        },
        null,
        2
      )
    );
    setCreateModalVisible(true);
  };

  const openEditModal = (zone: Zone) => {
    setSelectedZone(zone);
    setFormName(zone.name);
    setFormDescription(zone.description || '');
    setFormType(zone.zone_type);
    setFormRisk(zone.risk_level);
    setFormStatus(zone.status);
    setFormCenterLon(zone.center?.coordinates ? String(zone.center.coordinates[0]) : '77.4892');
    setFormCenterLat(zone.center?.coordinates ? String(zone.center.coordinates[1]) : '10.2381');
    setFormGeoJsonText(JSON.stringify(zone.boundary, null, 2));
    setEditModalVisible(true);
  };

  const applyTemplate = (preset: typeof TEMPLATE_PRESETS[0]) => {
    setFormCenterLon(String(preset.lon));
    setFormCenterLat(String(preset.lat));
    setFormGeoJsonText(
      JSON.stringify(
        {
          type: 'Polygon',
          coordinates: [preset.coordinates],
        },
        null,
        2
      )
    );
    Toast.show({
      type: 'info',
      text1: 'Template Applied',
      text2: `Boundary coordinates set for ${preset.name}`,
    });
  };

  const handleCreateSubmit = async () => {
    if (!formName.trim()) {
      Toast.show({ type: 'error', text1: 'Validation Error', text2: 'Zone name is required.' });
      return;
    }

    let parsedBoundary: any;
    try {
      parsedBoundary = JSON.parse(formGeoJsonText);
    } catch {
      Toast.show({ type: 'error', text1: 'Invalid GeoJSON', text2: 'Boundary must be valid JSON format.' });
      return;
    }

    const lon = parseFloat(formCenterLon);
    const lat = parseFloat(formCenterLat);
    if (isNaN(lon) || isNaN(lat)) {
      Toast.show({ type: 'error', text1: 'Invalid Center', text2: 'Center coordinates must be valid numbers.' });
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: Partial<Zone> = {
        name: formName.trim(),
        description: formDescription.trim(),
        zone_type: formType,
        risk_level: formRisk,
        status: formStatus,
        boundary: parsedBoundary,
        center: { type: 'Point', coordinates: [lon, lat] },
        properties: { dataset: 'DEVELOPMENT GEOMETRY' },
      };

      await zoneApi.create(payload);
      Toast.show({ type: 'success', text1: 'Zone Created', text2: `Zone '${formName}' saved to MongoDB.` });
      setCreateModalVisible(false);
      fetchZones();
    } catch (err: any) {
      console.error('Failed to create zone:', err);
      Toast.show({
        type: 'error',
        text1: 'Creation Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not save zone.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async () => {
    if (!selectedZone) return;
    if (!formName.trim()) {
      Toast.show({ type: 'error', text1: 'Validation Error', text2: 'Zone name is required.' });
      return;
    }

    let parsedBoundary: any;
    try {
      parsedBoundary = JSON.parse(formGeoJsonText);
    } catch {
      Toast.show({ type: 'error', text1: 'Invalid GeoJSON', text2: 'Boundary must be valid JSON format.' });
      return;
    }

    const lon = parseFloat(formCenterLon);
    const lat = parseFloat(formCenterLat);

    setIsSubmitting(true);
    try {
      const payload: Partial<Zone> = {
        name: formName.trim(),
        description: formDescription.trim(),
        zone_type: formType,
        risk_level: formRisk,
        status: formStatus,
        boundary: parsedBoundary,
        center: { type: 'Point', coordinates: [lon, lat] },
      };

      await zoneApi.update(selectedZone.id || selectedZone.zone_id, payload);
      Toast.show({ type: 'success', text1: 'Zone Updated', text2: `Zone '${formName}' updated & audited.` });
      setEditModalVisible(false);
      fetchZones();
    } catch (err: any) {
      console.error('Failed to update zone:', err);
      Toast.show({
        type: 'error',
        text1: 'Update Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not update zone.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStatusToggle = async (zone: Zone, targetStatus: ZoneStatus) => {
    try {
      await zoneApi.update(zone.id || zone.zone_id, { status: targetStatus });
      Toast.show({
        type: 'success',
        text1: 'Status Updated',
        text2: `Zone status changed to '${targetStatus}'.`,
      });
      fetchZones();
      if (selectedZone && (selectedZone.id === zone.id || selectedZone.zone_id === zone.zone_id)) {
        setSelectedZone({ ...selectedZone, status: targetStatus });
      }
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Transition Error',
        text2: err?.response?.data?.detail || 'Invalid status transition.',
      });
    }
  };

  const handleDelete = (zone: Zone) => {
    Alert.alert(
      'Deactivate Zone',
      `Are you sure you want to deactivate '${zone.name}'? This will mark it inactive and record an audit log.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Deactivate',
          style: 'destructive',
          onPress: async () => {
            try {
              await zoneApi.delete(zone.id || zone.zone_id);
              Toast.show({
                type: 'success',
                text1: 'Zone Deactivated',
                text2: `Zone '${zone.name}' is now inactive.`,
              });
              setDetailModalVisible(false);
              fetchZones();
            } catch (err: any) {
              Toast.show({
                type: 'error',
                text1: 'Delete Failed',
                text2: err?.response?.data?.detail || 'Could not deactivate zone.',
              });
            }
          },
        },
      ]
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View>
            <Text style={styles.title}>Safety Zones</Text>
            <Text style={styles.subtitle}>Authoritative GeoJSON Zone Management & Audit Trails</Text>
          </View>
          <TouchableOpacity onPress={openCreateModal} style={styles.createBtn}>
            <Plus size={18} color="#fff" />
            <Text style={styles.createBtnText}>Create Zone</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Search & Filter Bar */}
      <View style={styles.searchCard}>
        <View style={styles.searchInputRow}>
          <Search size={16} color="#64748b" />
          <TextInput
            placeholder="Search zones by name or description..."
            placeholderTextColor="#94a3b8"
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <X size={16} color="#64748b" />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Filter Pills */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterScroll}>
          <Text style={styles.filterLabel}>Type:</Text>
          {['all', 'safe', 'warning', 'restricted'].map((t) => (
            <TouchableOpacity
              key={`type-${t}`}
              onPress={() => setTypeFilter(t)}
              style={[styles.filterChip, typeFilter === t && styles.filterChipActive]}
            >
              <Text style={[styles.filterChipText, typeFilter === t && styles.filterChipTextActive]}>
                {t.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}

          <Text style={[styles.filterLabel, { marginLeft: 12 }]}>Risk:</Text>
          {['all', 'low', 'medium', 'high', 'critical'].map((r) => (
            <TouchableOpacity
              key={`risk-${r}`}
              onPress={() => setRiskFilter(r)}
              style={[styles.filterChip, riskFilter === r && styles.filterChipActive]}
            >
              <Text style={[styles.filterChipText, riskFilter === r && styles.filterChipTextActive]}>
                {r.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}

          <Text style={[styles.filterLabel, { marginLeft: 12 }]}>Status:</Text>
          {['all', 'active', 'inactive', 'draft'].map((s) => (
            <TouchableOpacity
              key={`status-${s}`}
              onPress={() => setStatusFilter(s)}
              style={[styles.filterChip, statusFilter === s && styles.filterChipActive]}
            >
              <Text style={[styles.filterChipText, statusFilter === s && styles.filterChipTextActive]}>
                {s.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Zone List */}
      {loading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#1a365d" />
          <Text style={styles.loadingText}>Fetching authoritative zones from MongoDB...</Text>
        </View>
      ) : error ? (
        <View style={styles.errorCard}>
          <AlertTriangle size={24} color="#ef4444" />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity onPress={fetchZones} style={styles.retryBtn}>
            <RefreshCw size={14} color="#fff" />
            <Text style={styles.retryBtnText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : zones.length === 0 ? (
        <View style={styles.emptyCard}>
          <Layers size={32} color="#94a3b8" />
          <Text style={styles.emptyTitle}>No Zones Found</Text>
          <Text style={styles.emptySubtitle}>No safety zones match your search and filter criteria.</Text>
        </View>
      ) : (
        zones.map((zone) => {
          const isDanger = zone.risk_level === 'critical' || zone.risk_level === 'high' || zone.zone_type === 'restricted';
          const isWarning = zone.risk_level === 'medium' || zone.zone_type === 'warning';
          return (
            <View key={zone.id || zone.zone_id} style={styles.card}>
              <View style={styles.cardHeader}>
                <View
                  style={[
                    styles.iconCircle,
                    isDanger ? styles.iconDanger : isWarning ? styles.iconWarning : styles.iconSafe,
                  ]}
                >
                  <MapPinned size={18} color={isDanger ? '#ef4444' : isWarning ? '#f59e0b' : '#0d9488'} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle}>{zone.name}</Text>
                  <Text style={styles.cardSubtitle}>
                    {zone.center ? `Center: [${zone.center.coordinates[0].toFixed(4)}, ${zone.center.coordinates[1].toFixed(4)}]` : ''}
                  </Text>
                </View>
                <View style={[styles.statusBadge, zone.status === 'active' ? styles.badgeActive : styles.badgeInactive]}>
                  <Text style={[styles.statusBadgeText, zone.status === 'active' ? styles.textActive : styles.textInactive]}>
                    {zone.status.toUpperCase()}
                  </Text>
                </View>
              </View>

              {zone.description ? <Text style={styles.cardMeta}>{zone.description}</Text> : null}

              <View style={styles.tags}>
                <Tag label={`TYPE: ${zone.zone_type.toUpperCase()}`} />
                <Tag label={`RISK: ${zone.risk_level.toUpperCase()}`} />
                <Tag label={`GEOJSON: ${zone.boundary?.type || 'Polygon'}`} />
                {zone.properties?.dataset ? <Tag label={zone.properties.dataset} highlight /> : null}
              </View>

              {/* Action Bar */}
              <View style={styles.cardActions}>
                <TouchableOpacity onPress={() => openDetails(zone)} style={styles.actionBtn}>
                  <Eye size={14} color="#1a365d" />
                  <Text style={styles.actionBtnText}>Details & Audits</Text>
                </TouchableOpacity>

                <TouchableOpacity onPress={() => openEditModal(zone)} style={styles.actionBtn}>
                  <Edit3 size={14} color="#1a365d" />
                  <Text style={styles.actionBtnText}>Edit</Text>
                </TouchableOpacity>

                {zone.status === 'active' ? (
                  <TouchableOpacity onPress={() => handleStatusToggle(zone, 'inactive')} style={styles.actionBtnWarn}>
                    <Text style={styles.actionBtnWarnText}>Deactivate</Text>
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity onPress={() => handleStatusToggle(zone, 'active')} style={styles.actionBtnSuccess}>
                    <Text style={styles.actionBtnSuccessText}>Activate</Text>
                  </TouchableOpacity>
                )}

                <TouchableOpacity onPress={() => handleDelete(zone)} style={styles.deleteBtn}>
                  <Trash2 size={14} color="#ef4444" />
                </TouchableOpacity>
              </View>
            </View>
          );
        })
      )}

      {/* ── Details & Audit Modal ── */}
      <Modal visible={detailModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <View style={{ flex: 1 }}>
                <Text style={styles.modalTitle}>{selectedZone?.name}</Text>
                <Text style={styles.modalSubtitle}>Zone ID: {selectedZone?.id || selectedZone?.zone_id}</Text>
              </View>
              <TouchableOpacity onPress={() => setDetailModalVisible(false)} style={styles.closeBtn}>
                <X size={20} color="#1e293b" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              <Text style={styles.detailHeading}>Description</Text>
              <Text style={styles.detailText}>{selectedZone?.description || 'No description provided.'}</Text>

              <Text style={styles.detailHeading}>Geospatial Attributes</Text>
              <View style={styles.detailGrid}>
                <View style={styles.detailGridItem}>
                  <Text style={styles.gridLabel}>Zone Type</Text>
                  <Text style={styles.gridValue}>{selectedZone?.zone_type?.toUpperCase()}</Text>
                </View>
                <View style={styles.detailGridItem}>
                  <Text style={styles.gridLabel}>Risk Level</Text>
                  <Text style={styles.gridValue}>{selectedZone?.risk_level?.toUpperCase()}</Text>
                </View>
                <View style={styles.detailGridItem}>
                  <Text style={styles.gridLabel}>Status</Text>
                  <Text style={styles.gridValue}>{selectedZone?.status?.toUpperCase()}</Text>
                </View>
                <View style={styles.detailGridItem}>
                  <Text style={styles.gridLabel}>Active</Text>
                  <Text style={styles.gridValue}>{selectedZone?.is_active ? 'YES' : 'NO'}</Text>
                </View>
              </View>

              <Text style={styles.detailHeading}>Center Coordinate (GeoJSON Point)</Text>
              <View style={styles.codeBlock}>
                <Text style={styles.codeText}>
                  {selectedZone?.center
                    ? `Longitude: ${selectedZone.center.coordinates[0]}° E\nLatitude:  ${selectedZone.center.coordinates[1]}° N`
                    : 'No center point'}
                </Text>
              </View>

              <Text style={styles.detailHeading}>Boundary Geometry (RFC 7946 GeoJSON)</Text>
              <View style={styles.codeBlock}>
                <Text style={styles.codeText}>{JSON.stringify(selectedZone?.boundary, null, 2)}</Text>
              </View>

              <Text style={styles.detailHeading}>Metadata & Timestamps</Text>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Created At:</Text>
                <Text style={styles.metaValue}>
                  {selectedZone?.created_at ? new Date(selectedZone.created_at).toLocaleString() : 'N/A'}
                </Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Updated At:</Text>
                <Text style={styles.metaValue}>
                  {selectedZone?.updated_at ? new Date(selectedZone.updated_at).toLocaleString() : 'N/A'}
                </Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Created By:</Text>
                <Text style={styles.metaValue}>{selectedZone?.created_by || 'system'}</Text>
              </View>

              {/* Audit History */}
              <View style={styles.auditSection}>
                <View style={styles.auditHeader}>
                  <History size={16} color="#1a365d" />
                  <Text style={styles.auditTitle}>Immutable Audit Trail ({zoneAudits.length})</Text>
                </View>
                {loadingAudits ? (
                  <ActivityIndicator size="small" color="#1a365d" style={{ marginTop: 10 }} />
                ) : zoneAudits.length === 0 ? (
                  <Text style={styles.emptyAuditText}>No prior audit logs recorded for this zone.</Text>
                ) : (
                  zoneAudits.map((audit) => (
                    <View key={audit.id || audit.audit_id} style={styles.auditItem}>
                      <View style={styles.auditItemTop}>
                        <Text style={styles.auditAction}>{audit.action.toUpperCase()}</Text>
                        <Text style={styles.auditTime}>
                          {audit.changed_at ? new Date(audit.changed_at).toLocaleString() : ''}
                        </Text>
                      </View>
                      <Text style={styles.auditSummary}>
                        {audit.change_summary || `By user: ${audit.changed_by}`}
                      </Text>
                    </View>
                  ))
                )}
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* ── Create / Edit Zone Modal ── */}
      <Modal visible={createModalVisible || editModalVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalContainer}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{createModalVisible ? 'Create New Safety Zone' : 'Edit Safety Zone'}</Text>
              <TouchableOpacity
                onPress={() => {
                  setCreateModalVisible(false);
                  setEditModalVisible(false);
                }}
                style={styles.closeBtn}
              >
                <X size={20} color="#1e293b" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              <Text style={styles.formLabel}>Zone Name *</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Pillar Rocks Viewpoint Safe Sector"
                value={formName}
                onChangeText={setFormName}
              />

              <Text style={styles.formLabel}>Description</Text>
              <TextInput
                style={[styles.input, { height: 60 }]}
                placeholder="Safety instructions, landmarks, boundaries..."
                multiline
                value={formDescription}
                onChangeText={setFormDescription}
              />

              {/* Type & Risk Selectors */}
              <Text style={styles.formLabel}>Zone Type</Text>
              <View style={styles.selectorRow}>
                {(['safe', 'warning', 'restricted'] as ZoneType[]).map((t) => (
                  <TouchableOpacity
                    key={`form-type-${t}`}
                    onPress={() => setFormType(t)}
                    style={[styles.selectBtn, formType === t && styles.selectBtnActive]}
                  >
                    <Text style={[styles.selectBtnText, formType === t && styles.selectBtnTextActive]}>
                      {t.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.formLabel}>Risk Level</Text>
              <View style={styles.selectorRow}>
                {(['low', 'medium', 'high', 'critical'] as ZoneRiskLevel[]).map((r) => (
                  <TouchableOpacity
                    key={`form-risk-${r}`}
                    onPress={() => setFormRisk(r)}
                    style={[styles.selectBtn, formRisk === r && styles.selectBtnActive]}
                  >
                    <Text style={[styles.selectBtnText, formRisk === r && styles.selectBtnTextActive]}>
                      {r.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.formLabel}>Status</Text>
              <View style={styles.selectorRow}>
                {(['active', 'inactive', 'draft'] as ZoneStatus[]).map((s) => (
                  <TouchableOpacity
                    key={`form-status-${s}`}
                    onPress={() => setFormStatus(s)}
                    style={[styles.selectBtn, formStatus === s && styles.selectBtnActive]}
                  >
                    <Text style={[styles.selectBtnText, formStatus === s && styles.selectBtnTextActive]}>
                      {s.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Center Coords */}
              <Text style={styles.formLabel}>Center Point [Longitude, Latitude] *</Text>
              <View style={styles.coordRow}>
                <TextInput
                  style={[styles.input, { flex: 1 }]}
                  placeholder="Longitude (e.g. 77.4892)"
                  value={formCenterLon}
                  onChangeText={setFormCenterLon}
                  keyboardType="numeric"
                />
                <TextInput
                  style={[styles.input, { flex: 1 }]}
                  placeholder="Latitude (e.g. 10.2381)"
                  value={formCenterLat}
                  onChangeText={setFormCenterLat}
                  keyboardType="numeric"
                />
              </View>

              {/* Quick Template Presets */}
              <Text style={styles.formLabel}>Quick Templates (Development Geometry)</Text>
              <View style={styles.templateRow}>
                {TEMPLATE_PRESETS.map((preset) => (
                  <TouchableOpacity
                    key={preset.name}
                    onPress={() => applyTemplate(preset)}
                    style={styles.templateBtn}
                  >
                    <Sparkles size={12} color="#0284c7" />
                    <Text style={styles.templateBtnText}>{preset.name.split(' ')[0]}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* GeoJSON Boundary Editor */}
              <Text style={styles.formLabel}>Boundary Geometry (RFC 7946 GeoJSON Polygon) *</Text>
              <TextInput
                style={[styles.input, styles.jsonInput]}
                multiline
                placeholder='{"type": "Polygon", "coordinates": [[[lon, lat], ...]]}'
                value={formGeoJsonText}
                onChangeText={setFormGeoJsonText}
                autoCapitalize="none"
                autoCorrect={false}
              />

              <TouchableOpacity
                onPress={createModalVisible ? handleCreateSubmit : handleEditSubmit}
                disabled={isSubmitting}
                style={styles.submitBtn}
              >
                {isSubmitting ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.submitBtnText}>
                    {createModalVisible ? 'Save & Publish Zone' : 'Update Zone & Record Audit'}
                  </Text>
                )}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function Tag({ label, highlight }: { label: string; highlight?: boolean }) {
  return (
    <View style={[styles.tag, highlight && styles.tagHighlight]}>
      <Text style={[styles.tagText, highlight && styles.tagTextHighlight]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  headerTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 4, color: 'rgba(100,116,139,0.75)', lineHeight: 18, fontSize: 13 },
  createBtn: {
    backgroundColor: '#1a365d',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
  },
  createBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  searchCard: { backgroundColor: '#fff', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: '#e2e8f0', gap: 10 },
  searchInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  searchInput: { flex: 1, fontSize: 13, color: '#0f172a' },
  filterScroll: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  filterLabel: { fontSize: 11, fontWeight: '700', color: '#64748b' },
  filterChip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, backgroundColor: '#f1f5f9' },
  filterChipActive: { backgroundColor: '#1a365d' },
  filterChipText: { fontSize: 10, fontWeight: '700', color: '#475569' },
  filterChipTextActive: { color: '#fff' },
  loadingBox: { height: 200, alignItems: 'center', justifyContent: 'center' },
  loadingText: { marginTop: 10, color: '#64748b', fontSize: 13 },
  errorCard: { backgroundColor: '#fef2f2', borderRadius: 14, padding: 16, alignItems: 'center', gap: 8 },
  errorText: { color: '#b91c1c', textAlign: 'center', fontSize: 13 },
  retryBtn: { backgroundColor: '#1a365d', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, flexDirection: 'row', gap: 6, alignItems: 'center' },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 12 },
  emptyCard: { backgroundColor: '#fff', borderRadius: 16, padding: 30, alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#e2e8f0' },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: '#1e293b' },
  emptySubtitle: { fontSize: 12, color: '#64748b', textAlign: 'center' },
  card: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0', gap: 10 },
  cardHeader: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  iconCircle: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  iconSafe: { backgroundColor: '#ecfdf5' },
  iconWarning: { backgroundColor: '#fffbeb' },
  iconDanger: { backgroundColor: '#fef2f2' },
  cardTitle: { fontSize: 16, fontWeight: '800', color: '#0f172a' },
  cardSubtitle: { fontSize: 11, color: '#64748b', marginTop: 2 },
  cardMeta: { color: 'rgba(100,116,139,0.85)', lineHeight: 18, fontSize: 12 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  badgeActive: { backgroundColor: '#dcfce7' },
  badgeInactive: { backgroundColor: '#f1f5f9' },
  statusBadgeText: { fontSize: 10, fontWeight: '800' },
  textActive: { color: '#166534' },
  textInactive: { color: '#64748b' },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  tag: { backgroundColor: '#eff6ff', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  tagHighlight: { backgroundColor: '#fef3c7' },
  tagText: { fontSize: 10, fontWeight: '700', color: '#1a365d' },
  tagTextHighlight: { color: '#92400e' },
  cardActions: { flexDirection: 'row', gap: 8, alignItems: 'center', marginTop: 4, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#f1f5f9' },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: '#f1f5f9' },
  actionBtnText: { fontSize: 11, fontWeight: '700', color: '#1a365d' },
  actionBtnWarn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: '#fef2f2' },
  actionBtnWarnText: { fontSize: 11, fontWeight: '700', color: '#ef4444' },
  actionBtnSuccess: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: '#ecfdf5' },
  actionBtnSuccessText: { fontSize: 11, fontWeight: '700', color: '#10b981' },
  deleteBtn: { marginLeft: 'auto', padding: 6, borderRadius: 8, backgroundColor: '#fff1f2' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(15,23,42,0.6)', justifyContent: 'flex-end' },
  modalContainer: { backgroundColor: '#fff', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '88%', padding: 20 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, borderBottomWidth: 1, borderBottomColor: '#e2e8f0', paddingBottom: 12 },
  modalTitle: { fontSize: 20, fontWeight: '800', color: '#1a365d' },
  modalSubtitle: { fontSize: 11, color: '#64748b', marginTop: 2 },
  closeBtn: { padding: 4 },
  modalBody: { paddingBottom: 20 },
  detailHeading: { fontSize: 13, fontWeight: '800', color: '#1a365d', marginTop: 14, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
  detailText: { fontSize: 13, color: '#334155', lineHeight: 20 },
  detailGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 6 },
  detailGridItem: { width: '48%', backgroundColor: '#f8fafc', padding: 10, borderRadius: 10, borderWidth: 1, borderColor: '#e2e8f0' },
  gridLabel: { fontSize: 10, color: '#64748b', fontWeight: '700', textTransform: 'uppercase' },
  gridValue: { fontSize: 13, color: '#0f172a', fontWeight: '800', marginTop: 2 },
  codeBlock: { backgroundColor: '#0f172a', borderRadius: 10, padding: 12, marginVertical: 6 },
  codeText: { color: '#38bdf8', fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', fontSize: 11, lineHeight: 16 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: '#f1f5f9' },
  metaLabel: { fontSize: 12, color: '#64748b', fontWeight: '600' },
  metaValue: { fontSize: 12, color: '#0f172a', fontWeight: '700' },
  auditSection: { marginTop: 16, backgroundColor: '#f8fafc', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  auditHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  auditTitle: { fontSize: 13, fontWeight: '800', color: '#1a365d' },
  emptyAuditText: { fontSize: 12, color: '#94a3b8', fontStyle: 'italic' },
  auditItem: { backgroundColor: '#fff', borderRadius: 8, padding: 10, marginVertical: 4, borderWidth: 1, borderColor: '#e2e8f0' },
  auditItemTop: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  auditAction: { fontSize: 11, fontWeight: '800', color: '#0284c7' },
  auditTime: { fontSize: 10, color: '#94a3b8' },
  auditSummary: { fontSize: 11, color: '#475569' },
  formLabel: { fontSize: 12, fontWeight: '700', color: '#1a365d', marginTop: 12, marginBottom: 6 },
  input: { backgroundColor: '#f8fafc', borderRadius: 10, borderWidth: 1, borderColor: '#cbd5e1', padding: 10, fontSize: 13, color: '#0f172a' },
  jsonInput: { height: 120, fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', fontSize: 11 },
  selectorRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  selectBtn: { flex: 1, minWidth: '28%', paddingVertical: 8, borderRadius: 8, backgroundColor: '#f1f5f9', alignItems: 'center', borderWidth: 1, borderColor: '#e2e8f0' },
  selectBtnActive: { backgroundColor: '#1a365d', borderColor: '#1a365d' },
  selectBtnText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  selectBtnTextActive: { color: '#fff' },
  coordRow: { flexDirection: 'row', gap: 8 },
  templateRow: { flexDirection: 'row', gap: 8, marginVertical: 4 },
  templateBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: '#e0f2fe' },
  templateBtnText: { fontSize: 11, fontWeight: '700', color: '#0369a1' },
  submitBtn: { backgroundColor: '#1a365d', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 18, marginBottom: 20 },
  submitBtnText: { color: '#fff', fontSize: 14, fontWeight: '800' },
});
