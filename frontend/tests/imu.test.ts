/**
 * TourSafe IMU Sensor Test Suite
 * Comprehensive automated tests for pure math functions, timestamp synchronization,
 * quality calculations, interval jitter, gap detection, bounded buffer, and adapter lifecycle.
 */

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

// Pure math & kinematics
import {
  calculateAccelerationMagnitude,
  calculateAngularVelocityMagnitude,
  gToMps2,
  mps2ToG,
  calculateObservedFrequency,
  calculateIntervalStatistics,
} from "../lib/sensors/math";

// Synchronizer & Quality Engine
import { IMUSynchronizer } from "../lib/sensors/synchronizer";
import { IMUQualityEngine } from "../lib/sensors/quality";
import { BoundedIMUBuffer } from "../lib/sensors/buffer";
import { IMU_CONFIG } from "../lib/sensors/config";
import { IMUController } from "../lib/sensors/imuController";
import { AccelerometerAdapter } from "../lib/sensors/accelerometer";
import { GyroscopeAdapter } from "../lib/sensors/gyroscope";
import type { AccelerometerSample, GyroscopeSample, IMUSample } from "../types/imu";

describe("1. Kinematics Magnitude Calculations", () => {
  it("should calculate correct 3D Euclidean acceleration magnitude", () => {
    // Stationary flat on table: ax=0, ay=0, az=1.0g -> A_mag = 1.0g
    const mag1 = calculateAccelerationMagnitude(0, 0, 1.0);
    assert.equal(mag1, 1.0);

    // 3D vector: ax=3, ay=4, az=0 -> A_mag = 5.0
    const mag2 = calculateAccelerationMagnitude(3, 4, 0);
    assert.equal(mag2, 5.0);

    // Realistic walking sample: ax=0.03, ay=-0.04, az=0.98 -> A_mag = sqrt(0.0009+0.0016+0.9604) = 0.981275
    const mag3 = calculateAccelerationMagnitude(0.03, -0.04, 0.98);
    assert.ok(Math.abs(mag3 - 0.981275) < 1e-4);
  });

  it("should calculate correct 3D Euclidean angular velocity magnitude", () => {
    // Stationary: 0 rad/s
    const mag1 = calculateAngularVelocityMagnitude(0, 0, 0);
    assert.equal(mag1, 0.0);

    // Gyro rotation: gx=0.1, gy=-0.2, gz=0.2 -> G_mag = 0.3 rad/s
    const mag2 = calculateAngularVelocityMagnitude(0.1, -0.2, 0.2);
    assert.equal(mag2, 0.3);
  });

  it("should handle NaN or undefined inputs safely by returning 0", () => {
    assert.equal(calculateAccelerationMagnitude(NaN, 0, 1), 0);
    assert.equal(calculateAngularVelocityMagnitude(0, NaN, 0), 0);
  });

  it("should convert g to m/s^2 and vice versa accurately", () => {
    const mps2 = gToMps2(1.0);
    assert.equal(mps2, 9.80665);
    const g = mps2ToG(mps2);
    assert.equal(g, 1.0);
  });
});

describe("2. Sampling Frequency, Interval & Jitter Calculations", () => {
  it("should calculate accurate observed frequency from count and elapsed time", () => {
    // 50 samples in 1000 ms = 50.0 Hz
    const hz1 = calculateObservedFrequency(50, 1000);
    assert.equal(hz1, 50.0);

    // 100 samples in 2000 ms = 50.0 Hz
    const hz2 = calculateObservedFrequency(100, 2000);
    assert.equal(hz2, 50.0);

    // 25 samples in 1000 ms = 25.0 Hz
    const hz3 = calculateObservedFrequency(25, 1000);
    assert.equal(hz3, 25.0);

    // Zero cases
    assert.equal(calculateObservedFrequency(0, 1000), 0);
    assert.equal(calculateObservedFrequency(50, 0), 0);
  });

  it("should calculate accurate interval statistics and standard deviation jitter", () => {
    // Perfectly uniform 20 ms intervals
    const uniform = [20, 20, 20, 20, 20];
    const stats1 = calculateIntervalStatistics(uniform);
    assert.equal(stats1.averageIntervalMs, 20.0);
    assert.equal(stats1.minIntervalMs, 20.0);
    assert.equal(stats1.maxIntervalMs, 20.0);
    assert.equal(stats1.jitterMs, 0.0);

    // Variable intervals with jitter: [18, 22, 19, 21, 20]
    // mean = 20, deviations = [-2, 2, -1, 1, 0], variance = (4+4+1+1+0)/5 = 2.0, stdDev = sqrt(2) ≈ 1.41
    const variable = [18, 22, 19, 21, 20];
    const stats2 = calculateIntervalStatistics(variable);
    assert.equal(stats2.averageIntervalMs, 20.0);
    assert.equal(stats2.minIntervalMs, 18.0);
    assert.equal(stats2.maxIntervalMs, 22.0);
    assert.ok(Math.abs(stats2.jitterMs - 1.41) < 0.02);
  });
});

