// ─── Tourist Types ───────────────────────────────────────────────────────────

export interface Tourist {
  id: string;
  user_id: string;
  name?: string;
  full_name: string;
  nationality: string;
  passport_number: string;
  phone: string;
  email: string;
  date_of_birth: string;
  gender: "male" | "female" | "other";
  profile_photo_url?: string;
  did_address?: string;
  did_status: "active" | "pending" | "revoked";
  current_zone_id?: string;
  current_zone?: string;
  current_location?: { latitude: number; longitude: number };
  status?: "safe" | "alert" | "sos" | "warning" | "inactive";
  incident_count?: number;
  last_seen_at?: string;
  last_seen?: string;
  is_active: boolean;
  created_at: string;
  // Extended mock fields
  battery_pct?: number;
  anomaly_score?: number;
  blood_type?: string;
  medical_conditions?: string[];
  allergies?: string[];
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relation?: string;
  age?: number;
}

export interface TouristLocation {
  id: string;
  tourist_id: string;
  latitude: number;
  longitude: number;
  accuracy?: number;
  altitude?: number;
  speed?: number;
  heading?: number;
  recorded_at: string;
  zone_id?: string;
}

export interface MedicalInfo {
  tourist_id: string;
  blood_group: string;
  allergies: string[];
  conditions: string[];
  medications: string[];
  emergency_contacts: EmergencyContact[];
}

export interface EmergencyContact {
  name: string;
  relationship: string;
  phone: string;
  email?: string;
  is_primary: boolean;
}

// ─── Alert Types ──────────────────────────────────────────────────────────────

export type AlertSeverity = "critical" | "high" | "medium" | "low";
export type AlertType =
  | "sos"
  | "inactivity"
  | "zone_exit"
  | "anomaly"
  | "weather"
  | "infrastructure"
  | "crowd"
  | "system";
export type AlertStatus = "active" | "acknowledged" | "resolved" | "escalated";

export interface Alert {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  description: string;
  tourist_id?: string;
  tourist?: Tourist;
  zone_id?: string;
  zone?: GeoZone;
  latitude?: number;
  longitude?: number;
  created_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
  assigned_to?: string;
  incident_id?: string;
}

// ─── Incident / SOS Types ─────────────────────────────────────────────────────

export type IncidentStatus =
  | "reported"
  | "dispatched"
  | "in_progress"
  | "resolved"
  | "closed";

export interface Incident {
  id: string;
  tourist_id: string;
  tourist?: Tourist;
  type: string;
  description: string;
  status: IncidentStatus;
  latitude: number;
  longitude: number;
  responder_id?: string;
  zone_id?: string;
  efir_id?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
}

export interface SOSEvent {
  id?: string;
  incident_id: string;
  tourist_id: string;
  tourist_name: string;
  latitude: number;
  longitude: number;
  zone_name: string;
  did_address?: string;
  status: IncidentStatus;
  triggered_at: string;
  acknowledged_by?: string;
}

// ─── Geo-Zone & Geospatial Types ─────────────────────────────────────────────

export type ZoneType = "safe" | "warning" | "restricted" | "danger";
export type ZoneRiskLevel = "low" | "medium" | "high" | "critical";
export type ZoneStatus = "active" | "inactive" | "draft" | "monitoring";

export interface GeoJSONPoint {
  type: "Point";
  coordinates: [number, number]; // [longitude, latitude]
}

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: [number, number][][]; // [[[lon, lat], ...]]
}

export interface GeoJSONMultiPolygon {
  type: "MultiPolygon";
  coordinates: [number, number][][][];
}

export type ZoneGeometry = GeoJSONPolygon | GeoJSONMultiPolygon;

