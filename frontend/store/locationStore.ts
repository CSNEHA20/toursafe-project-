/**
 * TourSafe Location Store (Zustand)
 * Central store for real-time GPS tracking state, active session, quality metrics, and sample buffer.
 */

import { create } from "zustand";
import type {
  LocationPermissionState,
  LocationQualityMetrics,
  LocationSample,
  LocationTrackingStatus,
  TrackingSession,
} from "@/types/location";

interface LocationState {
  permissionState: LocationPermissionState;
  trackingStatus: LocationTrackingStatus;
  activeSession: TrackingSession | null;
  currentLocation: LocationSample | null;
  qualityMetrics: LocationQualityMetrics;
  recentSamples: LocationSample[];
  lastTransmittedSequence: number;
  lastServerError: string | null;
  isBackgroundTracking: boolean;

  setPermissionState: (state: LocationPermissionState) => void;
  setTrackingStatus: (status: LocationTrackingStatus) => void;
  setActiveSession: (session: TrackingSession | null) => void;
  setCurrentLocation: (sample: LocationSample | null) => void;
  setQualityMetrics: (metrics: LocationQualityMetrics) => void;
  appendSample: (sample: LocationSample) => void;
  setLastTransmittedSequence: (seq: number) => void;
  setLastServerError: (error: string | null) => void;
  setIsBackgroundTracking: (active: boolean) => void;
  reset: () => void;
}

const initialQualityMetrics: LocationQualityMetrics = {
  qualityState: "unavailable",
  sampleCount: 0,
  observedFrequencyHz: 0,
  averageIntervalMs: 0,
  minIntervalMs: 0,
  maxIntervalMs: 0,
  currentAccuracyMeters: null,
  staleDurationSeconds: 0,
  lastUpdateTimestamp: null,
};

export const useLocationStore = create<LocationState>((set, get) => ({
  permissionState: "unknown",
  trackingStatus: "idle",
  activeSession: null,
  currentLocation: null,
  qualityMetrics: initialQualityMetrics,
  recentSamples: [],
  lastTransmittedSequence: 0,
  lastServerError: null,
  isBackgroundTracking: false,

  setPermissionState: (permissionState) => set({ permissionState }),
  setTrackingStatus: (trackingStatus) => set({ trackingStatus }),
  setActiveSession: (activeSession) => set({ activeSession }),
  setCurrentLocation: (currentLocation) => set({ currentLocation }),
  setQualityMetrics: (qualityMetrics) => set({ qualityMetrics }),
  appendSample: (sample) => {
    const current = get().recentSamples;
    const updated = [...current.slice(-49), sample]; // keep up to 50 recent samples
    set({
      currentLocation: sample,
      recentSamples: updated,
      lastTransmittedSequence: sample.sequence_number,
    });
  },
  setLastTransmittedSequence: (lastTransmittedSequence) => set({ lastTransmittedSequence }),
  setLastServerError: (lastServerError) => set({ lastServerError }),
  setIsBackgroundTracking: (isBackgroundTracking) => set({ isBackgroundTracking }),
  reset: () =>
    set({
      trackingStatus: "idle",
      activeSession: null,
      currentLocation: null,
      qualityMetrics: initialQualityMetrics,
      recentSamples: [],
      lastTransmittedSequence: 0,
      lastServerError: null,
      isBackgroundTracking: false,
    }),
}));