describe("3. Sensor Timestamp Synchronizer", () => {
  let synchronizer: IMUSynchronizer;
  let emittedSamples: IMUSample[] = [];

  beforeEach(() => {
    synchronizer = new IMUSynchronizer(IMU_CONFIG.SYNC_TOLERANCE_MS); // 25 ms tolerance
    emittedSamples = [];
    synchronizer.setCallback((sample) => emittedSamples.push(sample));
  });

  it("should successfully pair synchronous accelerometer and gyroscope samples", () => {
    const baseTime = 1000;

    const accel: AccelerometerSample = {
      x: 0.01,
      y: 0.02,
      z: 0.99,
      timestamp: new Date().toISOString(),
      monotonic_timestamp_ms: baseTime,
      sequence_number: 1,
      sensor_type: "accelerometer",
      session_id: "sess_sync_test",
    };

    const gyro: GyroscopeSample = {
      x: 0.005,
      y: -0.005,
      z: 0.001,
      timestamp: new Date().toISOString(),
      monotonic_timestamp_ms: baseTime + 3, // 3ms offset (within 25ms tolerance)
      sequence_number: 1,
      sensor_type: "gyroscope",
      session_id: "sess_sync_test",
    };

    synchronizer.pushAccelerometer(accel);
    assert.equal(emittedSamples.length, 0); // Waiting for gyro pair

    synchronizer.pushGyroscope(gyro);
    assert.equal(emittedSamples.length, 1); // Paired!

    const record = emittedSamples[0];
    assert.equal(record.session_id, "sess_sync_test");
    assert.equal(record.sequence_number, 1);
    assert.equal(record.accelerometer.z, 0.99);
    assert.equal(record.gyroscope.x, 0.005);
    assert.equal(record.quality.is_synchronized, true);
    assert.equal(record.quality.sensor_timestamp_delta_ms, 3.0);
    assert.ok(record.derived.acceleration_magnitude > 0.9);
  });

  it("should preserve monotonic sequence numbers across multiple paired samples", () => {
    for (let i = 1; i <= 5; i++) {
      const t = 1000 + i * 20;
      synchronizer.pushAccelerometer({
        x: 0,
        y: 0,
        z: 1,
        timestamp: new Date().toISOString(),
        monotonic_timestamp_ms: t,
        sequence_number: i,
        sensor_type: "accelerometer",
        session_id: "sess_seq_test",
      });
      synchronizer.pushGyroscope({
        x: 0,
        y: 0,
        z: 0,
        timestamp: new Date().toISOString(),
        monotonic_timestamp_ms: t + 1,
        sequence_number: i,
        sensor_type: "gyroscope",
        session_id: "sess_seq_test",
      });
    }

    assert.equal(emittedSamples.length, 5);
    for (let i = 0; i < 5; i++) {
      assert.equal(emittedSamples[i].sequence_number, i + 1);
    }
  });

  it("should prune orphaned samples exceeding synchronization tolerance without crashing", () => {
    // Push an accelerometer sample at t=1000
    synchronizer.pushAccelerometer({
      x: 0,
      y: 0,
      z: 1,
      timestamp: new Date().toISOString(),
      monotonic_timestamp_ms: 1000,
      sequence_number: 1,
      sensor_type: "accelerometer",
      session_id: "sess_timeout_test",
    });

    // Push a gyroscope sample at t=1100 (100ms later, exceeding 25ms tolerance)
    synchronizer.pushGyroscope({
      x: 0,
      y: 0,
      z: 0,
      timestamp: new Date().toISOString(),
      monotonic_timestamp_ms: 1100,
      sequence_number: 1,
      sensor_type: "gyroscope",
      session_id: "sess_timeout_test",
    });

    // Old orphaned accel at t=1000 should be pruned; gyro at 1100 remains buffered
    assert.equal(emittedSamples.length, 0);

    // Push matching accel at t=1102
    synchronizer.pushAccelerometer({
      x: 0.1,
      y: 0.2,
      z: 0.9,
      timestamp: new Date().toISOString(),
      monotonic_timestamp_ms: 1102,
      sequence_number: 2,
      sensor_type: "accelerometer",
      session_id: "sess_timeout_test",
    });

    // Now gyro 1100 and accel 1102 pair successfully (delta 2ms)
    assert.equal(emittedSamples.length, 1);
    assert.equal(emittedSamples[0].quality.sensor_timestamp_delta_ms, 2.0);
  });
});

