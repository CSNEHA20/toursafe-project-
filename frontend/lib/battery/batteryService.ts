/**
 * TourSafe Battery Service
 * Monitors battery percentage, charging state, and low-power state.
 * Provides battery-aware sampling policies for adaptive telemetry behavior.
 */

import { BatteryInfo, BatteryLevelPolicy, deriveBatteryPolicy } from "@/types/battery";
import { useBatteryStore } from "@/store/batteryStore";

class BatteryService {
  private batteryLevel = 100;
  private isCharging = false;
  private isLowPowerMode = false;
  private policy: BatteryLevelPolicy = deriveBatteryPolicy(100, false, false);
  private listenerCount = 0;
  private intervalId: any = null;

  constructor() {
    this.scheduleCheck();
  }

  private scheduleCheck() {
    this.readCurrentState().then((info) => {
      useBatteryStore.getState().setBatteryInfo(info);
    });
  }

  public async readCurrentState(): Promise<BatteryInfo> {
    try {
      if (typeof navigator !== "undefined" && "getBattery" in (navigator as any)) {
        const battery: any = await (navigator as any).getBattery();
        this.batteryLevel = Math.round(battery.level * 100);
        this.isCharging = battery.charging;
        this.policy = deriveBatteryPolicy(this.batteryLevel, this.isCharging, this.isLowPowerMode);
      }
    } catch (err) {
      // Keep default
    }

    return {
      level: this.batteryLevel,
      isCharging: this.isCharging,
      isLowPowerMode: this.isLowPowerMode,
    };
  }

  public subscribe(callback: (state: BatteryInfo) => void): () => void {
    this.listenerCount += 1;
    callback({
      level: this.batteryLevel,
      isCharging: this.isCharging,
      isLowPowerMode: this.isLowPowerMode,
    });

    if (!this.intervalId) {
      this.intervalId = setInterval(async () => {
        const state = await this.readCurrentState();
        callback(state);
      }, 30000);
    }

    return () => {
      this.listenerCount -= 1;
      if (this.listenerCount <= 0 && this.intervalId) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
    };
  }

  public getCurrentPolicy(): BatteryLevelPolicy {
    return this.policy;
  }

  public allowsGPSFrequency(freqHz: number): boolean {
    return freqHz <= this.policy.gpsFrequencyHz;
  }

  public allowsIMUFrequency(freqHz: number): boolean {
    return freqHz <= this.policy.imuFrequencyHz;
  }

  public allowsBackgroundTracking(): boolean {
    return this.policy.allowBackground;
  }

  public requiresWifiOnly(): boolean {
    return this.policy.allowWifiOnly;
  }

  public allowsCellularUploads(): boolean {
    return this.policy.allowCellularOnly;
  }
}

export const batteryService = new BatteryService();
export type { BatteryInfo, BatteryLevelPolicy };