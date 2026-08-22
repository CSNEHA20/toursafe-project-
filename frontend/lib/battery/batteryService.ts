/**
 * TourSafe Battery Service
 * Monitors battery percentage, charging state, and low-power state.
 * Provides battery-aware sampling policies for adaptive telemetry behavior.
 * Tracks battery state changes and surfaces diagnostics.
 *
 * Principle: The phone adapts its telemetry behavior based on battery state,
 * but never disables safety-critical tracking entirely.
 */

import { BatteryInfo, BatteryLevelPolicy, deriveBatteryPolicy } from "../../types/battery";

/**
 * BatteryService observes the device's battery state and provides
 * policy recommendations to the telemetry pipeline.
 * It uses the native React Native Battery API or falls back to
 * periodic estimated state.
 */
class BatteryService {
  private batteryLevel = 100;
  private isCharging = false;
  private isLowPowerMode = false;
  private policy: BatteryLevelPolicy = deriveBatteryPolicy(100, false, false);
  private listenerCount = 0;
  private subscription: (() => void) | null = null;
  private checkTimer: NodeJS.Timeout | null = null;

  constructor() {
    this.scheduleCheck();
  }

  /**
   * Read current battery state from the device.
   * Uses expo-battery if available, falls back to estimation.
   */
  public async readCurrentState(): Promise<BatteryInfo> {
    try {
      // Try Expo Battery API
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { Battery } = require("expo-battery");

      if (Battery && typeof Battery.getBatteryStateAsync === "function") {
        const state = await Battery.getBatteryStateAsync();
        this.batteryLevel = state.level * 100;
        this.isCharging = state.isCharging;
        this.isLowPowerMode = state.isLowPowerMode ?? false;
      } else {
        // Fallback: estimate from level only
        this.batteryLevel = 100;
        this.isCharging = false;
        this.isLowPowerMode = false;
      }
    } catch (err) {
      console.warn("[BatteryService] Could not read battery state:", err);
    }

    return {
      level: this.batteryLevel,
      isCharging: this.isCharging,
      isLowPowerMode: this.isLowPowerMode,
    };
  }

  /**
   * Subscribe to battery state changes.
   * Caller receives updates whenever the battery state changes.
   */
  public subscribe(callback: (state: BatteryInfo) => void): () => void {
    this.listenerCount += 1;

    if (this.listenerCount === 1) {
      this.startMonitoring(callback);
    }

    return () => {
      this.listenerCount -= 1;
      if (this.listenerCount <= 0 && this.subscription) {
        this.subscription();
        this.subscription = null;
      }
    };
  }

  private startMonitoring(callback: (state: BatteryInfo) => void): void {
    try {
      // Try expo-battery monitoring
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { Battery } = require("expo-battery");

      if (Battery && typeof Battery.addBatteryStateListener === "function") {
        const unsubscribe = Battery.addBatteryStateListener(async (state) => {
          this.batteryLevel = state.level * 100;
          this.isCharging = state.isCharging;
          this.isLowPowerMode = state.isLowPowerMode ?? false;

          const newPolicy = deriveBatteryPolicy(
            this.batteryLevel,
            this.isCharging,
            this.isLowPowerMode
          );
          this.policy = newPolicy;

          callback({
            level: this.batteryLevel,
            isCharging: this.isCharging,
            isLowPowerMode: this.isLowPowerMode,
            policy: newPolicy,
          });
        });

        this.subscription = unsubscribe;
        return;
      }
    } catch (err) {
      console.warn("[BatteryService] Battery monitoring not available, using periodic check:", err);
    }

    // Fallback: periodic battery check every 30 seconds
    this.schedulePeriodicCheck(callback);
  }

  private schedulePeriodicCheck(callback: (state: BatteryInfo) => void): void {
    const check = async () => {
      const state = await this.readCurrentState();
      callback(state);
      setTimeout(() => this.schedulePeriodicCheck(callback), 30_000);
    };
    check();
  }

  public getCurrentPolicy(): BatteryLevelPolicy {
    return this.policy;
  }

  public allowsGPSFrequency(freqHz: number): boolean {
    const { policyKey, gpsFrequencyHz } = this.policy;
    return freqHz <= gpsFrequencyHz;
  }

  public allowsIMUFrequency(freqHz: number): boolean {
    const { policyKey, imuFrequencyHz } = this.policy;
    return freqHz <= imuFrequencyHz;
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