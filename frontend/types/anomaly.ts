/**
 * TourSafe Anomaly & ML Inference Frontend Type Definitions
 * Prompt 9: Real-Time LSTM Inference Service
 */

export interface AnomalyEpisodeItem {
  anomaly_id: string;
  tourist_id: string;
  session_id: string;
  model_version: string;
  started_at: string;
  cleared_at?: string | null;
  status: "active" | "resolved";
  current_score: number;
  peak_score: number;
  threshold: number;
  window_count: number;
  duration_seconds: number;
  quality?: {
    overall_quality?: string;
    gps_quality?: string;
    imu_quality?: string;
    observed_frequency_hz?: number;
    completeness_ratio?: number;
  };
  last_known_gps?: {
    latitude: number;
    longitude: number;
    accuracy?: number;
  } | null;
}

export interface AnomalyDetectedPayload {
  anomaly_id: string;
  tourist_id: string;
  session_id: string;
  model_version: string;
  timestamp: string;
  window_start: string;
  window_end: string;
  anomaly_score: number;
  threshold: number;
  persistence_count: number;
  quality?: Record<string, any>;
  last_known_gps?: {
    latitude: number;
    longitude: number;
    accuracy?: number;
  } | null;
  source: string;
}

export interface AnomalyClearedPayload {
  anomaly_id: string;
  tourist_id: string;
  session_id: string;
  model_version: string;
  timestamp: string;
  duration_seconds: number;
  peak_score: number;
  recovery_score: number;
  threshold: number;
  source: string;
}

export interface MLHealthStatus {
  model_health: string;
  model_version: string;
  artifact_status: string;
  preprocessing_status: string;
  threshold_status: string;
  runtime_framework: string;
  device: string;
  total_inferences: number;
  queue_depth: number;
  queue_capacity: number;
  inference_rate_sec: number;
  error_rate: number;
  average_latency_ms: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
}
