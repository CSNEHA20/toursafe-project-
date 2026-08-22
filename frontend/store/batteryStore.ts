/**
 * TourSafe Battery Store (Zustand)
 * Central store for battery state, policy, and battery-aware sampling decisions.
 */

import { create } from "zustand";
import { BatteryInfo, BatteryLevelPolicy, deriveBatteryPolicy } from "@/types/battery";

interface BatteryStoreState {
  batteryInfo: BatteryInfo;
  lastUpdated: number; // epoch ms
  policy: BatteryLevelPolicy;

  setBatteryInfo: (info: BatteryInfo) => void;
  setPolicy: (policy: BatteryLevelPolicy) => void;
  updatePolicyFromState: (info: BatteryInfo) => void;
  reset: () => void;
}

const initialInfo: BatteryInfo = {
  level: 100,
  isCharging: false,
  isLowPowerMode: false,
};

export const useBatteryStore = create<BatteryStoreState>((set, get) => ({
  batteryInfo: initialInfo,
  lastUpdated: Date.now(),
  policy: deriveBatteryPolicy(100, false, false),

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
      batteryInfo: initialInfo,
      lastUpdated: Date.now(),
      policy: deriveBatteryPolicy(100, false, false),
    }),
}));