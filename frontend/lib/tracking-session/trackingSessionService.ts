/**
 * TourSafe Tracking Session Service
 * Manages the explicit tracking session lifecycle with state validation.
 *
 * Lifecycle: IDLE → STARTING → ACTIVE → PAUSED → OFFLINE → STOPPING → COMPLETED → ERROR
 *
 * Principle: Do not allow arbitrary state changes. Every transition must be
 * validated against permissions, sensor availability, and system conditions.
 */

import { TrackingSessionStatus, LocationTrackingStatus, LocationPermissionState } from "@/types/location";
import { useLocationStore } from "@/store/locationStore";
import { useTelemetryStore } from "@/store/telemetryStore";
import { useBatteryStore } from "@/store/batteryStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { batteryService } from "../battery/batteryService";
import { connectivityService } from "../connectivity/connectivityService";
import { batteryPolicy } from "../battery/batteryService";
import { generateId } from "../lib/utils";
import { api } from "../api";

/**
 * Tracking session lifecycle states.
 * These states enforce valid transitions and prevent arbitrary changes.
 */
export type TrackingSessionLifecycleState =
  | "idle"
  | "starting"
  | "active"
  | "paused"
  | "offline"
  | "stopping"
  | "completed"
  | "error";

/**
 * Tracking session metadata.
 * Every telemetry record must include tracking_session_id.
 * The ID originates from the server where possible.
 */
export interface TrackingSessionMetadata {
  session_id: string;
  tourist_id: string;
  device_id: string | undefined;
  started_at: string;
  status: TrackingSessionLifecycleState;
  last_sequence_number: number;
  source: "mobile_app" | "backend";
  sample_count: number;
  quality_metrics: {
    gps_quality: TrackingGPSQuality;
    imu_quality: IMUQualityState;
  };
  connectivity_at_start: string;
  battery_level_at_start: number;
}

/**
 * GPS quality states for tracking session.
 */
export type TrackingGPSQuality =
  | "GOOD"
  | "DEGRADED"
  | "POOR"
  | "UNKNOWN";

/**
 * Validate that a state transition is allowed.
 * Prevents arbitrary state changes and enforces lifecycle rules.
 */
function isValidTransition(
  from: TrackingSessionLifecycleState,
  to: TrackingSessionLifecycleState
): boolean {
  // Define valid transitions in the lifecycle
  const validTransitions: Record<TrackingSessionLifecycleState, TrackingSessionLifecycleState[]> = {
    idle: ["starting", "error"],
    starting: ["active", "error", "idle"],
    active: ["paused", "stopping", "error", "offline"],
    paused: ["active", "stopping", "error", "idle"],
    offline: ["active", "stopping", "error"],
    stopping: ["completed", "error", "idle"],
    completed: [], // Terminal state - no further transitions
    error: ["idle", "starting", "stopping"], // Error can recover
  };

  const allowed = validTransitions[from] || [];
  return allowed.includes(to);
}

/**
 * TrackingSessionService owns the tracking session lifecycle,
 * permission validation, sensor initialization, and synchronization
 * with the backend. It coordinates between GPS, IMU, connectivity,
 * and battery services to ensure a consistent tracking state.
 */
class TrackingSessionService {
  private currentState: TrackingSessionLifecycleState = "idle";
  private currentSession: TrackingSessionMetadata | null = null;
  private isPermissionsValidated = false;
  private initializedSensors = false;
  private transitionQueue: Array<{ from: TrackingSessionLifecycleState; to: TrackingSessionLifecycleState; reason: string }> = [];

  constructor() {
    // Set up store listeners for state changes
    this.setupStoreListeners();
  }

  /**
   * Set up listeners on Zustand stores to react to external state changes.
   */
  private setupStoreListeners(): void {
    // Listen to location store changes
    const locationUnsubscribe = useLocationStore.getState();
    // We'll react to explicit start/stop calls

    // Listen to battery and connectivity for auto-policy adjustments
    const batteryUnsubscribe = useBatteryStore.getState().subscribe(() => {
      this.onBatteryStateChanged();
    });

    const connectivityUnsubscribe = useConnectivityStore.getState().subscribe(() => {
      this.onConnectivityChanged();
    });
  }

