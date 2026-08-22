/**
 * TourSafe - Mobile Edge & Sensor Intelligence Layer
 * Prompt 17: Mobile Edge & Sensor Intelligence
 * 
 * Exports all services for the mobile telemetry pipeline.
 */

export * from '@/lib/sensors';
export * from '@/lib/battery';
export * from '@/lib/connectivity';
export * from '@/lib/telemetry';
export * from '@/lib/gps';
export * from '@/lib/tracking-session';
export * from '@/lib/device-health';

export type {
  GPSAccuracyClassification,
  GPSQualityMetadata,
  GPSJumpFilterResult,
  GGPSampleWithMetadata,
  BatteryInfo,
  BatteryLevelPolicy,
  ConnectionType,
  NetworkState,
  ConnectionInfo,
  TrackingSessionLifecycleState,
  TrackingSessionMetadata,
  TrackingGPSQuality,
  DeviceHealthStatus,
  SensorHealthStatus,
  GPSHealthStatus,
  ConnectivityHealthStatus,
  BatteryHealthStatus,
  DeviceCapabilityProfile,
  ClockSkewInfo,
  IMUQualityState,
  IMUTrackingStatus,
  SensorHardwareStatus,
  AccelerometerSample,
  GyroscopeSample,
  IMUSample,
  IMUQualityMetrics,
  IMUSession,
  IMUSampleBatch,
  IMUTelemetryMessage,
  TelemetryPacketType,
  QualityState,
  SessionStatus,
  TelemetryAckStatus,
  TelemetryPacketEnvelope,
  TelemetryAck,
  TelemetryBatchRequest,
  TelemetryBatchAck,
  TelemetrySample,
  TelemetryWindow,
  TelemetrySessionMetrics,
  TouristTelemetryStatusResponse,
  AuthorityTelemetryStatusResponse,
  TelemetryDiagnosticsResponse,
};