/**
 * TourSafe High-Frequency Sensor Timestamp Synchronizer
 * Pairs asynchronous physical Accelerometer and Gyroscope callback samples
 * using timestamp proximity matching within configurable synchronization tolerance.
 */

import { IMU_CONFIG } from "./config";
import {
  calculateAccelerationMagnitude,
  calculateAngularVelocityMagnitude,
} from "./math";
import type {
  AccelerometerSample,
  GyroscopeSample,
  IMUQualityState,
  IMUSample,
} from "../../types/imu";

export type SynchronizedSampleCallback = (sample: IMUSample) => void;

export class IMUSynchronizer {
  private accelBuffer: AccelerometerSample[] = [];
  private gyroBuffer: GyroscopeSample[] = [];
  private callback: SynchronizedSampleCallback | null = null;
  private sequenceNumber = 0;
  private toleranceMs: number;
  private maxBufferCapacity = 30; // Max pending unpaired samples before pruning

  constructor(toleranceMs: number = IMU_CONFIG.SYNC_TOLERANCE_MS) {
    this.toleranceMs = toleranceMs;
  }

  public setCallback(callback: SynchronizedSampleCallback | null): void {
    this.callback = callback;
  }

  public setTolerance(toleranceMs: number): void {
    this.toleranceMs = toleranceMs;
  }

  public getTolerance(): number {
    return this.toleranceMs;
  }

  /**
   * Ingest an incoming physical Accelerometer sample.
   */
  public pushAccelerometer(sample: AccelerometerSample): void {
    this.accelBuffer.push(sample);
    if (this.accelBuffer.length > this.maxBufferCapacity) {
      this.accelBuffer.shift();
    }
    this.processPending();
  }

  /**
   * Ingest an incoming physical Gyroscope sample.
   */
  public pushGyroscope(sample: GyroscopeSample): void {
    this.gyroBuffer.push(sample);
    if (this.gyroBuffer.length > this.maxBufferCapacity) {
      this.gyroBuffer.shift();
    }
    this.processPending();
  }

  /**
   * Pair samples based on timestamp proximity within tolerance window.
   */
  private processPending(): void {
    while (this.accelBuffer.length > 0 && this.gyroBuffer.length > 0) {
      const a = this.accelBuffer[0];
      const g = this.gyroBuffer[0];

      const deltaMs = Math.abs(a.monotonic_timestamp_ms - g.monotonic_timestamp_ms);

      if (deltaMs <= this.toleranceMs) {
        // Successful pairing within synchronization tolerance
        this.accelBuffer.shift();
        this.gyroBuffer.shift();
        this.emitSynchronizedSample(a, g, deltaMs, true);
      } else if (a.monotonic_timestamp_ms < g.monotonic_timestamp_ms) {
        // Accelerometer sample is strictly older than earliest Gyroscope sample
        // Search if a closer gyro exists in the buffer
        const bestGyroIdx = this.findClosestGyroIndex(a.monotonic_timestamp_ms);
        if (bestGyroIdx !== -1) {
          const matchedGyro = this.gyroBuffer[bestGyroIdx];
          const matchDelta = Math.abs(a.monotonic_timestamp_ms - matchedGyro.monotonic_timestamp_ms);
          if (matchDelta <= this.toleranceMs) {
            this.accelBuffer.shift();
            this.gyroBuffer.splice(bestGyroIdx, 1);
            this.emitSynchronizedSample(a, matchedGyro, matchDelta, true);
            continue;
          }
        }

        // Accelerometer sample is too old to be paired with any gyro; prune orphaned sample
        this.accelBuffer.shift();
      } else {
        // Gyroscope sample is strictly older than earliest Accelerometer sample
        const bestAccelIdx = this.findClosestAccelIndex(g.monotonic_timestamp_ms);
        if (bestAccelIdx !== -1) {
          const matchedAccel = this.accelBuffer[bestAccelIdx];
          const matchDelta = Math.abs(g.monotonic_timestamp_ms - matchedAccel.monotonic_timestamp_ms);
          if (matchDelta <= this.toleranceMs) {
            this.gyroBuffer.shift();
            this.accelBuffer.splice(bestAccelIdx, 1);
            this.emitSynchronizedSample(matchedAccel, g, matchDelta, true);
            continue;
          }
        }

        // Gyroscope sample is too old to be paired; prune orphaned sample
        this.gyroBuffer.shift();
      }
    }
  }

  private findClosestGyroIndex(accelTimeMs: number): number {
    if (this.gyroBuffer.length === 0) return -1;
    let closestIdx = 0;
    let minDiff = Math.abs(this.gyroBuffer[0].monotonic_timestamp_ms - accelTimeMs);

    for (let i = 1; i < this.gyroBuffer.length; i++) {
      const diff = Math.abs(this.gyroBuffer[i].monotonic_timestamp_ms - accelTimeMs);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }
    return closestIdx;
  }

  private findClosestAccelIndex(gyroTimeMs: number): number {
    if (this.accelBuffer.length === 0) return -1;
    let closestIdx = 0;
    let minDiff = Math.abs(this.accelBuffer[0].monotonic_timestamp_ms - gyroTimeMs);

    for (let i = 1; i < this.accelBuffer.length; i++) {
      const diff = Math.abs(this.accelBuffer[i].monotonic_timestamp_ms - gyroTimeMs);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }
    return closestIdx;
  }

  private emitSynchronizedSample(
    accel: AccelerometerSample,
    gyro: GyroscopeSample,
    deltaMs: number,
    isSynchronized: boolean
  ): void {
    if (!this.callback) return;

    // Kinematic derived magnitudes (scalar invariant representations)
    const accMag = calculateAccelerationMagnitude(accel.x, accel.y, accel.z);
    const gyroMag = calculateAngularVelocityMagnitude(gyro.x, gyro.y, gyro.z);

    // Sequence index for unified synchronized stream
    const seq = ++this.sequenceNumber;
    const sampleId = `imu_${accel.session_id}_${seq}`;

    // Quality state for this individual sample
    let qualityState: IMUQualityState = "excellent";
    if (deltaMs > IMU_CONFIG.QUALITY_GOOD_MAX_SYNC_DELTA_MS) {
      qualityState = "degraded";
    } else if (deltaMs > IMU_CONFIG.QUALITY_EXCELLENT_MAX_SYNC_DELTA_MS) {
      qualityState = "good";
    }

    const imuSample: IMUSample = {
      sample_id: sampleId,
      session_id: accel.session_id,
      tourist_id: accel.tourist_id,
      device_id: accel.device_id,
      timestamp: accel.timestamp, // Primary reference wall-clock
      monotonic_timestamp_ms: accel.monotonic_timestamp_ms,
      sequence_number: seq,
      accelerometer: {
        x: accel.x,
        y: accel.y,
        z: accel.z,
      },
      gyroscope: {
        x: gyro.x,
        y: gyro.y,
        z: gyro.z,
      },
      derived: {
        acceleration_magnitude: accMag,
        angular_velocity_magnitude: gyroMag,
      },
      quality: {
        sensor_timestamp_delta_ms: Number(deltaMs.toFixed(2)),
        is_synchronized: isSynchronized,
        quality_state: qualityState,
      },
    };

    this.callback(imuSample);
  }

  public reset(): void {
    this.accelBuffer = [];
    this.gyroBuffer = [];
    this.sequenceNumber = 0;
  }
}
