/**
 * TourSafe IMU Pure Math and Derived Kinematics Functions
 * Pure, deterministic mathematical calculations for magnitude, timing, and jitter.
 */

import { IMU_CONFIG } from "./config";

/**
 * Calculate Euclidean acceleration magnitude:
 * A_mag = sqrt(ax² + ay² + az²)
 * Preserves original raw channels while providing scalar magnitude.
 *
 * @param x Acceleration X in g
 * @param y Acceleration Y in g
 * @param z Acceleration Z in g
 * @returns Scalar acceleration magnitude in g
 */
export function calculateAccelerationMagnitude(
  x: number,
  y: number,
  z: number
): number {
  if (isNaN(x) || isNaN(y) || isNaN(z)) return 0;
  const mag = Math.sqrt(x * x + y * y + z * z);
  return Number(mag.toFixed(6));
}

/**
 * Calculate Euclidean angular velocity magnitude:
 * G_mag = sqrt(gx² + gy² + gz²)
 * Preserves original raw channels while providing scalar magnitude.
 *
 * @param x Angular velocity around X in rad/s
 * @param y Angular velocity around Y in rad/s
 * @param z Angular velocity around Z in rad/s
 * @returns Scalar angular velocity magnitude in rad/s
 */
export function calculateAngularVelocityMagnitude(
  x: number,
  y: number,
  z: number
): number {
  if (isNaN(x) || isNaN(y) || isNaN(z)) return 0;
  const mag = Math.sqrt(x * x + y * y + z * z);
  return Number(mag.toFixed(6));
}

/**
 * Convert acceleration from 'g' to standard SI meters per second squared (m/s^2).
 * 1 g ≈ 9.80665 m/s^2
 */
export function gToMps2(g: number): number {
  return Number((g * IMU_CONFIG.GRAVITY_EARTH_MPS2).toFixed(6));
}

/**
 * Convert acceleration from SI m/s^2 to 'g'.
 */
export function mps2ToG(mps2: number): number {
  return Number((mps2 / IMU_CONFIG.GRAVITY_EARTH_MPS2).toFixed(6));
}

/**
 * High-precision monotonic timer in milliseconds.
 * Uses global performance.now() if available, fallback to Date.now().
 */
export function getMonotonicTimeMs(): number {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }
  return Date.now();
}

/**
 * Compute sample frequency: sample_count / elapsed_time_seconds
 */
export function calculateObservedFrequency(
  sampleCount: number,
  elapsedMs: number
): number {
  if (sampleCount <= 0 || elapsedMs <= 0) return 0;
  const elapsedSeconds = elapsedMs / 1000;
  const hz = sampleCount / elapsedSeconds;
  return Number(hz.toFixed(2));
}

/**
 * Compute sample interval statistics (average, min, max, jitter).
 */
export function calculateIntervalStatistics(intervals: number[]): {
  averageIntervalMs: number;
  minIntervalMs: number;
  maxIntervalMs: number;
  jitterMs: number;
} {
  if (!intervals || intervals.length === 0) {
    return {
      averageIntervalMs: 0,
      minIntervalMs: 0,
      maxIntervalMs: 0,
      jitterMs: 0,
    };
  }

  const sum = intervals.reduce((acc, val) => acc + val, 0);
  const avg = sum / intervals.length;
  let min = intervals[0];
  let max = intervals[0];

  for (let i = 1; i < intervals.length; i++) {
    if (intervals[i] < min) min = intervals[i];
    if (intervals[i] > max) max = intervals[i];
  }

  // Calculate population standard deviation for jitter
  const variance =
    intervals.reduce((acc, val) => acc + Math.pow(val - avg, 2), 0) /
    intervals.length;
  const jitter = Math.sqrt(variance);

  return {
    averageIntervalMs: Number(avg.toFixed(2)),
    minIntervalMs: Number(min.toFixed(2)),
    maxIntervalMs: Number(max.toFixed(2)),
    jitterMs: Number(jitter.toFixed(2)),
  };
}