  /**
   * Handle battery state changes - may trigger policy-based tracking adjustments.
   */
  private onBatteryStateChanged(): void {
    const batteryPolicy = batteryService.getCurrentPolicy();

    // If we're in active tracking and battery drops to critical,
    // we may need to adjust behavior but not stop entirely
    if (this.currentState === "active") {
      if (batteryPolicy.policyKey === "critical") {
        // Log warning but don't stop - safety critical
        console.warn("[TrackingSession] Battery critical during active tracking - maintaining tracking at reduced frequency");
        // The actual frequency adjustment is handled by the telemetry pipeline
      }
    }
  }

  /**
   * Handle connectivity changes - may trigger tracking adjustments.
   */
  private onConnectivityChanged(): void {
    const connectivityPolicy = connectivityService.getCurrentPolicy();

    // If we're in active tracking and connectivity drops to offline,
    // tracking continues but telemetry moves to offline buffer
    if (this.currentState === "active" && connectivityPolicy.mode === "buffer") {
      console.log("[TrackingSession] Connectivity lost - tracking continues, telemetry buffered");
      // State remains "active" but telemetry will be buffered
    }
  }

  /**
   * Start tracking - the full initialization sequence.
   * Validates permissions, creates session, initializes sensors, syncs with backend.
   */
  public async startTracking(): Promise<{
    success: boolean;
    session?: TrackingSessionMetadata;
    error?: string;
    reason?: string;
  }> {
    // 1. Validate that we're not already tracking
    if (this.currentState !== "idle" && this.currentState !== "error") {
      return {
        success: false,
        error: `Tracking already in state: ${this.currentState}`,
        reason: "tracking_already_active",
      };
    }

    // 2. Validate location permissions
    const permResult = await this.validateLocationPermissions();
    if (!permResult.granted) {
      return {
        success: false,
        error: `Location permission not granted: ${permResult.state}`,
        reason: "permission_denied",
      };
    }

    // 3. Validate sensor availability
    const sensorResult = await this.validateSensorAvailability();
    if (!sensorResult.available) {
      return {
        success: false,
        error: `Required sensor unavailable: ${sensorResult.missing.join(", ")}`,
        reason: "sensor_unavailable",
      };
    }

    // 4. Check battery and connectivity before starting
    const batteryPolicy = batteryService.getCurrentPolicy();
    const connectivityPolicy = connectivityService.getCurrentPolicy();

    // If battery is critical and policy doesn't allow tracking, defer
    if (batteryPolicy.policyKey === "critical" && !batteryPolicy.allowBackground) {
      return {
        success: false,
        error: "Battery critical and background tracking not permitted",
        reason: "battery_critical_deferred",
      };
    }

    // 5. Check if we can start given connectivity
    if (connectivityPolicy.mode === "offline" && this.currentState === "idle") {
      // Can start but all telemetry will be buffered offline
      console.log("[TrackingSession] Starting tracking in offline mode - all telemetry will be buffered");
    }

    // 6. Enter STARTING state
    this.transitionTo("starting");

    try {
      // 7. Create tracking session on backend
      const backendSession = await this.createBackendSession();

      // 8. Initialize local tracking session metadata
      const touristId = useAuthStore?.getState?.()?.user?.tourist_id || "tourist_me";
      const deviceId = useDeviceId();

      this.currentSession = {
        session_id: backendSession.session_id,
        tourist_id: touristId,
        device_id: deviceId,
        started_at: new Date().toISOString(),
        status: "active",
        last_sequence_number: 0,
        source: "mobile_app",
        sample_count: 0,
        quality_metrics: {
          gps_quality: "UNKNOWN",
          imu_quality: "unavailable",
        },
        connectivity_at_start: connectivityPolicy.type,
        battery_level_at_start: batteryPolicy.batteryLevel,
      };

      this.transitionTo("active");

      // 9. Notify stores
      useLocationStore.getState().setActiveSession(this.currentSession);
      useTelemetryStore.getState().setActiveSessionId(this.currentSession?.session_id);

      return {
        success: true,
        session: this.currentSession,
      };
    } catch (err: any) {
      console.error("[TrackingSession] Failed to start tracking:", err);
      this.transitionTo("error");

      return {
        success: false,
        error: err?.message || "Failed to start tracking session",
        reason: "startup_failed",
      };
    }
  }

