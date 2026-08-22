/**
 * TourSafe - Safety Orchestration & Advanced Risk Fusion Types (Prompt 23)
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

export type SignalType =
  | "ANOMALY_DETECTED"
  | "ANOMALY_CLEARED"
  | "ZONE_ENTERED"
  | "ZONE_EXITED"
  | "ZONE_DWELL"
  | "GPS_LOCATION_UPDATE"
  | "GPS_STALE"
  | "GPS_UNCERTAIN"
  | "TELEMETRY_GOOD"
  | "TELEMETRY_DEGRADED"
  | "TELEMETRY_OFFLINE"
  | "TRACKING_ACTIVE"
  | "TRACKING_STOPPED"
  | "ITINERARY_DEVIATION"
  | "TEMPORAL_CONTEXT"
  | "TRIP_CONTEXT"
  | "HISTORICAL_CONTEXT";

export type SignalQuality = "EXCELLENT" | "GOOD" | "DEGRADED" | "POOR" | "STALE" | "UNKNOWN";

export type ConfidenceClass = "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";

export type IncidentStatus = "OPEN" | "ACKNOWLEDGED" | "ASSESSING" | "ASSIGNED" | "RESPONDING" | "MONITORING" | "ESCALATED" | "RESOLVED" | "CANCELLED" | "CLOSED";

export type IncidentSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface NormalizedSafetyFeatures {
  motion_anomaly_norm: number;
  geospatial_hazard_norm: number;
  itinerary_deviation_norm: number;
  telemetry_degradation_norm: number;
  temporal_risk_norm: number;
  trip_vulnerability_norm: number;
  historical_risk_norm: number;
  kinematic_shock_norm: number;
}

export interface RiskScoreBreakdown {
  composite_risk_score: number;
  motion_risk_score: number;
  spatial_risk_score: number;
  itinerary_risk_score: number;
  environmental_risk_score: number;
  vulnerability_risk_score: number;
  risk_level_label: string; // "SAFE" | "WATCH" | "ELEVATED" | "CRITICAL"
  risk_trend: string; // "INCREASING" | "STABLE" | "DECREASING"
}

export interface SignalCorrelationResult {
  correlated_pattern: string;
  dampening_factor: number;
  false_positive_probability: number;
  is_false_alarm_suppressed: boolean;
  matched_signatures: string[];
  correlation_notes: string[];
}

export interface ConfidenceAssessment {
  confidence_score: number;
  confidence_class: ConfidenceClass;
  sensor_uncertainty: number;
  sparsity_penalty: number;
  cross_signal_conflict: number;
  freshness_penalty: number;
}

export interface FeatureAttribution {
  feature_name: string;
  contribution_score: number;
  percentage: number;
  direction: string; // "INCREASES_RISK" | "MITIGATES_RISK" | "NEUTRAL"
  description: string;
}

export interface ExplainabilityReport {
  primary_risk_drivers: string[];
  mitigating_factors: string[];
  feature_attributions: FeatureAttribution[];
  natural_language_summary: string;
  tourist_guidance: string;
}

export interface DecisionSupportRecommendation {
  recommended_action: string;
  action_priority: string; // "LOW" | "MEDIUM" | "HIGH" | "URGENT"
  verification_checklist: string[];
  sensor_health_advisory?: string | null;
  suggested_responder_type?: string | null;
}

export interface MultiSignalRiskAssessment {
  assessment_id: string;
  tourist_id: string;
  session_id?: string | null;
  timestamp: string;
  normalized_features: NormalizedSafetyFeatures;
  risk_breakdown: RiskScoreBreakdown;
  correlation: SignalCorrelationResult;
  confidence: ConfidenceAssessment;
  explainability: ExplainabilityReport;
  decision_support: DecisionSupportRecommendation;
  raw_signals_count: number;
}

export interface TriggeredRule {
  rule_id: string;
  rule_name: string;
  category: string;
  contributed_state: SafetyState;
  reason: string;
  confidence_weight: number;
  matched_signals: string[];
}

export interface SafetyDecisionRecord {
  decision_id: string;
  tourist_id: string;
  session_id?: string | null;
  timestamp: string;
  state: SafetyState;
  previous_state: SafetyState;
  rule_version: string;
  triggered_rules: TriggeredRule[];
  reasons: string[];
  signals: Record<string, any>;
  quality: SignalQuality;
  confidence_class: ConfidenceClass;
  risk_score?: number | null;
  risk_assessment?: MultiSignalRiskAssessment | null;
}

export interface IncidentRecord {
  incident_id: string;
  tourist_id: string;
  session_id?: string | null;
  started_at: string;
  updated_at?: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  decision_id: string;
  rule_version: string;
  reasons: string[];
  signal_summary: Record<string, any>;
  risk_score?: number | null;
  risk_assessment?: MultiSignalRiskAssessment | null;
  notes?: string | null;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
}

export interface ActiveSafetyState {
  tourist_id: string;
  current_state: SafetyState;
  previous_state: SafetyState;
  decision_id: string;
  started_at: string;
  last_update: string;
  last_evaluated_at?: string;
  last_decision_id?: string;
  rule_version: string;
  confidence_class: ConfidenceClass;
  active_reasons: string[];
  reasons?: string[];
  active_signals_summary: Record<string, any>;
  active_incident_id?: string | null;
  recovery_started_at?: string | null;
  quality?: SignalQuality;
  risk_score?: number | null;
  risk_assessment?: MultiSignalRiskAssessment | null;
}

export interface TouristSafetyStatusResponse {
  safety_status: string;
  monitoring_active: boolean;
  gps_connected: boolean;
  last_checked_at: string;
  zone_name?: string | null;
  zone_risk?: string | null;
  guidance_message: string;
  safety_index?: number | null;
  risk_level?: string | null;
  proactive_check_required?: boolean;
  proactive_check_message?: string | null;
}

export interface SafetyCheckResponseRequest {
  response_type: string; // "SAFE_CONFIRMED" | "ASSISTANCE_REQUESTED" | "FALSE_ALARM"
  user_note?: string | null;
  battery_level?: number | null;
  timestamp?: string | null;
}

export interface SafetyCheckResponseResult {
  success: boolean;
  message: string;
  updated_state: SafetyState;
  risk_score: number;
  guidance: string;
}
