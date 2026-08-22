/**
 * TourSafe Battery Store (Zustand)
 * Central store for battery state, policy, and battery-aware sampling decisions.
 * Persists battery state across app restarts via AsyncStorage.
 */

import { create } from "zustand";
import { BatteryInfo, BatteryLevelPolicy, BATTERY_THRESHOLDS, BATTERY_POLICIES } from "@/types/battery";
import AsyncStorage from "@react-native-async-storage/async-storage";

interface BatteryStoreState {
  batteryInfo: BatteryInfo;
  lastUpdated: number; // epoch ms
  policy: BatteryLevelPolicy;

  setBatteryInfo: (info: BatteryInfo) => void;
  setPolicy: (policy: BatteryLevelPolicy) => void;
  updatePolicyFromState: (info: BatteryInfo) => void;
  reset: () => void;
}

const BATTERY_STORAGE_KEY = "@toursafe_battery_state_v1";

const initialState: BatteryStoreState = {
  batteryInfo: {
    level: 100,
    isCharging: false,
    isLowPowerMode: false,
  },
  lastUpdated: Date.now(),
  policy: deriveBatteryPolicy(100, false, false),
};

export const useBatteryStore = create<BatteryStoreState>((set, get) => ({
  batteryInfo: initialState.batteryInfo,
  lastUpdated: initialState.lastUpdated,
  policy: initialState.policy,

  setBatteryInfo: (batteryInfo) =>
    set({
      batteryInfo,
      lastUpdated: Date.now(),
      policy: deriveBatteryPolicy(
        batteryInfo.level,
        batteryInfo.isCharging,
        batteryInfo.isLowPowerMode
      ),
    }),

  setPolicy: (policy) => set({ policy }),

  updatePolicyFromState: () => {
    const { batteryInfo } = get();
    set({
      policy: deriveBatteryPolicy(
        batteryInfo.level,
        batteryInfo.isCharging,
        batteryInfo.isLowPowerMode
      ),
    });
  },

  reset: () =>
    set({
      batteryInfo: {
        level: 100,
        isCharging: false,
        isLowPowerMode: false,
      },
      lastUpdated: Date.now(),
      policy: deriveBatteryPolicy(100, false, false),
    }),
}));

// Persist battery state across restarts
// Save on every state change
useBatteryStore.setState(
  {
    // @ts-expect-error - async storage integration
    name: "@toursafe-battery-store",
    // @ts-expect-error
    size: 1,
  },
  persist(
    (state) => ({
      batteryInfo: state.batteryInfo,
      lastUpdated: state.lastUpdated,
      policy: state.policy,
    }),
    {
      storage: AsyncStorage,
      getStorageKey: (name) => BATTERY_STORAGE_KEY,
      partialize: (state) => ({
        batteryInfo: state.batteryInfo,
        lastUpdated: state.lastUpdated,
      }),
    }
  )
);