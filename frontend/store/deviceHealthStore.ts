/**
 * TourSafe Device Health Store (Zustand)
 * Central store for comprehensive device health status.
 */

import { create } from "zustand";
import {
  DeviceHealthStatus,
  ClockSkewInfo,
} from "@/types/device-health";

interface DeviceHealthStoreState {
  healthStatus: DeviceHealthStatus | null;
  lastChecked: number; // epoch ms
  clockSkew?: ClockSkewInfo;

  setHealthStatus: (status: DeviceHealthStatus | null) => void;
  setClockSkew: (skew: ClockSkewInfo | null) => void;
  updateFromHealthService: (health: DeviceHealthStatus) => void;
  reset: () => void;
}

export const useDeviceHealthStore = create<DeviceHealthStoreState>((set) => ({
  healthStatus: null,
  lastChecked: 0,
  clockSkew: undefined,

  setHealthStatus: (healthStatus) =>
    set({
      healthStatus,
      lastChecked: Date.now(),
    }),

  setClockSkew: (clockSkew) => set({ clockSkew: clockSkew ?? undefined }),

  updateFromHealthService: (health) =>
    set({
      healthStatus: health,
      lastChecked: Date.now(),
    }),

  reset: () =>
    set({
      healthStatus: null,
      lastChecked: 0,
      clockSkew: undefined,
    }),
}));