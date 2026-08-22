/**
 * TourSafe - Telemetry State Store (Zustand)
 * Prompt 7: Real Telemetry Ingestion + Window Contract
 * Tracks end-to-end telemetry session state, buffer status, quality metrics, and recent windows.
 * Updated for Prompt 17: Mobile Edge & Sensor Intelligence.
 */

import { create } from 'zustand';
import type {
  QualityMetrics,
  QualityState,
  SessionStatus,
  TelemetryAck,
  TelemetryWindow,
  GGPSampleWithMetadata,
} from '@/types/telemetry';
import type { DeviceHealthStatus } from '@/types/device-health';
import { telemetryService } from '@/lib/telemetry/telemetryService';
import { telemetryOfflineBuffer } from '@/lib/telemetry/offlineBuffer';
import { batteryService } from '@/lib/battery/batteryService';
import { connectivityService } from '@/lib/connectivity/connectivityService';
import { gpsService } from '@/lib/gps/gpsService';
import { deviceHealthService } from '@/lib/device-health/deviceHealthService';


interface TelemetryState {
  sessionStatus: SessionStatus;
  activeSessionId: string | null;
  sequenceNumber: number;
  highestContiguousAck: number;
  offlineBufferDepth: number;
  isOnline: boolean;
  quality: QualityMetrics;
  recentWindows: any[];
  lastServerAck: TelemetryAck | null;
  deviceHealth: DeviceHealthStatus | null;
  gpsSample: GGPSampleWithMetadata | null;
  lastGPSQuality: QualityState;

  setSessionStatus: (status: SessionStatus) => void;
  setActiveSessionId: (sessionId: string | null) => void;
  updateSequenceProgress: (seq: number, ack: number, bufferDepth: number, isOnline: boolean) => void;
  setQuality: (quality: QualityMetrics) => void;
  addRecentWindow: (window: any) => void;
  setRecentWindows: (windows: any[]) => void;
  setLastServerAck: (ack: TelemetryAck) => void;
  setDeviceHealth: (health: DeviceHealthStatus | null) => void;
  setGPSSample: (sample: GGPSampleWithMetadata | null) => void;
  setLastGPSQuality: (quality: QualityState) => void;
  reset: () => void;
  forceHealthCheck: () => Promise<void>;
}

const initialQuality: QualityMetrics = {
  gps_quality: 'unavailable' as QualityState,
  imu_quality: 'unavailable' as QualityState,
  synchronization_quality: 'unavailable' as QualityState,
  network_quality: 'good' as QualityState,
  overall_quality: 'unavailable' as QualityState,
  observed_frequency_hz: 0,
  gps_accuracy_meters: 0,
  imu_jitter_ms: 0,
  sync_delta_ms: 0,
  transport_latency_ms: 0,
};

export const useTelemetryStore = create<TelemetryState>((set, get) => ({
  sessionStatus: 'stopped',
  activeSessionId: null,
  sequenceNumber: 0,
  highestContiguousAck: 0,
  offlineBufferDepth: 0,
  isOnline: true,
  quality: initialQuality,
  recentWindows: [],
  lastServerAck: null,
  deviceHealth: null,
  gpsSample: null,
  lastGPSQuality: 'unavailable',

  setSessionStatus: (sessionStatus) => set({ sessionStatus }),

  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),

  updateSequenceProgress: (sequenceNumber, highestContiguousAck, offlineBufferDepth, isOnline) =>
    set({
      sequenceNumber,
      highestContiguousAck,
      offlineBufferDepth,
      isOnline,
    }),

  setQuality: (quality) => set({ quality }),

  addRecentWindow: (window) =>
    set((state) => ({
      recentWindows: [window, ...state.recentWindows].slice(0, 20),
    })),

  setRecentWindows: (recentWindows) => set({ recentWindows }),

  setLastServerAck: (lastServerAck) => set({ lastServerAck }),

  setDeviceHealth: (deviceHealth) => set({ deviceHealth }),

  setGPSSample: (gpsSample) => set({ gpsSample }),

  setLastGPSQuality: (lastGPSQuality) => set({ lastGPSQuality }),

  reset: () =>
    set({
      sessionStatus: 'stopped',
      activeSessionId: null,
      sequenceNumber: 0,
      highestContiguousAck: 0,
      offlineBufferDepth: 0,
      isOnline: true,
      quality: initialQuality,
      recentWindows: [],
      lastServerAck: null,
      deviceHealth: null,
      gpsSample: null,
      lastGPSQuality: 'unavailable',
    }),

  forceHealthCheck: async () => {
    try {
      const health = deviceHealthService.evaluateOverallHealth();
      set({ deviceHealth: health });
    } catch (e) {
      console.warn("Telemetry store health check failed:", e);
    }
  },
}));