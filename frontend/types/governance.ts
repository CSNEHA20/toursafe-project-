/**
 * TourSafe Authority Administration, Policy Configuration & System Governance Types
 */

export type OrganizationType =
  | 'POLICE'
  | 'TOURISM_BOARD'
  | 'EMS'
  | 'MUNICIPAL_SAFETY'
  | 'NATIONAL_PARK'
  | 'DISASTER_MANAGEMENT'
  | 'COAST_GUARD'
  | 'OTHER';

export type OrganizationStatus = 'ACTIVE' | 'SUSPENDED' | 'ARCHIVED';
export type JurisdictionStatus = 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';
export type AdminUserStatus = 'ACTIVE' | 'SUSPENDED' | 'DEACTIVATED';

export type ConfigurationType =
  | 'SAFETY'
  | 'RESPONSE_POLICY'
  | 'ESCALATION'
  | 'NOTIFICATION'
  | 'SYSTEM'
  | 'ML_THRESHOLDS'
  | 'GEOFENCE'
  | 'SECURITY';

export type ConfigurationLifecycleStatus =
  | 'DRAFT'
  | 'VALIDATING'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'ACTIVE'
  | 'RETIRED'
  | 'REJECTED';

export type AuditAction =
  | 'CREATE'
  | 'EDIT'
  | 'VALIDATE'
  | 'APPROVE'
  | 'REJECT'
  | 'ACTIVATE'
  | 'ROLLBACK'
  | 'RETIRE'
  | 'SUSPEND'
  | 'REACTIVATE'
  | 'MANUAL_OVERRIDE'
  | 'LOGIN_FAILURE'
  | 'PERMISSION_DENIED'
  | 'BULK_OPERATION'
  | 'IMPORT'
  | 'EXPORT';

export interface OrganizationModel {
  id: string;
  name: string;
  code: string;
  type: OrganizationType;
  jurisdiction_ids: string[];
  status: OrganizationStatus;
  contact_email?: string;
  contact_phone?: string;
  address?: string;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface JurisdictionModel {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  boundary: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: any;
  };
  center?: {
    type: 'Point';
    coordinates: [number, number];
  };
  status: JurisdictionStatus;
  cross_jurisdiction_allowed: boolean;
  auto_dispatch_allowed: boolean;
  overlap_priority: number;
  configuration: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface GovernanceConfigurationRecord {
  configuration_id: string;
  type: ConfigurationType;
  name: string;
  description: string;
  version: string;
  status: ConfigurationLifecycleStatus;
  jurisdiction_id?: string | null;
  parameters: Record<string, any>;
  change_reason: string;
  created_by: string;
  approved_by?: string | null;
  rejected_by?: string | null;
  rejection_reason?: string | null;
  activated_by?: string | null;
  retired_by?: string | null;
  previous_version_id?: string | null;
  rollback_target_version_id?: string | null;
  dependencies: string[];
  validation_results: {
    valid: boolean;
    errors: string[];
    warnings: string[];
    dependency_checks?: Array<{ dependency_id: string; exists: boolean; valid: boolean }>;
  };
  activated_at?: string | null;
  retired_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConfigurationDiffResult {
  source_version: string;
  target_version: string;
  source_config_id: string;
  target_config_id: string;
  added_keys: Record<string, any>;
  removed_keys: Record<string, any>;
  modified_keys: Record<string, { old: any; new: any }>;
  summary: string;
}

export interface ImmutableAuditRecord {
  audit_id: string;
  timestamp: string;
  actor_id: string;
  actor_name?: string | null;
  actor_role: string;
  action: AuditAction;
  resource_type: string;
  resource_id: string;
  jurisdiction_id?: string | null;
  before_state?: Record<string, any> | null;
  after_state?: Record<string, any> | null;
  change_reason?: string | null;
  ip_address?: string | null;
  integrity_hash?: string | null;
}

export interface SubsystemHealth {
  subsystem: string;
  status: 'HEALTHY' | 'DEGRADED' | 'DOWN' | 'UNKNOWN';
  latency_ms?: number | null;
  details?: Record<string, any> | null;
  last_check_at: string;
}

export interface SystemHealthOverview {
  system_status: 'HEALTHY' | 'DEGRADED' | 'DOWN';
  timestamp: string;
  subsystems: SubsystemHealth[];
  maintenance_mode: boolean;
  active_feature_flags: Record<string, boolean>;
}

export interface AdminOverviewMetrics {
  active_organizations_count: number;
  active_jurisdictions_count: number;
  active_responders_count: number;
  active_zones_count: number;
  active_policies_count: number;
  pending_approvals_count: number;
  recent_audit_events_count_24h: number;
  system_health_status: string;
  active_safety_config_version: string;
  recent_changes: Array<{
    audit_id: string;
    action: string;
    resource_type: string;
    resource_id: string;
    actor_role: string;
    change_reason?: string;
    timestamp: string;
  }>;
}

export interface PolicySimulationResult {
  policy_id: string;
  policy_name: string;
  version: string;
  simulation_timestamp: string;
  simulated_stages: Array<{
    stage: number;
    name: string;
    target_severity: string;
    delay_seconds: number;
    actions_count: number;
  }>;
  simulated_dispatches: Array<{
    stage: number;
    action_key: string;
    required_capabilities: string[];
    estimated_units_available: number;
  }>;
  simulated_notifications: Array<{
    stage: number;
    action_key: string;
    channels: string[];
  }>;
  expected_escalation_path: string[];
  potential_risks_identified: string[];
}

export interface SafetyRuleSimulationResult {
  baseline_version: string;
  candidate_version?: string;
  composite_risk_score_baseline: number;
  composite_risk_score_candidate: number;
  baseline_state: string;
  candidate_state: string;
  domain_breakdown_baseline: Record<string, number>;
  domain_breakdown_candidate: Record<string, number>;
  sensitivity_delta: number;
  explainability: string[];
}
