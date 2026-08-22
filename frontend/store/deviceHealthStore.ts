/**
 * TourSafe Device Health Store (Zustand)
 * Central store for comprehensive device health status.
 * Persists latest health status across app restarts via AsyncStorage.
 */

import { create } from "zustand";
import {
  DeviceHealthStatus,
  BatteryHealthStatus,
  GPSHealthStatus,
  ConnectivityHealthStatus,
  SensorHealthStatus,
  DeviceCapabilityProfile,
  ClockSkewInfo,
} from "@/types/device-health";
import AsyncStorage from "@react-native-async-storage/async-storage";

interface DeviceHealthStoreState {
  healthStatus: DeviceHealthStatus | null;
  lastChecked: number; // epoch ms
  clockSkew?: ClockSkewInfo;

  setHealthStatus: (status: DeviceHealthStatus | null) => void;
  setClockSkew: (skew: ClockSkewInfo | null) => void;
  updateFromHealthService: (health: DeviceHealthStatus) => void;
  reset: () => void;
}

const HEALTH_STORAGE_KEY = "@toursafe_device_health_v1";

const initialState: DeviceHealthStoreState = {
  healthStatus: null,
  lastChecked: 0,
};

export const useDeviceHealthStore = create<DeviceHealthStoreState>((set) => ({
  healthStatus: initialState.healthStatus,
  lastChecked: initialState.lastChecked,

  setHealthStatus: (healthStatus) =>
    set({
      healthStatus,
      lastChecked: Date.now(),
    }),

  setClockSkew: (clockSkew) => set({ clockSkew }),

  updateFromHealthService: (health) =>
    set({
      healthStatus: health,
      lastChecked: Date.now(),
    }),

  reset: () =>
    set({
      healthStatus: null,
      lastChecked: 0,
    }),
}));

// Persist health status across restarts
useDeviceHealthStore.setState(
  {
    // @ts-expect-error - async storage integration
    name: "@toursafe-device-health-store",
    // @ts-expect-error
    size: 1,
  },
  persist(
    (state) => ({
      healthStatus: state.healthStatus,
      lastChecked: state.lastChecked,
    }),
    {
      storage: AsyncStorage,
      getStorageKey: (name) => HEALTH_STORAGE_KEY,
      partialize: (state) => ({
        healthStatus: state.healthStatus,
        lastChecked: state.lastChecked,
      }),
    }
  )
);