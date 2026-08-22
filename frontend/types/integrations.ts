export type IntegrationType =
  | 'MAPS'
  | 'ROUTING'
  | 'GEOCODING'
  | 'NOTIFICATION'
  | 'SMS'
  | 'VOICE'
  | 'EMAIL'
  | 'PUSH'
  | 'IDENTITY'
  | 'KYC'
  | 'WEATHER'
  | 'TRANSLATION'
  | 'DOCUMENT'
  | 'EMERGENCY_SERVICE'
  | 'GOVERNMENT'
  | 'TOURISM'
  | 'ANALYTICS'
  | 'AI'
  | 'OTHER';

export type IntegrationStatus = 'ACTIVE' | 'INACTIVE' | 'DEGRADED' | 'FAILED' | 'DISABLED';

export type CircuitBreakerState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export interface IntegrationHealthStatus {
  status: IntegrationStatus;
  is_healthy: boolean;
  latency_ms: number;
  last_successful_request?: string;
  last_failure?: string;
  consecutive_failures: number;
  circuit_state: CircuitBreakerState;
  detail: string;
  checked_at: string;
}

export interface IntegrationConfig {
  provider_name: string;
  integration_type: IntegrationType;
  environment: string;
  enabled: boolean;
  is_primary: boolean;
  fallback_provider?: string;
  endpoint_url?: string;
  timeout_seconds: number;
  connect_timeout_seconds: number;
  max_retries: number;
  retry_backoff_factor: number;
  rate_limit_per_minute: number;
  circuit_failure_threshold: number;
  circuit_recovery_cooldown_seconds: number;
  allowlist_domains: string[];
  custom_settings: Record<string, any>;
  api_key_configured: boolean;
  client_secret_configured: boolean;
  webhook_secret_configured: boolean;
}

export interface IntegrationRegistration {
  integration_id: string;
  provider_name: string;
  integration_type: IntegrationType;
  status: IntegrationStatus;
  environment: string;
  is_real_provider: boolean;
  capabilities: string[];
  configuration: IntegrationConfig;
  health: IntegrationHealthStatus;
  created_at: string;
  updated_at: string;
}

export interface DeadLetterRecord {
  record_id: string;
  timestamp: string;
  operation_name: string;
  integration_id: string;
  provider_name: string;
  integration_type: IntegrationType;
  idempotency_key: string;
  correlation_id: string;
  attempt_count: number;
  max_attempts: number;
  error_code: string;
  error_message: string;
  payload_summary: Record<string, any>;
  resolved: boolean;
  resolved_at?: string;
  resolved_by?: string;
}

export interface IntegrationAuditLog {
  audit_id: string;
  timestamp: string;
  action: string;
  integration_id?: string;
  provider_name?: string;
  integration_type?: IntegrationType;
  actor_id: string;
  actor_role: string;
  correlation_id: string;
  status: string;
  latency_ms?: number;
  details: Record<string, any>;
}

export interface ExternalStateConflict {
  conflict_id: string;
  toursafe_incident_id: string;
  external_system: string;
  external_incident_id: string;
  toursafe_status: string;
  external_status: string;
  detected_at: string;
  resolved: boolean;
  resolution_policy?: string;
  resolved_status?: string;
  resolved_by?: string;
  resolved_at?: string;
}