describe("4. Sensor Quality Engine & Delivery Gap Detection", () => {
  it("should detect delivery gaps when interval exceeds 50 ms threshold", () => {
    const quality = new IMUQualityEngine();
    quality.setHardwareAvailability(true, true);

    const baseTime = 1000;

    // Normal samples at 20ms intervals
    for (let i = 0; i < 5; i++) {
      const t = baseTime + i * 20;
      quality.recordAccelerometerSample(t);
      quality.recordGyroscopeSample(t);
      quality.recordSynchronizedSample({
        sample_id: `s_${i}`,
        session_id: "sess_gap_test",
        timestamp: new Date().toISOString(),
        monotonic_timestamp_ms: t,
        sequence_number: i + 1,
        accelerometer: { x: 0, y: 0, z: 1 },
        gyroscope: { x: 0, y: 0, z: 0 },
        derived: { acceleration_magnitude: 1, angular_velocity_magnitude: 0 },
        quality: { sensor_timestamp_delta_ms: 0, is_synchronized: true, quality_state: "excellent" },
      });
    }

    let metrics = quality.getMetrics();
    assert.equal(metrics.sampleGapCount, 0);

    // Introduce a 80ms delivery stall (> 50ms threshold)
    const stallTime = baseTime + 4 * 20 + 80;
    quality.recordSynchronizedSample({
      sample_id: "s_gap",
      session_id: "sess_gap_test",
      timestamp: new Date().toISOString(),
      monotonic_timestamp_ms: stallTime,
      sequence_number: 6,
      accelerometer: { x: 0, y: 0, z: 1 },
      gyroscope: { x: 0, y: 0, z: 0 },
      derived: { acceleration_magnitude: 1, angular_velocity_magnitude: 0 },
      quality: { sensor_timestamp_delta_ms: 0, is_synchronized: true, quality_state: "excellent" },
    });

    metrics = quality.getMetrics();
    assert.equal(metrics.sampleGapCount, 1);
    assert.equal(metrics.largestGapMs, 80.0);
  });

  it("should evaluate quality state as 'unavailable' if hardware is not detected", () => {
    const quality = new IMUQualityEngine();
    quality.setHardwareAvailability(false, false);
    const metrics = quality.getMetrics();
    assert.equal(metrics.qualityState, "unavailable");
  });
});

