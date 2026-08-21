/**
 * TourSafe Sensor Quality Monitoring Engine
 * Calculates real-time observed sampling frequencies, inter-sample jitter,
 * delivery gaps, synchronization offsets, and health classification.
 */

import { IMU_CONFIG } from "./config";
import { calculateIntervalStatistics, calculateObservedFrequency } from "./math";
import type {
  IMUQualityMetrics,
  IMUQualityState,
  IMUSample,
} from "../../types/imu";

export class IMUQualityEngine {
  private startTimeMs: number | null = null;
  private lastSampleTimeMs: number | null = null;
  private lastAccelTimeMs: number | null = null;
  private lastGyroTimeMs: number | null = null;

  private totalSynchronizedSamples = 0;
  private totalAccelSamples = 0;
  private totalGyroSamples = 0;

  private recentIntervals: number[] = [];
  private maxIntervalHistory = 100; // Sliding window of last 100 sample intervals

  // Delivery Gap tracking
  private sampleGapCount = 0;
  private largestGapMs = 0;
  private totalGapDurationMs = 0;

  // Latest metadata
  private latestSyncDeltaMs = 0;
  private lastUpdateTimestamp: string | null = null;

  // Hardware status
  private accelAvailable = false;
  private gyroAvailable = false;

  public setHardwareAvailability(accelAvailable: boolean, gyroAvailable: boolean): void {
    this.accelAvailable = accelAvailable;
    this.gyroAvailable = gyroAvailable;
  }

  public recordAccelerometerSample(timestampMs: number): void {
    this.totalAccelSamples += 1;
    this.lastAccelTimeMs = timestampMs;
  }

  public recordGyroscopeSample(timestampMs: number): void {
    this.totalGyroSamples += 1;
    this.lastGyroTimeMs = timestampMs;
  }

  public recordSynchronizedSample(sample: IMUSample): IMUQualityMetrics {
    const now = sample.monotonic_timestamp_ms;
    this.totalSynchronizedSamples += 1;
    this.lastUpdateTimestamp = sample.timestamp;
    this.latestSyncDeltaMs = sample.quality.sensor_timestamp_delta_ms;

    if (!this.startTimeMs) {
      this.startTimeMs = now;
      this.lastSampleTimeMs = now;
      return this.getMetrics();
    }

    const interval = now - (this.lastSampleTimeMs ?? now);
    this.lastSampleTimeMs = now;

    if (interval > 0) {
      this.recentIntervals.push(interval);
      if (this.recentIntervals.length > this.maxIntervalHistory) {
        this.recentIntervals.shift();
      }

      // Detect sample delivery gap (> 50ms = 2.5x expected 20ms)
      if (interval >= IMU_CONFIG.GAP_THRESHOLD_MS) {
        this.sampleGapCount += 1;
        if (interval > this.largestGapMs) {
          this.largestGapMs = Number(interval.toFixed(2));
        }
        this.totalGapDurationMs += interval;
      }
    }

    return this.getMetrics();
  }

  /**
   * Compute comprehensive real-time metrics.
   */
  public getMetrics(): IMUQualityMetrics {
    if (!this.accelAvailable || !this.gyroAvailable) {
      return this.buildMetrics("unavailable", 0, 0, 0, 0, {
        averageIntervalMs: 0,
        minIntervalMs: 0,
        maxIntervalMs: 0,
        jitterMs: 0,
      });
    }

    const elapsedMs = this.startTimeMs && this.lastSampleTimeMs
      ? Math.max(1, this.lastSampleTimeMs - this.startTimeMs)
      : 1;

    const syncHz = calculateObservedFrequency(this.totalSynchronizedSamples, elapsedMs);
    const accelHz = calculateObservedFrequency(this.totalAccelSamples, elapsedMs);
    const gyroHz = calculateObservedFrequency(this.totalGyroSamples, elapsedMs);

    const stats = calculateIntervalStatistics(this.recentIntervals);

    // Evaluate Quality State based on measured frequency, jitter, and gaps
    const qualityState = this.evaluateQualityState(syncHz, stats.jitterMs, this.latestSyncDeltaMs);

    return this.buildMetrics(qualityState, syncHz, accelHz, gyroHz, syncHz, stats);
  }

  private evaluateQualityState(
    hz: number,
    jitterMs: number,
    syncDeltaMs: number
  ): IMUQualityState {
    if (!this.accelAvailable || !this.gyroAvailable) {
      return "unavailable";
    }

    if (this.totalSynchronizedSamples < 5) {
      // Warming up
      return "good";
    }

    if (
      hz >= IMU_CONFIG.QUALITY_EXCELLENT_MIN_HZ &&
      jitterMs <= IMU_CONFIG.QUALITY_EXCELLENT_MAX_JITTER_MS &&
      syncDeltaMs <= IMU_CONFIG.QUALITY_EXCELLENT_MAX_SYNC_DELTA_MS
    ) {
      return "excellent";
    }

    if (
      hz >= IMU_CONFIG.QUALITY_GOOD_MIN_HZ &&
      jitterMs <= IMU_CONFIG.QUALITY_GOOD_MAX_JITTER_MS &&
      syncDeltaMs <= IMU_CONFIG.QUALITY_GOOD_MAX_SYNC_DELTA_MS
    ) {
      return "good";
    }

    if (hz >= IMU_CONFIG.QUALITY_DEGRADED_MIN_HZ) {
      return "degraded";
    }

    return "poor";
  }

  private buildMetrics(
    qualityState: IMUQualityState,
    observedFrequencyHz: number,
    accelHz: number,
    gyroHz: number,
    syncHz: number,
    stats: {
      averageIntervalMs: number;
      minIntervalMs: number;
      maxIntervalMs: number;
      jitterMs: number;
    }
  ): IMUQualityMetrics {
    return {
      qualityState,
      sampleCount: this.totalSynchronizedSamples,
      observedFrequencyHz,
      accelerometerFrequencyHz: accelHz,
      gyroscopeFrequencyHz: gyroHz,
      synchronizedFrequencyHz: syncHz,
      averageIntervalMs: stats.averageIntervalMs,
      minIntervalMs: stats.minIntervalMs,
      maxIntervalMs: stats.maxIntervalMs,
      jitterMs: stats.jitterMs,
      sampleGapCount: this.sampleGapCount,
      largestGapMs: this.largestGapMs,
      totalGapDurationMs: Number(this.totalGapDurationMs.toFixed(2)),
      timestampDeltaMs: Number(this.latestSyncDeltaMs.toFixed(2)),
      lastUpdateTimestamp: this.lastUpdateTimestamp,
      accelerometerAvailable: this.accelAvailable,
      gyroscopeAvailable: this.gyroAvailable,
    };
  }

  public reset(): void {
    this.startTimeMs = null;
    this.lastSampleTimeMs = null;
    this.lastAccelTimeMs = null;
    this.lastGyroTimeMs = null;
    this.totalSynchronizedSamples = 0;
    this.totalAccelSamples = 0;
    this.totalGyroSamples = 0;
    this.recentIntervals = [];
    this.sampleGapCount = 0;
    this.largestGapMs = 0;
    this.totalGapDurationMs = 0;
    this.latestSyncDeltaMs = 0;
    this.lastUpdateTimestamp = null;
  }
}