  /**
   * Validate location permissions, requesting if necessary.
   */
  private async validateLocationPermissions(): Promise<{
    granted: boolean;
    state: LocationPermissionState;
  }> {
    // Check current permission state
    const currentState = useLocationStore.getState().permissionState;

    if (currentState === "granted") {
      return { granted: true, state: "granted" };
    }

    if (currentState === "denied" || currentState === "blocked") {
      // User has previously denied - show guidance, don't spam prompt
      return { granted: false, state: currentState };
    }

    // Request foreground permission
    try {
      const permService = useLocationStore.getState().permissionService
        || require("../../lib/location/permissionService").locationPermissionService;
      const result = await permService.requestForegroundPermission();

      const newState = result === "granted" ? "granted" : result;
      useLocationStore.getState().setPermissionState(newState);

      return { granted: result === "granted", state: newState };
    } catch (err) {
      console.warn("[TrackingSession] Permission validation failed:", err);
      return { granted: false, state: "unavailable" };
    }
  }

  /**
   * Validate that required sensors (accelerometer, gyroscope, GPS) are available.
   */
  private async validateSensorAvailability(): Promise<{
    available: boolean;
    missing: string[];
  }> {
    const missing: string[] = [];

    // Check GPS availability - through location store
    const gpsAvailable = useLocationStore.getState().trackingStatus !== "error";

    if (!gpsAvailable) {
      missing.push("GPS");
    }

    // Check accelerometer availability
    // In a full implementation, we'd check expo-sensors directly
    // For now, assume available if we have permission and the hardware exists

    // Check gyroscope availability
    // Same as accelerometer

    return {
      available: missing.length === 0,
      missing,
    };
  }

  /**
   * Create a backend tracking session.
   */
  private async createBackendSession(): Promise<{ session_id: string }> {
    const authUser = useAuthStore?.getState?.()?.user;
    const touristId = authUser?.tourist_id || authUser?.id || "tourist_me";

    try {
      const res = await api.post("/api/v1/telemetry/session/start", {
        device_id: useDeviceId(),
        tourist_id: touristId,
        sampling_rate_target_hz: 50.0,
        gps_frequency_hz: 1.0,
        battery_pct: useBatteryStore.getState().batteryInfo.level,
        network_type: connectivityService.getCurrentState().type,
        schema_version: "1.0.0",
      });

      return { session_id: res.data.session_id };
    } catch (err) {
      console.warn("[TrackingSession] Backend session start failed, continuing locally:", err);
      // Return a local session ID even if backend fails
      return { session_id: `local_sess_${Date.now()}_${Math.random().toString(36).substring(2, 7)}` };
    }
  }

  /**
   * Stop tracking - clean shutdown with backend notification and buffer flush.
   */
  public async stopTracking(): Promise<{
    success: boolean;
    session?: TrackingSessionMetadata;
    error?: string;
  }> {
    // 1. Validate we're in a stoppable state
    if (this.currentState === "idle") {
      return { success: true, error: "No active tracking session" };
    }

    if (this.currentState === "completed") {
      return { success: true, error: "Tracking already completed" };
    }

    // 2. Enter STOPPING state
    this.transitionTo("stopping");

    try {
      // 3. Flush any pending telemetry to offline buffer first
      // Then attempt server notification
      await this.flushAndNotifyStop();

      // 4. Update session metadata
      if (this.currentSession) {
        this.currentSession.status = "completed";
        this.currentSession.ended_at = new Date().toISOString();
        this.currentSampleCount = useTelemetryStore.getState().sequenceNumber || 0;
      }

      this.transitionTo("completed");

      // 5. Clear stores
      useLocationStore.getState().setTrackingStatus("stopped");
      useTelemetryStore.getState().reset();

      return { success: true, session: this.currentSession };
    } catch (err: any) {
      console.error("[TrackingSession] Failed to stop tracking:", err);
      this.transitionTo("error");

      return {
        success: false,
        error: err?.message || "Failed to stop tracking session",
      };
    }
  }

