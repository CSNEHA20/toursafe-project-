/**
 * TourSafe Real Hardware Accelerometer Acquisition Adapter
 * Direct interface to physical device accelerometer using Expo Sensors API.
 * NO simulated data, NO random values, NO mock fallbacks in production.
 */

import { IMU_CONFIG } from "./config";
import { getMonotonicTimeMs } from "./math";
import type { AccelerometerSample, SensorHardwareStatus } from "../../types/imu";

export interface SensorSubscription {
  remove: () => void;
}

export type AccelerometerCallback = (sample: AccelerometerSample) => void;

export class AccelerometerAdapter {
  private subscription: SensorSubscription | null = null;
  private sequenceNumber = 0;
  private currentSessionId = "";
  private touristId = "";
  private deviceId = "";
  private callback: AccelerometerCallback | null = null;
  private status: SensorHardwareStatus = "unknown";
  private isAvailableCache: boolean | null = null;

  /**
   * Check physical hardware accelerometer availability.
   */
  public async isAvailable(): Promise<boolean> {
    try {
      const { Accelerometer } = require("expo-sensors");
      if (!Accelerometer || typeof Accelerometer.isAvailableAsync !== "function") {
        this.status = "unavailable";
        this.isAvailableCache = false;
        return false;
      }
      const available = await Accelerometer.isAvailableAsync();
      this.isAvailableCache = available;
      this.status = available ? "available" : "unavailable";
      return available;
    } catch (err) {
      console.warn("[AccelerometerAdapter] Availability check note:", err);
      this.isAvailableCache = false;
      this.status = "unavailable";
      return false;
    }
  }

  public getStatus(): SensorHardwareStatus {
    return this.status;
  }

  /**
   * Subscribe to physical device accelerometer stream.
   * Target: 50 Hz (~20 ms interval).
   *
   * @throws Error if hardware accelerometer is unavailable or already active.
   */
  public async start(
    sessionId: string,
    callback: AccelerometerCallback,
    options?: {
      touristId?: string;
      deviceId?: string;
      intervalMs?: number;
    }
  ): Promise<void> {
    if (this.subscription) {
      console.warn("[AccelerometerAdapter] Subscription already active. Preventing duplicate subscription.");
      return;
    }

    const available = await this.isAvailable();
    if (!available) {
      this.status = "unavailable";
      throw new Error("Physical hardware accelerometer is not available on this device.");
    }

    this.currentSessionId = sessionId;
    this.touristId = options?.touristId || "";
    this.deviceId = options?.deviceId || "";
    this.callback = callback;
    this.sequenceNumber = 0;

    const interval = options?.intervalMs ?? IMU_CONFIG.SAMPLE_INTERVAL_MS;

    try {
      const { Accelerometer } = require("expo-sensors");
      Accelerometer.setUpdateInterval(interval);

      this.subscription = Accelerometer.addListener((data: { x: number; y: number; z: number }) => {
        if (!this.callback) return;

        const monotonicMs = getMonotonicTimeMs();
        const wallClockIso = new Date().toISOString();

        const sample: AccelerometerSample = {
          x: Number(data.x.toFixed(6)),
          y: Number(data.y.toFixed(6)),
          z: Number(data.z.toFixed(6)),
          timestamp: wallClockIso,
          monotonic_timestamp_ms: monotonicMs,
          sequence_number: ++this.sequenceNumber,
          sensor_type: "accelerometer",
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
      throw new Error(`Failed to activate physical accelerometer subscription: ${err?.message || err}`);
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
        console.warn("[AccelerometerAdapter] Error removing accelerometer subscription:", err);
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

export const accelerometerAdapter = new AccelerometerAdapter();
