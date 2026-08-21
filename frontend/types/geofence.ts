/**
 * TourSafe - Geofencing Frontend Types
 */

export type ZoneMembershipStateType =
  | "outside"
  | "enter_candidate"
  | "inside"
  | "exit_candidate"
  | "uncertain"
  | "stale";

export type MembershipConfidenceType = "high" | "medium" | "low" | "uncertain";

export interface ActiveZoneMembershipItem {
  zone_id: string;
  name: string;
  zone_type: "safe" | "warning" | "restricted";
  risk_level: "low" | "medium" | "high" | "critical";
  state: ZoneMembershipStateType;
  confidence_level: MembershipConfidenceType;
  confidence_score: number;
  entered_at: string;
  last_seen_inside: string;
  dwell_duration_seconds: number;
  dwell_threshold_notified: boolean;
  last_location_timestamp: string;
  distance_to_boundary_meters: number;
  accuracy_meters: number;
  geometry_version?: string;
  properties?: Record<string, any>;
}

export interface TouristGeofenceSnapshotResponse {
  tourist_id: string;
  active_zones: ActiveZoneMembershipItem[];
  highest_risk_level: "low" | "medium" | "high" | "critical";
  primary_zone_type: "safe" | "warning" | "restricted";
  is_stale: boolean;
  last_gps_timestamp?: string;
  total_active_zones: number;
  updated_at: string;
}

export interface ZoneTransitionHistoryRecord {
  id: string;
  transition_id: string;
  tourist_id: string;
  user_id: string;
  zone_id: string;
  zone_name: string;
  zone_type: string;
  risk_level: string;
  session_id?: string;
  event_type: string;
  from_state: string;
  to_state: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  location: { type: "Point"; coordinates: [number, number] };
  accuracy: number;
  confidence_score: number;
  confidence_level: string;
  boundary_distance_meters: number;
  dwell_duration_seconds?: number;
  created_at: string;
}

export interface GeofenceDiagnosticsData {
  tourist_id: string;
  current_coordinates: { latitude: number; longitude: number };
  gps_accuracy_meters: number;
  gps_timestamp: string;
  gps_freshness_seconds?: number;
  candidate_zones_count: number;
  candidate_zones: Array<{
    zone_id: string;
    name: string;
    risk_level: string;
    zone_type: string;
  }>;
  active_memberships: ActiveZoneMembershipItem[];
  highest_risk_level: string;
  last_transition_event?: Record<string, any>;
  processing_latency_ms: number;
  engine_status: string;
}
