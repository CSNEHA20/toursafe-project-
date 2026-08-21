/**
 * TourSafe Bounded IMU In-Memory Buffer
 * Fixed-capacity circular sliding window maintaining recent synchronized IMU samples
 * in strict monotonic sequence order for real-time monitoring and diagnostic export.
 */

import { IMU_CONFIG } from "./config";
import type { IMUSample } from "../../types/imu";

export class BoundedIMUBuffer {
  private buffer: IMUSample[] = [];
  private readonly maxCapacity: number;

  constructor(maxCapacity: number = IMU_CONFIG.BUFFER_MAX_CAPACITY) {
    this.maxCapacity = Math.max(1, maxCapacity);
  }

  /**
   * Push a new synchronized IMU sample into the bounded buffer.
   * Evicts oldest sample when buffer reaches maxCapacity.
   */
  public push(sample: IMUSample): void {
    this.buffer.push(sample);
    if (this.buffer.length > this.maxCapacity) {
      this.buffer.shift();
    }
  }

  /**
   * Get the most recent N samples (default returns all available buffered samples).
   */
  public getRecent(count?: number): IMUSample[] {
    if (!count || count >= this.buffer.length) {
      return [...this.buffer];
    }
    return this.buffer.slice(-count);
  }

  /**
   * Get the latest single sample.
   */
  public getLatest(): IMUSample | null {
    return this.buffer.length > 0 ? this.buffer[this.buffer.length - 1] : null;
  }

  /**
   * Export bounded diagnostic snapshot (e.g. last 5-10 seconds) for developer inspection.
   */
  public exportDiagnosticSnapshot(durationSeconds: number = 5): {
    sample_count: number;
    duration_seconds: number;
    first_timestamp: string | null;
    last_timestamp: string | null;
    samples: IMUSample[];
  } {
    const targetCount = Math.min(this.buffer.length, Math.round(durationSeconds * IMU_CONFIG.TARGET_FREQUENCY_HZ));
    const samples = this.getRecent(targetCount);

    return {
      sample_count: samples.length,
      duration_seconds: durationSeconds,
      first_timestamp: samples.length > 0 ? samples[0].timestamp : null,
      last_timestamp: samples.length > 0 ? samples[samples.length - 1].timestamp : null,
      samples,
    };
  }

  /**
   * Current number of samples in the buffer.
   */
  public size(): number {
    return this.buffer.length;
  }

  /**
   * Maximum capacity.
   */
  public capacity(): number {
    return this.maxCapacity;
  }

  /**
   * Clear buffer contents.
   */
  public clear(): void {
    this.buffer = [];
  }
}
