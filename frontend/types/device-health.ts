/**
 * TourSafe Device Health Types
 * Diagnostic status for GPS, IMU, connectivity, battery, and platform edge telemetry.
 */

export type HealthGrade = "EXCELLENT" | "GOOD" | "DEGRADED" | "POOR" | "CRITICAL" | "UNAVAILABLE";

export interface GPSHealthStatus {
  status: HealthGrade;
  accuracyMeters: number | null;
  sampleCount: number;
  lastFixTimestamp: string | null;
  ageSeconds: number | null;
  satellitesInView?: number | null;
  isStale: boolean;
}

export interface SensorHealthStatus {
  status: HealthGrade;
  accelerometerAvailable: boolean;
  gyroscopeAvailable: boolean;
  observedFrequencyHz: number;
  jitterMs: number;
  lastSampleTimestamp: string | null;
  isStreaming: boolean;
}

export interface ConnectivityHealthStatus {
  status: HealthGrade;
  type: string;
  isConnected: boolean;
  isCellular: boolean;
  isWifi: boolean;
  latencyMs: number | null;
  offlineQueueDepth: number;
}

export interface BatteryHealthStatus {
  status: HealthGrade;
  level: number;
  isCharging: boolean;
  isLowPowerMode: boolean;
  policyKey: "normal" | "low" | "critical";
}

export interface ClockSkewInfo {
  offsetMs: number;
  estimatedAccuracyMs: number;
  lastSyncedAt: string | null;
}

export interface DeviceCapabilityProfile {
  hasGps: boolean;
  hasAccelerometer: boolean;
  hasGyroscope: boolean;
  hasBackgroundLocation: boolean;
  hasNotifications: boolean;
  platform: string;
  model: string;
  osVersion: string;
}

export interface DeviceHealthStatus {
  overallHealth: HealthGrade;
  gps: GPSHealthStatus;
  sensors: SensorHealthStatus;
  connectivity: ConnectivityHealthStatus;
  battery: BatteryHealthStatus;
  clockSkew: ClockSkewInfo;
  capabilities: DeviceCapabilityProfile;
  lastEvaluatedAt: string;
}
