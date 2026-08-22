/**
 * TourSafe - Safety Orchestration & Incident Types
 */

export type SafetyState =
  | "NORMAL"
  | "WATCH"
  | "ELEVATED"
  | "INCIDENT_CANDIDATE"
  | "INCIDENT"
  | "RECOVERING"
  | "UNKNOWN"
  | "ERROR";

export type SignalType = "GPS" | "ANOMALY" | "GEOFENCE" | "TELEMETRY" | "TRACKING" | "CONTEXT";

export type SignalQuality = "EXCELLENT" | "GOOD" | "DEGRADED" | "POOR" | "STALE" | "MISSING";

export type ConfidenceClass = "HIGH" | "MEDIUM" | "LOW" | "NONE";

export type IncidentStatus = "OPEN" | "ACKNOWLEDGED" | "MONITORING" | "RESOLVED" | "CANCELLED";

export type IncidentSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface TriggeredRule {
  rule_id: string;
  category: string;
  weight: number;
  reason: string;
  signals_used: string[];
}

export interface SafetyDecisionRecord {
  decision_id: string;
  tourist_id: string;
  session_id?: string | null;
  state: SafetyState;
  previous_state: SafetyState;
  confidence: number;
  confidence_class: ConfidenceClass;
  quality: SignalQuality;
  reasons: string[];
  signals: Record<string, any>;
  triggered_rules: TriggeredRule[];
  rule_version: string;
  model_version?: string | null;
  timestamp: string;
}

export interface ActiveSafetyState {
  tourist_id: string;
  current_state: SafetyState;
  previous_state: SafetyState;
  last_evaluated_at: string;
  active_incident_id?: string | null;
  last_decision_id: string;
  rule_version: string;
  reasons: string[];
  quality: SignalQuality;
  confidence_class: ConfidenceClass;
  recovery_started_at?: string | null;
}

export interface IncidentRecord {
  incident_id: string;
  tourist_id: string;
  session_id?: string | null;
  started_at: string;
  updated_at: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  decision_id: string;
  rule_version: string;
  reasons: string[];
  signal_summary: Record<string, any>;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
  notes?: string | null;
}

export interface TouristSafetyStatusResponse {
  safety_status: string;
  monitoring_active: boolean;
  gps_connected: boolean;
  last_checked_at: string;
  guidance_message: string;
  zone_guidance?: string | null;
}
