/**
 * TourSafe Unified IMU Controller
 * Orchestrates physical Accelerometer and Gyroscope hardware subscriptions,
 * timestamp synchronization, quality assessment, bounded buffering, and lifecycle.
 * Prevents duplicate hardware subscriptions and ensures complete resource cleanup.
 */

import { AccelerometerAdapter, accelerometerAdapter } from "./accelerometer";
import { GyroscopeAdapter, gyroscopeAdapter } from "./gyroscope";
import { IMUSynchronizer } from "./synchronizer";
import { IMUQualityEngine } from "./quality";
import { BoundedIMUBuffer } from "./buffer";
import { useIMUStore } from "../../store/imuStore";
import type {
  IMUSample,
  IMUSession,
  IMUTrackingStatus,
  IMUQualityMetrics,
} from "../../types/imu";

export class IMUController {
  private accelAdapter: AccelerometerAdapter;
  private gyroAdapter: GyroscopeAdapter;
  private synchronizer: IMUSynchronizer;
  private qualityEngine: IMUQualityEngine;
  private buffer: BoundedIMUBuffer;

  private currentSessionId: string | null = null;
  private isPaused = false;
  private isRunning = false;
  private metricsTimer: ReturnType<typeof setInterval> | null = null;
  private sampleThrottleTimer: number = 0;

  // Realtime transmission configuration
  private enableRealtimeStreaming = false;

  constructor(
    accel: AccelerometerAdapter = accelerometerAdapter,
    gyro: GyroscopeAdapter = gyroscopeAdapter,
    synchronizer: IMUSynchronizer = new IMUSynchronizer(),
    qualityEngine: IMUQualityEngine = new IMUQualityEngine(),
    buffer: BoundedIMUBuffer = new BoundedIMUBuffer()
  ) {
    this.accelAdapter = accel;
    this.gyroAdapter = gyro;
    this.synchronizer = synchronizer;
    this.qualityEngine = qualityEngine;
    this.buffer = buffer;

    // Connect synchronizer to receiver pipeline
    this.synchronizer.setCallback((sample) => this.handleSynchronizedSample(sample));
  }

  public getStatus(): IMUTrackingStatus {
    try {
      return useIMUStore.getState().imuStatus;
    } catch {
      return this.isRunning ? (this.isPaused ? "paused" : "active") : "idle";
    }
  }

  public getBuffer(): BoundedIMUBuffer {
    return this.buffer;
  }

  public getQualityMetrics(): IMUQualityMetrics {
    return this.qualityEngine.getMetrics();
  }

  public setRealtimeStreaming(enabled: boolean): void {
    this.enableRealtimeStreaming = enabled;
  }

  /**
   * Check physical sensor hardware availability on this device.
   */
  public async checkAvailability(): Promise<{
    accelerometer: boolean;
    gyroscope: boolean;
    available: boolean;
  }> {
    const [accelAvailable, gyroAvailable] = await Promise.all([
      this.accelAdapter.isAvailable(),
      this.gyroAdapter.isAvailable(),
    ]);

    try {
      const store = useIMUStore.getState();
      store.setAccelerometerStatus(accelAvailable ? "available" : "unavailable");
      store.setGyroscopeStatus(gyroAvailable ? "available" : "unavailable");
    } catch {}

    this.qualityEngine.setHardwareAvailability(accelAvailable, gyroAvailable);

    return {
      accelerometer: accelAvailable,
      gyroscope: gyroAvailable,
      available: accelAvailable && gyroAvailable,
    };
  }

