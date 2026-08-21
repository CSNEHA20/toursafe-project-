/**
 * TourSafe Real IMU Sensor Types & Interfaces
 * Canonical definitions for physical device Accelerometer & Gyroscope telemetry,
 * timestamp synchronization, sequence ordering, quality metrics, and session lifecycle.
 */

export type IMUQualityState =
  | "excellent"    // >= 45 Hz, jitter <= 5ms, sync delta <= 10ms
  | "good"         // >= 35 Hz, jitter <= 10ms, sync delta <= 20ms
  | "degraded"     // >= 20 Hz, jitter <= 20ms, sync delta <= 35ms
  | "poor"         // < 20 Hz or high jitter/delivery gaps
  | "unavailable"; // Hardware sensor missing or permission denied

export type IMUTrackingStatus =
  | "idle"
  | "starting"
  | "active"
  | "paused"
  | "stopped"
  | "error";

export type SensorHardwareStatus =
  | "unknown"
  | "available"
  | "unavailable"
  | "active"
  | "error";

/**
 * Raw physical device Accelerometer measurement.
 * Units: 'g' (Earth gravitational acceleration, ~9.80665 m/s^2 per g) from expo-sensors.
 */
export interface AccelerometerSample {
  x: number; // Acceleration on X-axis (g)
  y: number; // Acceleration on Y-axis (g)
  z: number; // Acceleration on Z-axis (g)
  timestamp: string; // ISO 8601 UTC string
  monotonic_timestamp_ms: number; // High-precision monotonic timer (ms)
  sequence_number: number; // Monotonically increasing per-session sequence
  sensor_type: "accelerometer";
  session_id: string;
  tourist_id?: string;
  device_id?: string;
}

/**
 * Raw physical device Gyroscope measurement.
 * Units: radians per second (rad/s) from expo-sensors.
 */
export interface GyroscopeSample {
  x: number; // Angular velocity around X-axis (rad/s)
  y: number; // Angular velocity around Y-axis (rad/s)
  z: number; // Angular velocity around Z-axis (rad/s)
  timestamp: string; // ISO 8601 UTC string
  monotonic_timestamp_ms: number; // High-precision monotonic timer (ms)
  sequence_number: number; // Monotonically increasing per-session sequence
  sensor_type: "gyroscope";
  session_id: string;
  tourist_id?: string;
  device_id?: string;
}

/**
 * Canonical Synchronized IMU Sample.
 * Pairs physical accelerometer and gyroscope samples within a precise synchronization tolerance.
 * Preserves raw XYZ channels and computes derived magnitudes.
 */
export interface IMUSample {
  sample_id: string;
  session_id: string;
  tourist_id?: string;
  device_id?: string;
  timestamp: string; // ISO 8601 UTC wall-clock
  monotonic_timestamp_ms: number; // High-precision monotonic time (ms)
  sequence_number: number; // Monotonically increasing synchronized index

  // Raw preserved 3-axis accelerometer channels (units: g)
  accelerometer: {
    x: number;
    y: number;
    z: number;
  };

  // Raw preserved 3-axis gyroscope channels (units: rad/s)
  gyroscope: {
    x: number;
    y: number;
    z: number;
  };

  // Derived kinematic features (raw channels are NEVER replaced)
  derived: {
    acceleration_magnitude: number; // sqrt(ax^2 + ay^2 + az^2) in g
    angular_velocity_magnitude: number; // sqrt(gx^2 + gy^2 + gz^2) in rad/s
  };

  // Telemetry quality & synchronization metadata
  quality: {
    sensor_timestamp_delta_ms: number; // |t_accel - t_gyro| in ms
    is_synchronized: boolean; // True if within synchronization tolerance
    quality_state: IMUQualityState;
  };
}

/**
 * Detailed real-time quality & sampling statistics.
 */
export interface IMUQualityMetrics {
  qualityState: IMUQualityState;
  sampleCount: number;
  observedFrequencyHz: number; // Measured: sample_count / elapsed_time
  accelerometerFrequencyHz: number; // Measured accelerometer callback rate
  gyroscopeFrequencyHz: number; // Measured gyroscope callback rate
  synchronizedFrequencyHz: number; // Rate of valid paired IMU records
  averageIntervalMs: number; // Mean interval between consecutive samples
  minIntervalMs: number; // Minimum observed interval
  maxIntervalMs: number; // Maximum observed interval
  jitterMs: number; // Standard deviation of inter-sample intervals
  sampleGapCount: number; // Number of delivery intervals > GAP_THRESHOLD
  largestGapMs: number; // Longest observed callback gap
  totalGapDurationMs: number; // Cumulative duration of all detected gaps
  timestampDeltaMs: number; // Latest accelerometer-gyroscope synchronization offset
  lastUpdateTimestamp: string | null;
  accelerometerAvailable: boolean;
  gyroscopeAvailable: boolean;
}

/**
 * IMU Tracking Session Model.
 */
export interface IMUSession {
  session_id: string;
  tourist_id: string;
  device_id?: string;
  started_at: string;
  ended_at?: string | null;
  status: IMUTrackingStatus;
  imu_enabled: boolean;
  accelerometer_enabled: boolean;
  gyroscope_enabled: boolean;
  last_accelerometer_timestamp?: string | null;
  last_gyroscope_timestamp?: string | null;
  last_sequence_number: number;
  observed_frequency: number;
  quality_state: IMUQualityState;
}

/**
 * Batch payload for high-frequency transport.
 */
export interface IMUSampleBatch {
  session_id: string;
  tourist_id?: string;
  device_id?: string;
  batch_timestamp: string;
  samples: IMUSample[];
}

/**
 * Realtime telemetry message payload.
 */
export interface IMUTelemetryMessage {
  type: "imu.sample" | "imu.batch";
  session_id: string;
  sequence_number?: number;
  timestamp: string;
  sample?: IMUSample;
  samples?: IMUSample[];
}
