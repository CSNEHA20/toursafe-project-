/**
 * TourSafe Telemetry Processing & Ingestion Pipeline Tests
 * Tests telemetry frame serialization, anomaly vector calculations,
 * and high-frequency sliding window evaluation.
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  calculateAccelerationMagnitude,
  calculateAngularVelocityMagnitude,
  calculateObservedFrequency,
  calculateIntervalStatistics,
  gToMps2,
  mps2ToG,
} from "../lib/sensors/math";
import { BoundedIMUBuffer } from "../lib/sensors/buffer";

describe("1. High-Frequency Kinematic Calculations", () => {
  it("should calculate correct acceleration vector magnitude in 3D", () => {
    const mag = calculateAccelerationMagnitude(0.0, 0.0, 1.0);
    assert.equal(mag, 1.0);

    const fallImpactMag = calculateAccelerationMagnitude(2.5, 3.1, 4.2);
    const expected = Math.sqrt(2.5 ** 2 + 3.1 ** 2 + 4.2 ** 2);
    assert.ok(Math.abs(fallImpactMag - expected) < 1e-5);
  });

  it("should calculate correct rotational velocity magnitude in 3D", () => {
    const gyroMag = calculateAngularVelocityMagnitude(0.2, 0.4, 0.4);
    assert.ok(Math.abs(gyroMag - 0.6) < 1e-5);
  });

  it("should convert g to m/s^2 with standard gravity constant", () => {
    assert.equal(gToMps2(1.0), 9.80665);
    assert.equal(mps2ToG(9.80665), 1.0);
  });
});

describe("2. Sampling Interval Statistics & Jitter Evaluation", () => {
  it("should calculate accurate observed frequency", () => {
    const hz50 = calculateObservedFrequency(50, 1000);
    assert.equal(hz50, 50.0);

    const hz100 = calculateObservedFrequency(100, 1000);
    assert.equal(hz100, 100.0);
  });

  it("should compute mean, min, max, and jitter standard deviation", () => {
    const intervals = [20, 20, 20, 20, 20];
    const stats = calculateIntervalStatistics(intervals);
    assert.equal(stats.averageIntervalMs, 20.0);
    assert.equal(stats.minIntervalMs, 20.0);
    assert.equal(stats.maxIntervalMs, 20.0);
    assert.equal(stats.jitterMs, 0.0);
  });
});

describe("3. Bounded Sliding Window FIFO Buffer", () => {
  it("should maintain max capacity and discard oldest samples", () => {
    const buffer = new BoundedIMUBuffer(3);
    assert.equal(buffer.capacity(), 3);

    for (let i = 1; i <= 5; i++) {
      buffer.push({
        sample_id: `s_${i}`,
        session_id: "sess_test",
        timestamp: new Date().toISOString(),
        monotonic_timestamp_ms: 1000 + i * 20,
        sequence_number: i,
        accelerometer: { x: 0, y: 0, z: 1 },
        gyroscope: { x: 0, y: 0, z: 0 },
        derived: { acceleration_magnitude: 1, angular_velocity_magnitude: 0 },
        quality: { sensor_timestamp_delta_ms: 0, is_synchronized: true, quality_state: "excellent" },
      });
    }

    assert.equal(buffer.size(), 3);
    const recent = buffer.getRecent();
    assert.equal(recent[0].sequence_number, 3);
    assert.equal(recent[2].sequence_number, 5);
  });
});
