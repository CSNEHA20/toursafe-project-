/**
 * TourSafe Location Tracking Service
 * Owns Expo Location hardware subscriptions, coordinate normalization, validation, sequence monotonicity,
 * quality calculations, and transmission to TourSafe backend.
 */

import { Platform } from "react-native";
import * as Location from "expo-location";
import { locationApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useLocationStore } from "@/store/locationStore";
import { locationPermissionService } from "./permissionService";
import { QualityCalculator } from "./qualityCalculator";
import {
  registerBackgroundUpdateCallback,
  TOURSAFE_BACKGROUND_LOCATION_TASK,
} from "./backgroundTask";
import type {
  LocationPermissionState,
  LocationSample,
  LocationTrackingStatus,
  TrackingSession,
} from "@/types/location";

class LocationTrackingService {
  private subscription: Location.LocationSubscription | null = null;
  private qualityCalc = new QualityCalculator();
  private sequenceNumber = 0;
  private currentSessionId: string | null = null;
  private isPaused = false;
  private syncTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    // Connect background callback
    registerBackgroundUpdateCallback((samples) => {
      samples.forEach((s) => this.processLocationFix(s, true));
    });
  }

  public getTrackingStatus(): LocationTrackingStatus {
    return useLocationStore.getState().trackingStatus;
  }

  /**
   * Request foreground and background location permissions.
   */
  public async requestLocationPermissions(): Promise<LocationPermissionState> {
    const permState = await locationPermissionService.requestForegroundPermission();
    useLocationStore.getState().setPermissionState(permState);
    return permState;
  }

  /**
   * One-off physical device GPS fix.
   */
  public async getCurrentLocation(): Promise<LocationSample | null> {
    const perm = await this.requestLocationPermissions();
    if (perm !== "granted") {
      throw new Error(`Location permission not granted (${perm})`);
    }

    try {
      const fix = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      const sample: LocationSample = {
        session_id: this.currentSessionId || `oneshot_${Date.now()}`,
        timestamp: new Date(fix.timestamp).toISOString(),
        latitude: fix.coords.latitude,
        longitude: fix.coords.longitude,
        altitude: fix.coords.altitude,
        accuracy: fix.coords.accuracy,
        speed: fix.coords.speed,
        heading: fix.coords.heading,
        provider: "gps",
        is_background: false,
        sequence_number: ++this.sequenceNumber,
        network_status: "online",
      };

      if (this.validateSample(sample)) {
        useLocationStore.getState().setCurrentLocation(sample);
        return sample;
      }
      return null;
    } catch (err: any) {
      console.error("[TrackingService] Failed to get one-shot location:", err);
      throw err;
    }
  }

  /**
   * Start continuous foreground location tracking (~1 GPS update / second).
   */
  public async startForegroundLocationTracking(): Promise<TrackingSession> {
    const store = useLocationStore.getState();
    if (this.subscription && store.trackingStatus === "active") {
      console.warn("[TrackingService] Tracking already active. Ignoring duplicate start.");
      return store.activeSession!;
    }

    // 1. Verify permissions
    const perm = await this.requestLocationPermissions();
    if (perm !== "granted") {
      store.setTrackingStatus("error");
      store.setLastServerError(`Location permission denied: ${perm}`);
      throw new Error(`Cannot start tracking: Location permission ${perm}`);
    }

    store.setTrackingStatus("starting");
    this.isPaused = false;
    this.sequenceNumber = 0;
    this.qualityCalc.reset();

    // 2. Initialize tracking session on backend
    const authUser = useAuthStore.getState().user;
    const touristId = authUser?.tourist_id || authUser?.id || "tourist_me";
    const sessionId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    this.currentSessionId = sessionId;

    const newSession: TrackingSession = {
      session_id: sessionId,
      tourist_id: touristId,
      started_at: new Date().toISOString(),
      status: "active",
      last_sequence_number: 0,
      source: "mobile_app",
      sample_count: 0,
    };

    store.setActiveSession(newSession);

    // Call backend startSession in background
    locationApi.startSession({ source: "mobile_app" }).catch((e) => {
      console.debug("[TrackingService] Backend session start notice:", e?.message);
    });

    // 3. Start Expo Location watchPositionAsync
    try {
      this.subscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.High,
          timeInterval: 1000,     // 1000ms target (1 Hz)
          distanceInterval: 1,    // 1 meter movement threshold
        },
        (loc) => {
          if (!this.isPaused) {
            const rawSample: LocationSample = {
              session_id: this.currentSessionId || sessionId,
              timestamp: new Date(loc.timestamp).toISOString(),
              latitude: loc.coords.latitude,
              longitude: loc.coords.longitude,
              altitude: loc.coords.altitude,
              accuracy: loc.coords.accuracy,
              speed: loc.coords.speed,
              heading: loc.coords.heading,
              provider: "gps",
              is_background: false,
              sequence_number: ++this.sequenceNumber,
              network_status: "online",
            };
            this.processLocationFix(rawSample, false);
          }
        }
      );

      store.setTrackingStatus("active");
      this.startStalenessMonitor();
      return newSession;
    } catch (err: any) {
      console.error("[TrackingService] Failed to start watchPositionAsync:", err);
      store.setTrackingStatus("error");
      store.setLastServerError(err?.message || "GPS hardware subscription failed");
      throw err;
    }
  }

  /**
   * Stop foreground tracking and cleanly unsubscribe.
   */
  public async stopForegroundLocationTracking(): Promise<void> {
    const store = useLocationStore.getState();
    if (this.subscription) {
      this.subscription.remove();
      this.subscription = null;
    }

    if (this.syncTimer) {
      clearInterval(this.syncTimer);
      this.syncTimer = null;
    }

    if (this.currentSessionId) {
      const sid = this.currentSessionId;
      locationApi.stopSession(sid).catch((e) => {
        console.debug("[TrackingService] Backend session stop notice:", e?.message);
      });
      this.currentSessionId = null;
    }

    store.setTrackingStatus("stopped");
    if (store.activeSession) {
      store.setActiveSession({
        ...store.activeSession,
        status: "stopped",
        ended_at: new Date().toISOString(),
      });
    }
  }

  /**
   * Pause tracking (keeps session open without transmitting samples).
   */
  public pauseTracking(): void {
    this.isPaused = true;
    useLocationStore.getState().setTrackingStatus("paused");
  }

  /**
   * Resume paused tracking.
   */
  public resumeTracking(): void {
    this.isPaused = false;
    useLocationStore.getState().setTrackingStatus("active");
  }

  /**
   * Start background location tracking (where platform supports expo-task-manager).
   */
  public async startBackgroundLocationTracking(): Promise<void> {
    if (Platform.OS === "web") {
      console.warn("[TrackingService] Background location not supported on Web");
      return;
    }

    const bgPerm = await locationPermissionService.requestBackgroundPermission();
    if (bgPerm !== "granted") {
      throw new Error(`Background location permission not granted: ${bgPerm}`);
    }

    try {
      await Location.startLocationUpdatesAsync(TOURSAFE_BACKGROUND_LOCATION_TASK, {
        accuracy: Location.Accuracy.High,
        timeInterval: 2000,
        distanceInterval: 3,
        foregroundService: {
          notificationTitle: "TourSafe Active Protection",
          notificationBody: "Real-time safety GPS tracking active.",
          notificationColor: "#1A3C6E",
        },
      });
      useLocationStore.getState().setIsBackgroundTracking(true);
    } catch (err) {
      console.warn("[TrackingService] Background task start note:", err);
    }
  }

  /**
   * Stop background location tracking.
   */
  public async stopBackgroundLocationTracking(): Promise<void> {
    if (Platform.OS === "web") return;

    try {
      const isRegistered = await Location.hasStartedLocationUpdatesAsync(TOURSAFE_BACKGROUND_LOCATION_TASK);
      if (isRegistered) {
        await Location.stopLocationUpdatesAsync(TOURSAFE_BACKGROUND_LOCATION_TASK);
      }
    } catch (err) {
      console.debug("[TrackingService] Stop background tracking note:", err);
    }
    useLocationStore.getState().setIsBackgroundTracking(false);
  }

  /**
   * Validate, record quality, update store, and transmit to backend.
   */
  private async processLocationFix(sample: LocationSample, isBackground: boolean) {
    if (!this.validateSample(sample)) {
      console.warn("[TrackingService] Rejected invalid GPS sample:", sample);
      return;
    }

    const store = useLocationStore.getState();

    // 1. Calculate and update quality metrics
    const quality = this.qualityCalc.recordSample(sample);
    store.setQualityMetrics(quality);

    // 2. Append sample to local buffer and state
    store.appendSample(sample);

    // 3. Transmit to backend
    try {
      await locationApi.updateLocation(sample);
      store.setLastServerError(null);
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || "Transmission failed";
      store.setLastServerError(errMsg);
      console.warn("[TrackingService] Location sync note:", errMsg);
    }
  }

  /**
   * Coordinate and sample validation (Prompt 5 Section 9).
   */
  public validateSample(sample: LocationSample): boolean {
    if (typeof sample.latitude !== "number" || isNaN(sample.latitude)) return false;
    if (typeof sample.longitude !== "number" || isNaN(sample.longitude)) return false;

    // Bounds: lat [-90, 90], lon [-180, 180]
    if (sample.latitude < -90 || sample.latitude > 90) return false;
    if (sample.longitude < -180 || sample.longitude > 180) return false;

    // Non-negative accuracy and speed where provided
    if (sample.accuracy !== undefined && sample.accuracy !== null && sample.accuracy < 0) return false;
    if (sample.speed !== undefined && sample.speed !== null && sample.speed < 0) return false;

    // Heading [0, 360] where provided
    if (sample.heading !== undefined && sample.heading !== null && (sample.heading < 0 || sample.heading > 360)) {
      return false;
    }

    // Monotonic sequence number
    if (!sample.sequence_number || sample.sequence_number < 1) return false;

    // Timestamp parseability
    const ts = new Date(sample.timestamp).getTime();
    if (isNaN(ts)) return false;

    return true;
  }

  private startStalenessMonitor() {
    if (this.syncTimer) clearInterval(this.syncTimer);
    this.syncTimer = setInterval(() => {
      const store = useLocationStore.getState();
      if (store.trackingStatus === "active") {
        const metrics = this.qualityCalc.getMetrics();
        store.setQualityMetrics(metrics);
      }
    }, 2000);
  }
}

export const locationTrackingService = new LocationTrackingService();