describe("5. Bounded Sliding In-Memory Buffer", () => {
  it("should maintain max capacity and discard oldest samples in FIFO order", () => {
    const buffer = new BoundedIMUBuffer(5); // Capacity of 5
    assert.equal(buffer.capacity(), 5);
    assert.equal(buffer.size(), 0);

    for (let i = 1; i <= 8; i++) {
      buffer.push({
        sample_id: `sample_${i}`,
        session_id: "sess_buffer_test",
        timestamp: new Date().toISOString(),
        monotonic_timestamp_ms: 1000 + i * 20,
        sequence_number: i,
        accelerometer: { x: 0, y: 0, z: 1 },
        gyroscope: { x: 0, y: 0, z: 0 },
        derived: { acceleration_magnitude: 1, angular_velocity_magnitude: 0 },
        quality: { sensor_timestamp_delta_ms: 0, is_synchronized: true, quality_state: "excellent" },
      });
    }

    assert.equal(buffer.size(), 5);
    const recent = buffer.getRecent();
    assert.equal(recent.length, 5);
    // Oldest samples 1, 2, 3 were discarded; 4, 5, 6, 7, 8 remain
    assert.equal(recent[0].sequence_number, 4);
    assert.equal(recent[4].sequence_number, 8);
    assert.equal(buffer.getLatest()?.sequence_number, 8);
  });

  it("should export bounded diagnostic snapshot for inspection", () => {
    const buffer = new BoundedIMUBuffer(50);
    for (let i = 1; i <= 10; i++) {
      buffer.push({
        sample_id: `sample_${i}`,
        session_id: "sess_snapshot",
        timestamp: new Date().toISOString(),
        monotonic_timestamp_ms: 1000 + i * 20,
        sequence_number: i,
        accelerometer: { x: 0, y: 0, z: 1 },
        gyroscope: { x: 0, y: 0, z: 0 },
        derived: { acceleration_magnitude: 1, angular_velocity_magnitude: 0 },
        quality: { sensor_timestamp_delta_ms: 0, is_synchronized: true, quality_state: "excellent" },
      });
    }

    const snapshot = buffer.exportDiagnosticSnapshot(2);
    assert.equal(snapshot.sample_count, 10);
    assert.equal(snapshot.duration_seconds, 2);
    assert.ok(snapshot.first_timestamp);
    assert.ok(snapshot.last_timestamp);
  });
});

describe("6. Mock Adapter Boundary & IMU Controller Lifecycle", () => {
  class TestMockAccelerometerAdapter extends AccelerometerAdapter {
    private available = true;
    public startCalled = false;
    public stopCalled = false;

    constructor(available = true) {
      super();
      this.available = available;
    }

    public override async isAvailable(): Promise<boolean> {
      return this.available;
    }

    public override async start(
      sessionId: string,
      callback: (sample: AccelerometerSample) => void
    ): Promise<void> {
      if (!this.available) throw new Error("Hardware unavailable");
      this.startCalled = true;
    }

    public override stop(): void {
      this.stopCalled = true;
      this.startCalled = false;
    }
  }

  class TestMockGyroscopeAdapter extends GyroscopeAdapter {
    private available = true;
    public startCalled = false;
    public stopCalled = false;

    constructor(available = true) {
      super();
      this.available = available;
    }

    public override async isAvailable(): Promise<boolean> {
      return this.available;
    }

    public override async start(
      sessionId: string,
      callback: (sample: GyroscopeSample) => void
    ): Promise<void> {
      if (!this.available) throw new Error("Hardware unavailable");
      this.startCalled = true;
    }

    public override stop(): void {
      this.stopCalled = true;
      this.startCalled = false;
    }
  }

  it("should fail gracefully when physical hardware is unavailable", async () => {
    const mockAccel = new TestMockAccelerometerAdapter(false); // unavailable
    const mockGyro = new TestMockGyroscopeAdapter(true);

    const controller = new IMUController(
      mockAccel,
      mockGyro,
      new IMUSynchronizer(),
      new IMUQualityEngine(),
      new BoundedIMUBuffer()
    );

    await assert.rejects(
      async () => {
        await controller.start("test_session_unavailable");
      },
      {
        message: /Physical hardware sensor\(s\) unavailable/,
      }
    );
  });

  it("should successfully start and stop physical sensor adapters and prevent duplicate subscriptions", async () => {
    const mockAccel = new TestMockAccelerometerAdapter(true);
    const mockGyro = new TestMockGyroscopeAdapter(true);

    const controller = new IMUController(
      mockAccel,
      mockGyro,
      new IMUSynchronizer(),
      new IMUQualityEngine(),
      new BoundedIMUBuffer()
    );

    const session = await controller.start("test_session_1");
    assert.equal(session.session_id, "test_session_1");
    assert.equal(session.status, "active");
    assert.equal(mockAccel.startCalled, true);
    assert.equal(mockGyro.startCalled, true);

    // Call start again - duplicate must be safely ignored
    const duplicateSession = await controller.start("test_session_1");
    assert.equal(duplicateSession.session_id, "test_session_1");

    // Clean stop
    await controller.stop();
    assert.equal(mockAccel.stopCalled, true);
    assert.equal(mockGyro.stopCalled, true);
  });
});
