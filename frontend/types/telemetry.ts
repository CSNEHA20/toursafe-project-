/**
 * TourSafe - Canonical Telemetry TypeScript Definitions
 * Prompt 7: Telemetry Ingestion + Window Contract
 */

export type TelemetryPacketType =
  | 'gps.sample'
  | 'imu.sample'
  | 'telemetry.sample'
  | 'telemetry.window';

export type QualityState =
  | 'excellent'
  | 'good'
  | 'fair'
  | 'poor'
  | 'degraded'
  | 'unavailable';

export type SessionStatus = 'active' | 'paused' | 'stopped' | 'stale';

export type TelemetryAckStatus =
  | 'accepted'
  | 'duplicate'
  | 'out_of_order'
  | 'rejected'
  | 'buffered';

export interface GPSPayload {
  latitude: number;
  longitude: number;
  altitude?: number | null;
  accuracy?: number | null;
  speed?: number | null;
  heading?: number | null;
  provider?: string | null;
  timestamp?: string | null;
}

export interface AccelerometerChannels {
  x: number;
  y: number;
  z: number;
}

export interface GyroscopeChannels {
  x: number;
  y: number;
  z: number;
}

export interface DerivedKinematics {
  acceleration_magnitude: number;
  jerk_magnitude: number;
  angular_velocity_magnitude: number;
  pitch_degrees?: number | null;
  roll_degrees?: number | null;
}

export interface QualityMetrics {
  gps_quality: QualityState;
  imu_quality: QualityState;
  synchronization_quality: QualityState;
  network_quality: QualityState;
  overall_quality: QualityState;
  observed_frequency_hz?: number | null;
  gps_accuracy_meters?: number | null;
  imu_jitter_ms?: number | null;
  sync_delta_ms?: number | null;
  transport_latency_ms?: number | null;
}

export interface TelemetryPacketEnvelope {
  packet_id: string;
  packet_type: TelemetryPacketType;
  session_id: string;
  sequence_number: number;
  timestamp: string;
  schema_version?: string;
  is_background?: boolean;
  network_status?: string;
  payload: {
    latitude?: number;
    longitude?: number;
    altitude?: number | null;
    accuracy?: number | null;
    speed?: number | null;
    heading?: number | null;
    accelerometer?: AccelerometerChannels;
    gyroscope?: GyroscopeChannels;
    battery_level?: number | null;
    battery_state?: string | null;
    [key: string]: any;
  };
}

export interface TelemetryAck {
  status: TelemetryAckStatus;
  packet_id: string;
  session_id: string;
  sequence_number: number;
  highest_contiguous_sequence: number;
  received_at: string;
  server_timestamp: string;
  latency_ms: number;
  errors: string[];
}

export interface TelemetryBatchRequest {
  session_id: string;
  packets: TelemetryPacketEnvelope[];
}

export interface TelemetryBatchAck {
  status: string;
  session_id: string;
  accepted_count: number;
  duplicate_count: number;
  rejected_count: number;
  highest_contiguous_sequence: number;
  missing_sequence_ranges: [number, number][];
  processed_at: string;
}

export interface TelemetrySample {
  sample_id: string;
  packet_id: string;
  packet_type: TelemetryPacketType;
  session_id: string;
  tourist_id: string;
  user_id: string;
  device_id?: string | null;
  sequence_number: number;
  timestamp: string;
  received_at: string;
  gps?: GPSPayload | null;
  accelerometer?: AccelerometerChannels | null;
  gyroscope?: GyroscopeChannels | null;
  derived?: DerivedKinematics | null;
  network_status?: string | null;
  is_background: boolean;
}

export interface TelemetryWindow {
  window_id: string;
  session_id: string;
  tourist_id: string;
  window_start: string;
  window_end: string;
  duration_seconds: number;
  sample_count: number;
  nominal_frequency_hz: number;
  actual_frequency_hz: number;
  completeness_ratio: number;
  is_valid: boolean;
  validation_errors: string[];
  max_gap_duration_ms: number;
  gps_context?: GPSPayload | null;
  mean_accel_magnitude: number;
  max_accel_magnitude: number;
  mean_gyro_magnitude: number;
  max_gyro_magnitude: number;
}

export interface TelemetrySessionMetrics {
  total_packets: number;
  accepted_packets: number;
  duplicate_packets: number;
  out_of_order_packets: number;
  estimated_missing_packets: number;
  window_count: number;
  valid_window_count: number;
  invalid_window_count: number;
  last_sequence_number: number;
  highest_contiguous_sequence: number;
}

export interface TouristTelemetryStatusResponse {
  tourist_id: string;
  active_session_id?: string | null;
  tracking_status: SessionStatus;
  imu_active: boolean;
  gps_active: boolean;
  last_telemetry_timestamp?: string | null;
  observed_imu_frequency_hz?: number | null;
  connection_state: string;
  quality: QualityMetrics;
  metrics: TelemetrySessionMetrics;
  recent_windows_generated: number;
}

export interface AuthorityTelemetryStatusResponse {
  tourist_id: string;
  session_id?: string | null;
  tracking_status: SessionStatus;
  last_location_timestamp?: string | null;
  last_telemetry_timestamp?: string | null;
  gps_quality: QualityState;
  imu_quality: QualityState;
  overall_quality: QualityState;
  connection_state: string;
  is_stale: boolean;
  age_seconds?: number | null;
}

export interface TelemetryDiagnosticsResponse {
  queue_depth: number;
  queue_capacity: number;
  enqueue_failures: number;
  processing_latency_ms: number;
  total_ingested_today: number;
  active_sessions_count: number;
  redis_health: Record<string, any>;
  mongodb_persistence_ok: boolean;
}
