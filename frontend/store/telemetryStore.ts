/**
 * TourSafe - Telemetry State Store (Zustand)
 * Prompt 7: Real Telemetry Ingestion + Window Contract
 * Tracks end-to-end telemetry session state, buffer status, quality metrics, and recent windows.
 */

import { create } from 'zustand';
import type {
  QualityMetrics,
  QualityState,
  SessionStatus,
  TelemetryAck,
  TelemetryWindow,
} from '@/types/telemetry';

interface TelemetryState {
  sessionStatus: SessionStatus;
  activeSessionId: string | null;
  sequenceNumber: number;
  highestContiguousAck: number;
  offlineBufferDepth: number;
  isOnline: boolean;
  quality: QualityMetrics;
  recentWindows: TelemetryWindow[];
  lastServerAck: TelemetryAck | null;

  setSessionStatus: (status: SessionStatus) => void;
  setActiveSessionId: (sessionId: string | null) => void;
  updateSequenceProgress: (seq: number, ack: number, bufferDepth: number, isOnline: boolean) => void;
  setQuality: (quality: QualityMetrics) => void;
  addRecentWindow: (window: TelemetryWindow) => void;
  setRecentWindows: (windows: TelemetryWindow[]) => void;
  setLastServerAck: (ack: TelemetryAck) => void;
  reset: () => void;
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

export const useTelemetryStore = create<TelemetryState>((set) => ({
  sessionStatus: 'stopped',
  activeSessionId: null,
  sequenceNumber: 0,
  highestContiguousAck: 0,
  offlineBufferDepth: 0,
  isOnline: true,
  quality: initialQuality,
  recentWindows: [],
  lastServerAck: null,

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
    }),
}));