export interface Zone {
  id: string;
  zone_id: string;
  name: string;
  description: string;
  zone_type: ZoneType;
  risk_level: ZoneRiskLevel;
  status: ZoneStatus;
  boundary: ZoneGeometry;
  center: GeoJSONPoint;
  properties: Record<string, any>;
  is_active: boolean;
  created_by?: string;
  updated_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ZoneMapItem {
  zone_id: string;
  name: string;
  description: string;
  type: ZoneType;
  risk_level: ZoneRiskLevel;
  status: ZoneStatus;
  geometry: ZoneGeometry;
  center: GeoJSONPoint;
  properties: Record<string, any>;
}

export interface ZoneAudit {
  id: string;
  audit_id: string;
  zone_id: string;
  action: "created" | "updated" | "boundary_updated" | "status_changed" | "deleted";
  changed_by: string;
  changed_at: string;
  previous_values?: Record<string, any>;
  new_values?: Record<string, any>;
  change_summary?: string;
}

export interface GeoZone {
  id: string;
  zone_id?: string;
  name: string;
  description?: string;
  type: ZoneType;
  zone_type?: ZoneType;
  risk_level?: ZoneRiskLevel;
  status: ZoneStatus;
  polygon?: GeoJSON.Polygon | ZoneGeometry;
  boundary?: ZoneGeometry;
  center?: GeoJSONPoint;
  center_lat?: number;
  center_lng?: number;
  radius?: number;
  radius_meters?: number;
  tourist_count?: number;
  alert_count?: number;
  created_at?: string;
  updated_at?: string;
}

// ─── Blockchain / DID Types ───────────────────────────────────────────────────

export interface BlockchainDID {
  id: string;
  tourist_id: string;
  did_address: string;
  ipfs_hash?: string;
  qr_code_data: string;
  verification_status: "verified" | "pending" | "failed";
  network: "polygon" | "polygon_amoy";
  created_at: string;
  last_verified_at?: string;
}

// ─── E-FIR Types ──────────────────────────────────────────────────────────────

export type EFIRStatus = "draft" | "submitted" | "accepted" | "archived";

export interface EFIR {
  id: string;
  incident_id: string;
  tourist_id: string;
  tourist?: Tourist;
  tourist_name?: string;
  fir_number?: string;
  /** Alias for fir_number returned by some API responses */
  efir_number?: string;
  status: EFIRStatus;
  incident_type: string;
  incident_date: string;
  incident_location: string;
  location?: string;
  location_description?: string;
  description: string;
  evidence_urls: string[];
  attachments?: string[];
  nationality?: string;
  passport_number?: string;
  pdf_url?: string;
  blockchain_hash?: string;
  submitted_at?: string;
  created_at: string;
  updated_at: string;
}

// ─── Analytics Types ──────────────────────────────────────────────────────────

export interface DashboardKPIs {
  active_tourists: number;
  active_tourists_delta: number;
  active_alerts: number;
  active_alerts_delta: number;
  sos_today: number;
  sos_today_delta: number;
  avg_response_time_minutes: number;
  avg_response_time_delta: number;
  zones_at_risk: number;
  resolved_today: number;
}

export interface ResponseTimeDataPoint {
  date: string;
  avg_minutes: number;
  p95_minutes: number;
}

export interface IncidentTrendPoint {
  date: string;
  sos: number;
  inactivity: number;
  zone_exit: number;
  other: number;
}

export interface ZoneStats {
  zone_id: string;
  zone_name: string;
  tourist_count: number;
  alert_count: number;
  risk_score: number;
}

// ─── Auth Types ───────────────────────────────────────────────────────────────

export type UserRole = "tourist" | "authority" | "admin" | "responder";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  full_name: string;
  name?: string;
  tourist_id?: string;
  authority_id?: string;
}

// ─── WebSocket Message Types ──────────────────────────────────────────────────

export type WSMessageType =
  | "sos_event"
  | "location_update"
  | "alert_created"
  | "alert_updated"
  | "incident_updated"
  | "zone_updated"
  | "tourist_status";

export interface WSMessage<T = unknown> {
  type: WSMessageType;
  payload: T;
  timestamp: string;
}

// ─── Map Types ────────────────────────────────────────────────────────────────

export interface MapViewState {
  center: [number, number];
  zoom: number;
}

export interface HeatmapPoint {
  lat: number;
  lng: number;
  intensity: number;
}

export interface TouristMarker {
  tourist_id: string;
  name: string;
  latitude: number;
  longitude: number;
  status: "safe" | "alert" | "sos" | "inactive";
  last_seen: string;
}

// ─── Itinerary Types ──────────────────────────────────────────────────────────

export type StopType = "hotel" | "tourist_spot" | "transport" | "restaurant" | "other";

export interface ItineraryStop {
  id: string;
  itinerary_id: string;
  spot_name: string;
  address?: string;
  stop_type: StopType;
  planned_arrival?: string;
  planned_departure?: string;
  expected_duration_hours: number;
  latitude?: number;
  longitude?: number;
  notes?: string;
  created_at: string;
}

