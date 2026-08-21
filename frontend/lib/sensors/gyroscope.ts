/**
 * TourSafe Real Hardware Gyroscope Acquisition Adapter
 * Direct interface to physical device gyroscope using Expo Sensors API.
 * NO simulated data, NO random values, NO mock fallbacks in production.
 */

import { IMU_CONFIG } from "./config";
import { getMonotonicTimeMs } from "./math";
import type { SensorSubscription } from "./accelerometer";
import type { GyroscopeSample, SensorHardwareStatus } from "../../types/imu";

export type GyroscopeCallback = (sample: GyroscopeSample) => void;

export class GyroscopeAdapter {
  private subscription: SensorSubscription | null = null;
  private sequenceNumber = 0;
  private currentSessionId = "";
  private touristId = "";
  private deviceId = "";
  private callback: GyroscopeCallback | null = null;
  private status: SensorHardwareStatus = "unknown";
  private isAvailableCache: boolean | null = null;

  /**
   * Check physical hardware gyroscope availability.
   */
  public async isAvailable(): Promise<boolean> {
    try {
      const { Gyroscope } = require("expo-sensors");
      if (!Gyroscope || typeof Gyroscope.isAvailableAsync !== "function") {
        this.status = "unavailable";
        this.isAvailableCache = false;
        return false;
      }
      const available = await Gyroscope.isAvailableAsync();
      this.isAvailableCache = available;
      this.status = available ? "available" : "unavailable";
      return available;
    } catch (err) {
      console.warn("[GyroscopeAdapter] Availability check note:", err);
      this.isAvailableCache = false;
      this.status = "unavailable";
      return false;
    }
  }

  public getStatus(): SensorHardwareStatus {
    return this.status;
  }

  /**
   * Subscribe to physical device gyroscope stream.
   * Target: 50 Hz (~20 ms interval).
   * Units: radians per second (rad/s).
   *
   * @throws Error if hardware gyroscope is unavailable or already active.
   */
  public async start(
    sessionId: string,
    callback: GyroscopeCallback,
    options?: {
      touristId?: string;
      deviceId?: string;
      intervalMs?: number;
    }
  ): Promise<void> {
    if (this.subscription) {
      console.warn("[GyroscopeAdapter] Subscription already active. Preventing duplicate subscription.");
      return;
    }

    const available = await this.isAvailable();
    if (!available) {
      this.status = "unavailable";
      throw new Error("Physical hardware gyroscope is not available on this device.");
    }

    this.currentSessionId = sessionId;
    this.touristId = options?.touristId || "";
    this.deviceId = options?.deviceId || "";
    this.callback = callback;
    this.sequenceNumber = 0;

    const interval = options?.intervalMs ?? IMU_CONFIG.SAMPLE_INTERVAL_MS;

    try {
      const { Gyroscope } = require("expo-sensors");
      Gyroscope.setUpdateInterval(interval);

      this.subscription = Gyroscope.addListener((data: { x: number; y: number; z: number }) => {
        if (!this.callback) return;

        const monotonicMs = getMonotonicTimeMs();
        const wallClockIso = new Date().toISOString();

        const sample: GyroscopeSample = {
          x: Number(data.x.toFixed(6)),
          y: Number(data.y.toFixed(6)),
          z: Number(data.z.toFixed(6)),
          timestamp: wallClockIso,
          monotonic_timestamp_ms: monotonicMs,
          sequence_number: ++this.sequenceNumber,
          sensor_type: "gyroscope",
          session_id: this.currentSessionId,
          tourist_id: this.touristId || undefined,
          device_id: this.deviceId || undefined,
        };

        this.callback(sample);
      });

      this.status = "active";
    } catch (err: any) {
      this.status = "error";
      this.subscription = null;
      throw new Error(`Failed to activate physical gyroscope subscription: ${err?.message || err}`);
    }
  }

  /**
   * Cleanly stop subscription and release hardware resources.
   */
  public stop(): void {
    if (this.subscription) {
      try {
        this.subscription.remove();
      } catch (err) {
        console.warn("[GyroscopeAdapter] Error removing gyroscope subscription:", err);
      }
      this.subscription = null;
    }
    this.callback = null;
    this.status = this.isAvailableCache ? "available" : "unavailable";
  }

  public resetSequence(): void {
    this.sequenceNumber = 0;
  }
}

export const gyroscopeAdapter = new GyroscopeAdapter();
