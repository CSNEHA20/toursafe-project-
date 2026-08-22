export type SystemMode = 'FULL' | 'DEGRADED' | 'CRITICAL_ONLY' | 'OFFLINE';

export type ServiceStatus = 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN' | 'DISABLED';

export interface GoldenSignalsData {
  traffic: {
    total_requests: number;
    requests_2xx: number;
    requests_4xx: number;
    requests_5xx: number;
  };
  latency_ms: {
    p50: number;
    p90: number;
    p95: number;
    p99: number;
    avg: number;
    count: number;
  };
  errors: {
    error_rate_5xx: number;
    client_error_rate_4xx: number;
    dependency_errors: number;
  };
  saturation: {
    cpu_percent: number;
    memory_rss_mb: number;
    memory_vms_mb: number;
    system_memory_percent: number;
  };
}

export interface SubsystemMetricsData {
  database: {
    queries_total: number;
    slow_queries: number;
    errors: number;
    latency_ms: { p50: number; p95: number; p99: number };
  };
  redis: {
    commands_total: number;
    errors: number;
    latency_ms: { p50: number; p95: number };
  };
  queues: {
    depth: number;
    processed_total: number;
    retries_total: number;
    dead_letter_total: number;
    oldest_age_sec: number;
  };
  realtime: {
    active_connections: number;
    total_connections: number;
    reconnects: number;
    dropped_frames: number;
    latency_ms: { p50: number; p95: number };
  };
  telemetry: {
    packets_ingested: number;
    packets_dropped: number;
    sequence_gaps: number;
    offline_backlog: number;
    latency_ms: { p50: number; p95: number };
  };
  incident_operations: {
    sos_signals_received: number;
    sos_processing_failures: number;
    sos_latency_ms: { p50: number; p95: number; p99: number };
    incidents_created_total: number;
    incidents_acknowledged_total: number;
    incidents_dispatched_total: number;
    ack_latency_ms: { p50: number; p95: number };
  };
  ml_and_ai: {
    ml_inferences_total: number;
    ml_inference_failures: number;
    ml_latency_ms: { p50: number; p95: number };
    ai_requests_total: number;
    ai_timeouts: number;
    ai_fallbacks: number;
    ai_latency_ms: { p50: number; p95: number };
  };
  notifications_and_integrations: {
    notifications_sent_total: number;
    notifications_failed_total: number;
    notifications_fallback_used: number;
    integration_calls_total: number;
    integration_circuit_trips: number;
  };
}

export interface SLOItem {
  name: string;
  target?: number;
  target_ms?: number;
  window: string;
  sli_formula: string;
  actual?: number;
  actual_ms?: number;
  status: 'HEALTHY' | 'DEGRADED' | 'BUDGET_AT_RISK' | 'CRITICAL_BREACH';
  error_budget_remaining_percent?: number;
}

export interface DeadLetterItem {
  job_id: string;
  queue_name: string;
  payload: Record<string, any>;
  error_message: string;
  attempts: number;
  trace_id: string;
  correlation_id: string;
  failed_at: string;
  status: string;
}

export interface BackupItem {
  backup_id: string;
  file_path: string;
  created_at: string;
  created_by: string;
  collections: string[];
  total_documents: number;
  checksum_sha256: string;
  size_bytes: number;
  is_encrypted: boolean;
  status: string;
}
