import { DataCategory } from './compliance';

export type ConsentPurpose =
  | 'LOCATION_TRACKING'
  | 'TELEMETRY_PROCESSING'
  | 'KYC_VERIFICATION'
  | 'EMERGENCY_COMMUNICATION'
  | 'OPTIONAL_ANALYTICS'
  | 'OPTIONAL_PERSONALIZATION';

export interface ConsentRecord {
  id: string;
  subject_id: string;
  purpose: ConsentPurpose;
  version: string;
  status: 'GRANTED' | 'WITHDRAWN' | 'SUPERSEDED';
  granted_at: string;
  withdrawn_at?: string | null;
  source: string;
  jurisdiction_id?: string | null;
  legal_basis: string;
  evidence_hash: string;
}

export type PrivacyRequestType =
  | 'ACCESS'
  | 'CORRECTION'
  | 'DELETION'
  | 'RESTRICTION'
  | 'EXPORT'
  | 'OBJECTION';

export type PrivacyRequestStatus =
  | 'SUBMITTED'
  | 'IDENTITY_VERIFICATION'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'PARTIALLY_FULFILLED'
  | 'COMPLETED'
  | 'CANCELLED';

export interface PrivacyRequest {
  id: string;
  subject_id: string;
  request_type: PrivacyRequestType;
  scope: DataCategory[];
  status: PrivacyRequestStatus;
  identity_verified: boolean;
  identity_verification_method?: string | null;
  identity_verified_at?: string | null;
  created_at: string;
  deadline_at: string;
  assigned_to?: string | null;
  completed_at?: string | null;
  export_token?: string | null;
  export_token_expires_at?: string | null;
  partial_deletion_details?: {
    deleted_categories: string[];
    retained_categories: string[];
    retention_reasons: string[];
    processed_at: string;
  } | null;
  correction_payload?: Record<string, any> | null;
  notes?: string | null;
  rejection_reason?: string | null;
}