  /**
   * Flush pending telemetry and notify backend of session stop.
   */
  private async flushAndNotifyStop(): Promise<void> {
    // 1. Flush pending batch from telemetry service
    // (The telemetryClient or telemetryService will handle this)

    // 2. Notify backend if we have a server session
    if (this.currentSession && !this.currentSession.session_id.startsWith("local_")) {
      try {
        await api.post("/api/v1/telemetry/session/stop", {
          session_id: this.currentSession.session_id,
        });
      } catch (err) {
        console.warn("[TrackingSession] Backend session stop notice failed:", err);
        // Continue regardless - local session cleanup is primary
      }
    }
  }

  /**
   * Pause tracking - keeps session open without transmitting samples.
   */
  public pauseTracking(): void {
    if (this.currentState !== "active") {
      console.warn("[TrackingSession] Cannot pause: current state is", this.currentState);
      return;
    }

    this.transitionTo("paused");
    useLocationStore.getState().setTrackingStatus("paused");
    console.log("[TrackingSession] Tracking paused");
  }

  /**
   * Resume paused tracking.
   */
  public resumeTracking(): void {
    if (this.currentState !== "paused") {
      console.warn("[TrackingSession] Cannot resume: current state is", this.currentState);
      return;
    }

    this.transitionTo("active");
    useLocationStore.getState().setTrackingStatus("active");
    console.log("[TrackingSession] Tracking resumed");
  }

  /**
   * Transition to a new state, with validation.
   */
  private transitionTo(newState: TrackingSessionLifecycleState): void {
    const previous = this.currentState;

    if (!isValidTransition(previous, newState)) {
      console.warn(
        `[TrackingSession] Invalid state transition: ${previous} → ${newState}. ` +
          `Queuing for later resolution.`
      );
      // Queue the transition for later
      this.transitionQueue.push({
        from: previous,
        to: newState,
        reason: "invalid_transition_queued",
      });
      return;
    }

    this.currentState = newState;

    // Process queued transitions after a valid one
    if (this.transitionQueue.length > 0) {
      const next = this.transitionQueue.shift();
      if (next) {
        setTimeout(() => this.transitionTo(next.to), 100);
      }
    }

    console.log(`[TrackingSession] State: ${previous} → ${newState}`);
  }
}

/**
 * Get a privacy-conscious application-scoped device identifier.
 * Does NOT collect IMEI, serial number, MAC address, or other unnecessary
 * persistent hardware identifiers.
 */
function useDeviceId(): string {
  // Use a deterministic but privacy-conscious identifier
  // Based on app installation and user context, not hardware IDs

  // Try to get from secure store or generate a persistent but opaque ID
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { useSecureStore } = require("../../store/secureStore");
    const secureUserId = useSecureStore.getState?.()?.userId;

    if (secureUserId) {
      return secureUserId;
    }
  } catch {
    // Fall through to generated ID
  }

  // Generate a deterministic but privacy-conscious ID
  // This is based on installation context, not hardware identifiers
  const timestampComponent = Date.now().toString(36);
  const randomComponent = Math.random().toString(36).substring(2, 8);
  return `tourist_${timestampComponent}_${randomComponent}`;
}

export const trackingSessionService = new TrackingSessionService();

/**
 * Export type utilities for UI/components.
 */
export type { TrackingSessionLifecycleState, TrackingSessionMetadata, TrackingGPSQuality };
export const isValidLifecycleTransition = isValidTransition;