/**
 * TourSafe IMU Sensor State Store (Zustand)
 * High-performance state management for physical IMU telemetry,
 * real-time quality metrics, active session, and diagnostic state.
 * High-frequency stream lives in bounded buffer to keep React state lightweight.
 */

import { create } from "zustand";
import type {
  IMUQualityMetrics,
  IMUSample,
  IMUSession,
  IMUTrackingStatus,
  SensorHardwareStatus,
} from "@/types/imu";

interface IMUState {
  imuStatus: IMUTrackingStatus;
  accelerometerStatus: SensorHardwareStatus;
  gyroscopeStatus: SensorHardwareStatus;
  latestIMUSample: IMUSample | null;
  imuFrequency: number;
  accelerometerFrequency: number;
  gyroscopeFrequency: number;
  synchronizationQuality: number; // in ms delta (lower is better)
  sampleGapCount: number;
  lastIMUTimestamp: string | null;
  imuError: string | null;
  imuSessionId: string | null;
  activeSession: IMUSession | null;
  qualityMetrics: IMUQualityMetrics;

  setIMUStatus: (status: IMUTrackingStatus) => void;
  setAccelerometerStatus: (status: SensorHardwareStatus) => void;
  setGyroscopeStatus: (status: SensorHardwareStatus) => void;
  setLatestIMUSample: (sample: IMUSample | null) => void;
  setQualityMetrics: (metrics: IMUQualityMetrics) => void;
  setActiveSession: (session: IMUSession | null) => void;
  setIMUError: (error: string | null) => void;
  reset: () => void;
}

const initialQualityMetrics: IMUQualityMetrics = {
  qualityState: "unavailable",
  sampleCount: 0,
  observedFrequencyHz: 0,
  accelerometerFrequencyHz: 0,
  gyroscopeFrequencyHz: 0,
  synchronizedFrequencyHz: 0,
  averageIntervalMs: 0,
  minIntervalMs: 0,
  maxIntervalMs: 0,
  jitterMs: 0,
  sampleGapCount: 0,
  largestGapMs: 0,
  totalGapDurationMs: 0,
  timestampDeltaMs: 0,
  lastUpdateTimestamp: null,
  accelerometerAvailable: false,
  gyroscopeAvailable: false,
};

export const useIMUStore = create<IMUState>((set) => ({
  imuStatus: "idle",
  accelerometerStatus: "unknown",
  gyroscopeStatus: "unknown",
  latestIMUSample: null,
  imuFrequency: 0,
  accelerometerFrequency: 0,
  gyroscopeFrequency: 0,
  synchronizationQuality: 0,
  sampleGapCount: 0,
  lastIMUTimestamp: null,
  imuError: null,
  imuSessionId: null,
  activeSession: null,
  qualityMetrics: initialQualityMetrics,

  setIMUStatus: (imuStatus) => set({ imuStatus }),
  setAccelerometerStatus: (accelerometerStatus) => set({ accelerometerStatus }),
  setGyroscopeStatus: (gyroscopeStatus) => set({ gyroscopeStatus }),
  setLatestIMUSample: (sample) =>
    set({
      latestIMUSample: sample,
      lastIMUTimestamp: sample ? sample.timestamp : null,
      synchronizationQuality: sample ? sample.quality.sensor_timestamp_delta_ms : 0,
    }),
  setQualityMetrics: (qualityMetrics) =>
    set({
      qualityMetrics,
      imuFrequency: qualityMetrics.observedFrequencyHz,
      accelerometerFrequency: qualityMetrics.accelerometerFrequencyHz,
      gyroscopeFrequency: qualityMetrics.gyroscopeFrequencyHz,
      sampleGapCount: qualityMetrics.sampleGapCount,
    }),
  setActiveSession: (activeSession) =>
    set({
      activeSession,
      imuSessionId: activeSession ? activeSession.session_id : null,
    }),
  setIMUError: (imuError) => set({ imuError }),
  reset: () =>
    set({
      imuStatus: "idle",
      latestIMUSample: null,
      imuFrequency: 0,
      accelerometerFrequency: 0,
      gyroscopeFrequency: 0,
      synchronizationQuality: 0,
      sampleGapCount: 0,
      lastIMUTimestamp: null,
      imuError: null,
      imuSessionId: null,
      activeSession: null,
      qualityMetrics: initialQualityMetrics,
    }),
}));