  /**
   * Start 50 Hz IMU sensor acquisition.
   * Prevents duplicate subscriptions if already running.
   */
  public async start(providedSessionId?: string): Promise<IMUSession> {
    // Guard: Prevent duplicate start calls
    if (this.isRunning) {
      console.warn("[IMUController] IMU acquisition already active. Ignoring duplicate start call.");
      try {
        const existing = useIMUStore.getState().activeSession;
        if (existing) return existing;
      } catch {}
    }

    try {
      const store = useIMUStore.getState();
      store.setIMUStatus("starting");
      store.setIMUError(null);
    } catch {}

    // 1. Verify physical hardware availability
    const { accelerometer, gyroscope, available } = await this.checkAvailability();
    if (!available) {
      const missing = [];
      if (!accelerometer) missing.push("Accelerometer");
      if (!gyroscope) missing.push("Gyroscope");
      const errMsg = `Physical hardware sensor(s) unavailable: ${missing.join(", ")}`;
      try {
        const store = useIMUStore.getState();
        store.setIMUStatus("error");
        store.setIMUError(errMsg);
      } catch {}
      throw new Error(errMsg);
    }

    // 2. Initialize or reuse session
    let touristId = "tourist_me";
    try {
      // Dynamic import or check for authStore in React Native runtime
      const { useAuthStore } = require("../../store/authStore");
      const authUser = useAuthStore.getState?.()?.user;
      if (authUser) touristId = authUser.tourist_id || authUser.id || touristId;
    } catch {
      // Fallback in headless test environments
    }

    const sessionId = providedSessionId || `imu_sess_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    this.currentSessionId = sessionId;
    this.isPaused = false;
    this.isRunning = true;

    // Reset pipeline components
    this.synchronizer.reset();
    this.qualityEngine.reset();
    this.qualityEngine.setHardwareAvailability(true, true);
    this.buffer.clear();

    const session: IMUSession = {
      session_id: sessionId,
      tourist_id: touristId,
      started_at: new Date().toISOString(),
      status: "active",
      imu_enabled: true,
      accelerometer_enabled: true,
      gyroscope_enabled: true,
      last_sequence_number: 0,
      observed_frequency: 0,
      quality_state: "good",
    };

    try {
      const store = useIMUStore.getState();
      store.setActiveSession(session);
    } catch {}

    // 3. Start physical Accelerometer and Gyroscope subscriptions
    try {
      await Promise.all([
        this.accelAdapter.start(
          sessionId,
          (accelSample) => {
            if (!this.isPaused) {
              this.qualityEngine.recordAccelerometerSample(accelSample.monotonic_timestamp_ms);
              this.synchronizer.pushAccelerometer(accelSample);
            }
          },
          { touristId }
        ),
        this.gyroAdapter.start(
          sessionId,
          (gyroSample) => {
            if (!this.isPaused) {
              this.qualityEngine.recordGyroscopeSample(gyroSample.monotonic_timestamp_ms);
              this.synchronizer.pushGyroscope(gyroSample);
            }
          },
          { touristId }
        ),
      ]);

      try {
        const store = useIMUStore.getState();
        store.setIMUStatus("active");
        store.setAccelerometerStatus("active");
        store.setGyroscopeStatus("active");
      } catch {}

      this.startMetricsMonitor();
      return session;
    } catch (err: any) {
      console.error("[IMUController] Failed to activate sensor subscriptions:", err);
      this.stop();
      try {
        const store = useIMUStore.getState();
        store.setIMUStatus("error");
        store.setIMUError(err?.message || "Failed to start hardware sensors");
      } catch {}
      throw err;
    }
  }

  /**
   * Cleanly stop all hardware subscriptions and flush pending state.
   */
  public async stop(): Promise<void> {
    this.isRunning = false;
    this.isPaused = false;

    if (this.metricsTimer) {
      clearInterval(this.metricsTimer);
      this.metricsTimer = null;
    }

    this.accelAdapter.stop();
    this.gyroAdapter.stop();
    this.synchronizer.reset();

    try {
      const store = useIMUStore.getState();
      store.setIMUStatus("stopped");
      store.setAccelerometerStatus("available");
      store.setGyroscopeStatus("available");

      if (store.activeSession) {
        store.setActiveSession({
          ...store.activeSession,
          status: "stopped",
          ended_at: new Date().toISOString(),
        });
      }
    } catch {}

    this.currentSessionId = null;
  }

  /**
   * Pause sensor processing without tearing down subscriptions.
   */
  public pause(): void {
    this.isPaused = true;
    try {
      useIMUStore.getState().setIMUStatus("paused");
    } catch {}
  }

  /**
   * Resume paused sensor processing.
   */
  public resume(): void {
    this.isPaused = false;
    try {
      useIMUStore.getState().setIMUStatus("active");
    } catch {}
  }

  /**
   * Export bounded diagnostic snapshot (e.g. last 5-10s).
   */
  public exportDiagnosticSnapshot(durationSeconds: number = 5) {
    return this.buffer.exportDiagnosticSnapshot(durationSeconds);
  }

  /**
   * Process a valid synchronized IMU record.
   */
  private handleSynchronizedSample(sample: IMUSample): void {
    // 1. Push to bounded local in-memory buffer
    this.buffer.push(sample);

    // 2. Record in quality engine
    const metrics = this.qualityEngine.recordSynchronizedSample(sample);

    // 3. Update Zustand store (throttled to ~10 Hz to prevent UI overload from 50 Hz updates)
    const now = Date.now();
    if (now - this.sampleThrottleTimer >= 100) {
      this.sampleThrottleTimer = now;
      try {
        const store = useIMUStore.getState();
        store.setLatestIMUSample(sample);
        store.setQualityMetrics(metrics);
      } catch {}
    }

    // 4. Send via Realtime WebSocket if streaming enabled
    if (this.enableRealtimeStreaming) {
      try {
        const { realtimeClient } = require("../../lib/realtimeClient");
        if (realtimeClient && realtimeClient.getConnectionState() === "connected") {
          realtimeClient.send("telemetry.imu", {
            sample,
            session_id: sample.session_id,
            sequence_number: sample.sequence_number,
          });
        }
      } catch (err) {
        console.debug("[IMUController] Realtime send note:", err);
      }
    }
  }

  private startMetricsMonitor(): void {
    if (this.metricsTimer) clearInterval(this.metricsTimer);
    this.metricsTimer = setInterval(() => {
      try {
        const store = useIMUStore.getState();
        if (store.imuStatus === "active") {
          const metrics = this.qualityEngine.getMetrics();
          store.setQualityMetrics(metrics);
        }
      } catch {}
    }, 1000);
  }
}

export const imuController = new IMUController();