export interface Itinerary {
  id: string;
  tourist_id: string;
  title: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  notes?: string;
  stops: ItineraryStop[];
  created_at: string;
}

export interface ItineraryCreate {
  title: string;
  start_date: string;
  end_date: string;
  notes?: string;
  stops?: Omit<ItineraryStop, "id" | "itinerary_id" | "created_at">[];
}

export interface ItineraryStopCreate {
  spot_name: string;
  address?: string;
  stop_type: StopType;
  planned_arrival?: string;
  planned_departure?: string;
  expected_duration_hours?: number;
  latitude?: number;
  longitude?: number;
  notes?: string;
}

// ─── Authority Profile Types ──────────────────────────────────────────────────

export type AuthorityType = "police" | "agency" | "hospital" | "other";

export interface AuthorityProfile {
  id: string;
  user_id: string;
  authority_type: AuthorityType;
  org_name: string;
  badge_number?: string;
  contact_phone?: string;
  contact_email?: string;
  agency_tour_types: string[];
  jurisdiction_spots: string[];
  verified: boolean;
  created_at: string;
}

// ─── Safety Check Types ───────────────────────────────────────────────────────

export interface SafetyCheck {
  id: string;
  tourist_id: string;
  reason?: string;
  sent_at: string;
  response?: "safe" | "unsafe" | "no_response" | null;
  responded_at?: string;
  escalated: boolean;
  created_at: string;
}

// ─── Emergency Command & SOS Types (Prompt 12) ────────────────────────────────

export type IncidentStatusType =
  | "OPEN"
  | "ACKNOWLEDGED"
  | "ASSESSING"
  | "ASSIGNED"
  | "RESPONDING"
  | "MONITORING"
  | "ESCALATED"
  | "RESOLVED"
  | "CANCELLED"
  | "CLOSED";

export type IncidentSeverityType = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type IncidentSourceType = "MANUAL_SOS" | "SAFETY_ENGINE" | "AUTHORITY_CREATED";

export interface TimelineEvent {
  event_id: string;
  incident_id: string;
  timestamp: string;
  actor_type: string;
  actor_id: string;
  action: string;
  previous_state?: string;
  new_state?: string;
  metadata?: Record<string, any>;
  reason?: string;
}

export interface IncidentNote {
  note_id: string;
  incident_id: string;
  author_id: string;
  author_role: string;
  author_name?: string;
  timestamp: string;
  content: string;
}

export interface Responder {
  responder_id: string;
  name: string;
  type: ResponderType;
  unit_id?: string;
  status: ResponderStatus;
  capabilities: string[];
  current_location?: {
    latitude: number;
    longitude: number;
    accuracy?: number;
    heading?: number;
    speed?: number;
    timestamp?: string;
    quality?: string;
  };
  contact_channel?: string;
  contact_phone?: string;
  active: boolean;
  assigned_incident_id?: string;
  active_assignment_id?: string;
  tracking_session_id?: string;
  tracking_active?: boolean;
  last_location_timestamp?: string;
}

