export type DataCategory =
  | 'IDENTITY'
  | 'KYC'
  | 'CONTACT'
  | 'LOCATION'
  | 'TELEMETRY'
  | 'INCIDENT'
  | 'EMERGENCY'
  | 'RESPONDER'
  | 'AUTHORITY'
  | 'COMMUNICATION'
  | 'ANALYTICS'
  | 'AI'
  | 'ML'
  | 'AUDIT'
  | 'SYSTEM';

export type PolicyStatus =
  | 'DRAFT'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'ACTIVE'
  | 'RETIRED'
  | 'REJECTED';

export type FrameworkType =
  | 'ISO_27001'
  | 'SOC_2'
  | 'GDPR_READINESS'
  | 'DPDP_READINESS'
  | 'NIST_CSF';

export type ControlStatus =
  | 'IMPLEMENTED'
  | 'PARTIAL'
  | 'NOT_IMPLEMENTED'
  | 'REQUIRES_REVIEW'
  | 'NOT_APPLICABLE';

export type ControlDomain =
  | 'DATA_PROTECTION'
  | 'ACCESS_CONTROL'
  | 'INCIDENT_RESPONSE'
  | 'AI_ML_GOVERNANCE'
  | 'AUDIT_LOGGING'
  | 'INFRASTRUCTURE_SECURITY'
  | 'THIRD_PARTY_RISK'
  | 'DISASTER_RECOVERY';

export interface RetentionPolicy {
  id: string;
  data_type: DataCategory;
  jurisdiction_id?: string | null;
  retention_period_days: number;
  archive_behavior: string;
  deletion_behavior: string;
  legal_hold_behavior: string;
  version: number;
  effective_from: string;
  effective_until?: string | null;
  status: PolicyStatus;
  created_by: string;
  approved_by?: string | null;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface LegalHold {
  id: string;
  title: string;
  reason: string;
  scope_type: 'USER' | 'INCIDENT' | 'JURISDICTION' | 'DATE_RANGE' | 'DATA_TYPE';
  scope_id: string;
  date_range_start?: string | null;
  date_range_end?: string | null;
  data_categories: string[];
  status: 'ACTIVE' | 'RELEASED' | 'EXPIRED';
  placed_by: string;
  placed_at: string;
  review_date?: string | null;
  released_by?: string | null;
  released_at?: string | null;
  release_reason?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface VendorIntegration {
  id: string;
  vendor_name: string;
  service_name: string;
  data_shared: string[];
  purpose: string;
  vendor_jurisdiction: string;
  data_residency_region: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'DECOMMISSIONED';
  security_review_status: 'NOT_REVIEWED' | 'IN_REVIEW' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
  contract_status: 'DPA_SIGNED' | 'SLA_ACTIVE' | 'PENDING_RENEWAL' | 'NO_CONTRACT';
  cross_border_transfer: boolean;
  risk_level: string;
  dpa_reference?: string | null;
  sla_reference?: string | null;
  last_reviewed_at?: string | null;
  next_review_date?: string | null;
}

export interface AccessReview {
  id: string;
  title: string;
  scope: 'ADMIN_USERS' | 'AUTHORITY_OFFICERS' | 'RESPONDERS' | 'SERVICE_ACCOUNTS';
  reviewer_id: string;
  period_start: string;
  period_end: string;
  status: 'SCHEDULED' | 'IN_PROGRESS' | 'COMPLETED' | 'OVERDUE';
  accounts_reviewed: Array<{
    user_id: string;
    email: string;
    role: string;
    is_active: boolean;
    last_login?: string | null;
    decision: string;
    notes?: string;
  }>;
  findings?: string | null;
  completed_at?: string | null;
  completed_by?: string | null;
}

export interface BreakGlassSession {
  id: string;
  user_id: string;
  user_email: string;
  requested_role: string;
  justification: string;
  target_scope: string;
  requested_at: string;
  expires_at: string;
  status: 'ACTIVE' | 'EXPIRED' | 'REVOKED';
  approved_by?: string | null;
}

export interface ComplianceControl {
  control_id: string;
  framework: FrameworkType;
  domain: ControlDomain;
  title: string;
  description: string;
  implementation_status: ControlStatus;
  evidence_refs: string[];
  owner: string;
  review_frequency_days: number;
  last_review?: string | null;
  next_review?: string | null;
}

export interface FrameworkReadinessReport {
  framework: FrameworkType;
  total_controls: number;
  implemented_count: number;
  partial_count: number;
  not_implemented_count: number;
  requires_review_count: number;
  readiness_percentage: number;
  gaps_count: number;
  generated_at: string;
  disclaimer: string;
  controls_summary: ComplianceControl[];
  identified_gaps?: Array<{
    id: string;
    framework: string;
    requirement: string;
    current_state: string;
    target_state: string;
    severity: string;
    status: string;
  }>;
}
