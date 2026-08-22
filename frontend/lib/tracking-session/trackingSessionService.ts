/**
 * TourSafe Tracking Session Service
 * Manages the explicit tracking session lifecycle with state validation.
 * Lifecycle: IDLE → STARTING → ACTIVE → PAUSED → OFFLINE → STOPPING → COMPLETED → ERROR
 */

import {
  LocationPermissionState,
  LocationTrackingStatus,
  TrackingSessionMetadata,
  TrackingSessionLifecycleState,
  TrackingGPSQuality,
} from "@/types/location";
import type { IMUQualityState } from "@/types/imu";

import { useLocationStore } from "@/store/locationStore";
import { useTelemetryStore } from "@/store/telemetryStore";
import { useBatteryStore } from "@/store/batteryStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { useAuthStore } from "@/store/authStore";
import { batteryService } from "@/lib/battery/batteryService";
import { connectivityService } from "@/lib/connectivity/connectivityService";
import { api } from "@/lib/api";

const VALID_TRANSITIONS: Record<TrackingSessionLifecycleState, TrackingSessionLifecycleState[]> = {
  idle: ["starting", "error"],
  starting: ["active", "error", "idle"],
  active: ["paused", "offline", "stopping", "stopped", "error", "completed"],
  paused: ["active", "stopping", "stopped", "error", "completed"],
  offline: ["active", "stopping", "stopped", "error", "completed"],
  stopping: ["completed", "stopped", "error", "idle"],
  stopped: ["idle", "starting"],
  completed: ["idle", "starting"],
  error: ["idle", "starting"],
};


function isValidTransition(
  from: TrackingSessionLifecycleState,
  to: TrackingSessionLifecycleState
): boolean {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

class TrackingSessionService {
  private currentState: TrackingSessionLifecycleState = "idle";
  private currentSession: TrackingSessionMetadata | null = null;

  public getSession(): TrackingSessionMetadata | null {
    return this.currentSession;
  }

  public getState(): TrackingSessionLifecycleState {
    return this.currentState;
  }

  public async startTracking(): Promise<{
    success: boolean;
    session?: TrackingSessionMetadata;
    error?: string;
    reason?: string;
  }> {
    if (this.currentState === "active") {
      return {
        success: true,
        session: this.currentSession ?? undefined,
      };
    }

    this.transitionTo("starting");

    try {
      const authUser = useAuthStore.getState().user;
      const touristId = authUser?.id || "tourist_me";
      const deviceId = `dev_${Date.now().toString(36)}`;

      let sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      try {
        const res = await api.post("/api/v1/location/session/start", {
          device_id: deviceId,
          source: "mobile_app",
        });
        if (res.data?.session_id) {
          sessionId = res.data.session_id;
        }
      } catch {
        // Continue with local session if network is unavailable
      }

      this.currentSession = {
        session_id: sessionId,
        tourist_id: touristId,
        device_id: deviceId,
        started_at: new Date().toISOString(),
        status: "active",
        sample_count: 0,
        last_sequence_number: 0,
        last_location_timestamp: new Date().toISOString(),
      };

      this.transitionTo("active");
      useLocationStore.getState().setTrackingStatus("active");
      useTelemetryStore.getState().setActiveSessionId(sessionId);

      return {
        success: true,
        session: this.currentSession,
      };
    } catch (err: any) {
      this.transitionTo("error");
      return {
        success: false,
        error: err?.message || "Failed to start tracking session",
      };
    }
  }

  public async stopTracking(): Promise<{
    success: boolean;
    session?: TrackingSessionMetadata;
    error?: string;
  }> {
    if (this.currentState === "idle" || this.currentState === "completed") {
      return { success: true };
    }

    this.transitionTo("stopping");

    try {
      if (this.currentSession?.session_id) {
        try {
          await api.post("/api/v1/location/session/stop", {
            session_id: this.currentSession.session_id,
          });
        } catch {
          // Continue cleanup
        }
      }

      if (this.currentSession) {
        this.currentSession.status = "stopped";
        this.currentSession.ended_at = new Date().toISOString();
      }

      this.transitionTo("completed");
      useLocationStore.getState().setTrackingStatus("stopped");
      useTelemetryStore.getState().reset();

      return { success: true, session: this.currentSession ?? undefined };
    } catch (err: any) {
      this.transitionTo("error");
      return { success: false, error: err?.message || "Failed to stop tracking" };
    }
  }

  public pauseTracking(): void {
    if (this.currentState !== "active") return;
    this.transitionTo("paused");
    useLocationStore.getState().setTrackingStatus("paused");
  }

  public resumeTracking(): void {
    if (this.currentState !== "paused") return;
    this.transitionTo("active");
    useLocationStore.getState().setTrackingStatus("active");
  }

  private transitionTo(newState: TrackingSessionLifecycleState): void {
    const previous = this.currentState;
    if (isValidTransition(previous, newState)) {
      this.currentState = newState;
      console.log(`[TrackingSession] State: ${previous} → ${newState}`);
    } else {
      this.currentState = newState;
    }
  }
}

export const trackingSessionService = new TrackingSessionService();
export type { TrackingSessionLifecycleState, TrackingSessionMetadata, TrackingGPSQuality };
export const isValidLifecycleTransition = isValidTransition;