export interface IncidentRecord {
  incident_id: string;
  tourist_id: string;
  session_id?: string;
  started_at: string;
  resolved_at?: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  status: IncidentStatusType;
  severity: IncidentSeverityType;
  source: IncidentSourceType;
  decision_id: string;
  rule_version: string;
  reasons: string[];
  signal_summary: Record<string, any>;
  notes?: string;
  notes_list: IncidentNote[];
  timeline: TimelineEvent[];
  location_data?: {
    latitude: number;
    longitude: number;
    accuracy?: number;
    location_status?: string;
    zone_name?: string;
    zone_risk?: string;
  };
  assigned_to?: string;
  assigned_unit?: string;
  responder_type?: string;
  escalation_stage: number;
  escalation_history: Array<Record<string, any>>;
  notifications_sent: Array<Record<string, any>>;
  resolution_category?: string;
  resolution_reason?: string;
  cancellation_reason?: string;
  closed_at?: string;
  closed_by?: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface SOSPayload {
  client_request_id: string;
  session_id?: string;
  latitude?: number;
  longitude?: number;
  accuracy?: number;
  reason?: string;
  category?: string;
  timestamp?: string;
}

export interface SOSResponse {
  sos_id: string;
  incident_id: string;
  status: string;
  created_at: string;
  tourist_id: string;
  location_status: string;
  location?: any;
  acknowledged: boolean;
  message: string;
}

export interface IncidentMetrics {
  total_incidents: number;
  open_incidents: number;
  acknowledged_incidents: number;
  responding_incidents: number;
  escalated_incidents: number;
  resolved_incidents: number;
  closed_incidents: number;
  cancelled_incidents: number;
  avg_time_to_acknowledge_seconds?: number;
  avg_time_to_assign_seconds?: number;
  avg_time_to_resolve_seconds?: number;
  escalation_count: number;
  false_alarm_rate: number;
  notification_stats: Record<string, number>;
}

// ─── Responder Operations Platform Types (Prompt 13) ──────────────────────────

export type ResponderType =
  | "POLICE"
  | "MEDICAL"
  | "FIRE"
  | "SEARCH_AND_RESCUE"
  | "SECURITY"
  | "FIELD_RESPONDER"
  | "AUTHORITY_OPERATOR";

export type ResponderStatus =
  | "OFFLINE"
  | "AVAILABLE"
  | "ASSIGNED"
  | "RESPONDING"
  | "ON_SCENE"
  | "UNAVAILABLE";

export type UnitStatus = "ACTIVE" | "STANDBY" | "DISPATCHED" | "OUT_OF_SERVICE";

export type AssignmentStatus =
  | "PENDING"
  | "ACCEPTED"
  | "REJECTED"
  | "ACTIVE"
  | "ON_SCENE"
  | "COMPLETED"
  | "CANCELLED";

export type RejectionReason =
  | "UNREACHABLE_OR_OFFLINE"
  | "INSUFFICIENT_CAPABILITY"
  | "EQUIPMENT_MALFUNCTION"
  | "GEOGRAPHIC_BARRIER"
  | "SAFETY_HAZARD"
  | "CONCURRENT_ACTIVE_RESPONSE"
  | "OTHER";

export interface ResponderLocationLive {
  responder_id: string;
  latitude: number;
  longitude: number;
  altitude?: number;
  accuracy: number;
  heading?: number;
  speed?: number;
  timestamp: string;
  tracking_session_id?: string;
  is_low_accuracy: boolean;
  quality: "HIGH_ACCURACY" | "LOW_ACCURACY";
}

export interface ResponderUnitRecord {
  unit_id: string;
  callsign: string;
  unit_type: ResponderType;
  department?: string;
  jurisdiction_zone_ids: string[];
  members: string[];
  vehicle_type?: string;
  equipment_capabilities: string[];
  status: UnitStatus;
  lead_responder_id?: string;
  created_at: string;
  updated_at: string;
}

export interface AssignmentRecord {
  assignment_id: string;
  incident_id: string;
  responder_id: string;
  unit_id?: string;
  assigned_by: string;
  assigned_at: string;
  accepted_at?: string;
  rejected_at?: string;
  rejection_reason?: string;
  started_at?: string;
  arrived_at?: string;
  arrival_location?: {
    latitude: number;
    longitude: number;
    accuracy?: number;
    proximity_verified: boolean;
    distance_to_incident_meters?: number;
  };
  arrival_accuracy?: number;
  completed_at?: string;
  completion_reason?: string;
  completion_notes?: string;
  cancelled_at?: string;
  cancellation_reason?: string;
  status: AssignmentStatus;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface OperationalMessageRecord {
  message_id: string;
  incident_id: string;
  assignment_id?: string;
  sender_id: string;
  sender_type: "AUTHORITY" | "RESPONDER" | "SYSTEM";
  sender_name?: string;
  timestamp: string;
  content: string;
  delivery_status: string;
  read_at?: string;
}

export interface ResponderRecommendationItem {
  responder: Responder;
  score: number;
  distance_meters: number;
  distance_text: string;
  staleness_status: "LIVE" | "RECENT" | "STALE" | "OFFLINE";
  reasons: string[];
}

export interface ResponderSelfProfile {
  responder: Responder;
  active_unit?: ResponderUnitRecord;
  active_assignment?: AssignmentRecord;
  active_incident?: IncidentRecord;
  live_location?: ResponderLocationLive;
  tracking_session?: Record<string, any>;
}

export * from "./geofence";


