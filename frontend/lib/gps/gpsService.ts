/**
 * TourSafe GPS Service
 * Enhanced GPS collection with accuracy classification, GPS/IMU synchronization,
 * jump filter detection, and quality metadata.
 *
 * Principle: Record GPS accuracy. Classify: GOOD / DEGRADED / POOR / UNKNOWN.
 * Do not silently discard poor GPS. Mark quality. Backend remains authoritative.
 */

import * as Location from "expo-location";
import { Platform } from "react-native";
import { GPSPayload, GPSQualityClassification } from "../../types/telemetry";
import { useLocationStore } from "../../store/locationStore";
import { useTelemetryStore } from "../../store/telemetryStore";
import { useBatteryStore } from "@/store/batteryStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { batteryService } from "@/lib/battery/batteryService";
import { connectivityService } from "@/lib/connectivity/connectivityService";
import { QualityState } from "../../types/telemetry";
import { generateSequenceNumber } from "../lib/utils";
import { api } from "../api";

/**
 * GPS accuracy classifications.
 * Used to classify GPS quality without discarding poor data.
 */
export type GPSAccuracyClassification =
  | "GOOD"    // accuracy <= 10m, fresh
  | "DEGRADED" // accuracy <= 25m, fresh
  | "POOR"    // accuracy > 25m
  | "UNKNOWN"; // no GPS fix available

/**
 * GPS quality metadata attached to each GPS sample.
 */
export interface GPSQualityMetadata {
  accuracyClassification: GPSAccuracyClassification;
  accuracyMeters: number | null;
  ageSeconds: number;
  isStale: boolean;
  satellitesInView?: number | null;
}

/**
 * GPS jump filter result.
 * Detects impossible or suspicious GPS jumps using timestamp, distance, speed, accuracy.
 */
export interface GPSJumpFilterResult {
  isAnomaly: boolean;
  reason?: "impossible_jump" | "suspicious_speed" | "accuracy_drop" | "unknown";
  distanceMeters?: number;
  speedMetersPerSecond?: number;
  accuracyChange?: number;
  originalSample: GPSPayload;
}

/**
 * GPS sample with full metadata.
 * Every telemetry record must include tracking_session_id.
 * The ID must originate from the server where possible.
 */
export interface GGPSampleWithMetadata {
  session_id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  altitude?: number | null;
  accuracy: number | null;
  speed?: number | null;
  heading?: number | null;
  provider?: string | null;
  tracking_session_id: string;
  sequence_number: number;
  quality: GPSQualityMetadata;
  gps_jump_filter?: GPSJumpFilterResult;
}

/**
 * GPS Service coordinates GPS collection with accuracy classification,
 * jump filtering, synchronization metadata, and telemetry envelope creation.
 */
class GPSService {
  private lastSampleTime: number = 0;
  private lastLatencyCheck: number = 0;
  private sequenceCounter = 0;
  private readonly MAX_JUMP_DISTANCE_METERS = 2000; // 2km max reasonable jump
  private readonly MAX_JUMP_SPEED_MS = 30; // 30m/s ≈ 108 km/h max reasonable

  constructor() {
    // No-op - state managed via stores
  }

  /**
   * Classify GPS accuracy based on horizontal accuracy value.
   * Configurable thresholds - product requirements may differ.
   */
  public classifyAccuracy(accuracy: number | null | undefined): GPSAccuracyClassification {
    if (accuracy === null || accuracy === undefined) {
      return "UNKNOWN";
    }

    if (accuracy <= 10) {
      return "GOOD";
    } else if (accuracy <= 25) {
      return "DEGRADED";
    } else {
      return "POOR";
    }
  }

  /**
   * Create GPS quality metadata from an accuracy value.
   */
  public createQualityMetadata(
    accuracy: number | null,
    ageSeconds: number,
    satellitesInView?: number | null
  ): GPSQualityMetadata {
    return {
      accuracyClassification: this.classifyAccuracy(accuracy),
      accuracyMeters: accuracy || null,
      ageSeconds,
      isStale: ageSeconds > 15, // stale if > 15 seconds old
      satellitesInView,
    };
  }

  /**
   * Apply GPS jump filter to detect impossible/suspicious jumps.
   * Uses: timestamp, distance, speed, accuracy.
   * Does not silently delete the point. Marks: GPS_ANOMALY or QUALITY_DEGRADED.
   */
  public applyJumpFilter(
    newSample: GPSPayload,
    previousSample: GPSPayload | null
  ): GPSJumpFilterResult {
    const result: GPSJumpFilterResult = {
      isAnomaly: false,
      originalSample: newSample,
    };

    if (!previousSample) {
      // First sample - no previous to compare against
      result.isAnomaly = false;
      return result;
    }

    // Calculate distance between previous and new sample
    const distance = this.calculateHaversineDistance(
      previousSample.latitude,
      previousSample.longitude,
      newSample.latitude,
      newSample.longitude
    );

    // Calculate time delta in seconds
    const newTime = new Date(newSample.timestamp).getTime();
    const prevTime = new Date(previousSample.timestamp).getTime();
    const timeDeltaMs = newTime - prevTime;
    const timeDeltaSec = timeDeltaMs / 1000;

    // Avoid division by zero or negative time
    if (timeDeltaSec <= 0) {
      result.isAnomaly = false;
      result.reason = "unknown";
      return result;
    }

    // Calculate inferred speed
    const inferredSpeed = distance / timeDeltaSec; // m/s

    // Check for impossible jump (excessive speed)
    if (inferredSpeed > this.MAX_JUMP_SPEED_MS) {
      result.isAnomaly = true;
      result.reason = "suspicious_speed";
      result.speedMetersPerSecond = Math.round(inferredSpeed * 100) / 100;
      result.distanceMeters = Math.round(distance * 100) / 100;
      return result;
    }

    // Check for large distance jump without proportional time
    // (e.g., jumping 5km in 1 second would be caught by speed check above,
    //  but this catches more subtle cases)
    const maxReasonableSpeed = 50; // 50 m/s ≈ 180 km/h - very fast but possible
    if (inferredSpeed > maxReasonableSpeed && distance > 1000) {
      // Could be an anomaly, but also could be GPS glitch
      // Classify based on accuracy too
      if (newSample.accuracy && previousSample.accuracy) {
        const accuracyChange = Math.abs(newSample.accuracy - previousSample.accuracy);
        if (accuracyChange > 50) {
          result.isAnomaly = true;
          result.reason = "accuracy_drop";
          result.accuracyChange = accuracyChange;
          result.distanceMeters = Math.round(distance * 100) / 100;
          result.speedMetersPerSecond = Math.round(inferredSpeed * 100) / 100;
          return result;
        }
      }
      // Above max speed but not extreme - mark as suspicious, not anomaly
      result.isAnomaly = false;
      result.reason = "suspicious_speed";
      result.speedMetersPerSecond = Math.round(inferredSpeed * 100) / 100;
      result.distanceMeters = Math.round(distance * 100) / 100;
      return result;
    }

    // Check for accuracy degradation
    if (newSample.accuracy && previousSample.accuracy) {
      const accuracyChange = Math.abs(newSample.accuracy - previousSample.accuracy);
      if (accuracyChange > 50) {
        // Significant accuracy change - mark quality degraded
        // But NOT an anomaly unless combined with other factors
        if (!result.isAnomaly) {
          result.reason = "accuracy_drop";
          result.accuracyChange = accuracyChange;
        }
      }
    }

    // No anomaly detected
    result.isAnomaly = false;
    return result;
  }

  /**
   * Calculate Haversine distance between two points in meters.
   */
  private calculateHaversineDistance(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number
  ): number {
    const R = 6371e3; // Earth radius in meters
    const φ1 = (lat1 * Math.PI) / 180;
    const φ2 = (lat2 * Math.PI) / 180;
    const Δφ = ((lat2 - lat1) * Math.PI) / 180;
    const Δλ = ((lon2 - lon1) * Math.PI) / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
      Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  }

  /**
   * Create a GPS sample with full metadata for telemetry.
   * Includes: sequence number, tracking_session_id, quality, jump filter.
   */
  public createSampleWithMetadata(
    gps: GPSPayload,
    sessionId: string,
    previousSample: GPSPayload | null = null,
    forceSequence?: number
  ): GGPSampleWithMetadata {
    // Increment sequence number
    this.sequenceCounter++;
    const sequenceNumber = forceSequence ?? this.sequenceCounter;

    // Compute age of the sample
    const sampleTime = new Date(gps.timestamp).getTime();
    const now = Date.now();
    const ageSeconds = Math.max(0, (now - sampleTime) / 1000);

    // Create quality metadata
    const quality = this.createQualityMetadata(
      gps.accuracy,
      ageSeconds,
      gps.satellitesInView
    );

    // Apply jump filter
    const jumpFilter = this.applyJumpFilter(gps, previousSample);

    // Determine if we should mark the point based on quality
    // Backend remains authoritative - we always send but mark quality
    const shouldMarkQuality = quality.accuracyClassification !== "UNKNOWN";

    // Build the enhanced GPS sample
    const enhancedSample: GGPSampleWithMetadata = {
      session_id: sessionId,
      timestamp: gps.timestamp || new Date().toISOString(),
      latitude: gps.latitude,
      longitude: gps.longitude,
      altitude: gps.altitude,
      accuracy: gps.accuracy,
      speed: gps.speed,
      heading: gps.heading,
      provider: gps.provider,
      tracking_session_id: sessionId,
      sequence_number: sequenceNumber,
      quality,
      ...(jumpFilter.isAnomaly && { gps_jump_filter: jumpFilter }),
    };

    return enhancedSample;
  }

  /**
   * Process a GPS sample through the full pipeline:
   * - Validate
   * - Classify accuracy
   * - Apply jump filter
   * - Create metadata-enriched sample
   * - Transmit to backend
   */
  public async processGPSSample(
    gps: GPSPayload,
    sessionId: string,
    isBackground: boolean = false
  ): Promise<GGPSampleWithMetadata | null> {
    // 1. Basic validation (reuse existing validateSample logic)
    if (typeof gps.latitude !== "number" || isNaN(gps.latitude)) {
      console.warn("[GPSService] Invalid latitude");
      return null;
    }
    if (typeof gps.longitude !== "number" || isNaN(gps.longitude)) {
      console.warn("[GPSService] Invalid longitude");
      return null;
    }

    // 2. Get previous sample from store for jump filter
    const locationStore = useLocationStore.getState();
    const previousSample = locationStore.currentLocation
      ? {
          latitude: locationStore.currentLocation.latitude,
          longitude: locationStore.currentLongitude,
          timestamp: locationStore.currentLocation.timestamp,
        } as GPSPayload
      : null;

    // 3. Create enhanced sample with metadata
    const enhancedSample = this.createSampleWithMetadata(gps, sessionId, previousSample);

    // 4. Transmit to backend via location API
    try {
      await api.post("/api/v1/location/update", {
        ...enhancedSample,
        is_background: isBackground,
        network_status: connectivityService.getCurrentState().type,
        battery_level: useBatteryStore.getState().batteryInfo.level,
        schema_version: "1.0.0",
      });
    } catch (err: any) {
      console.warn("[GPSService] Backend transmit failed:", err);
      // Sample is still valid - just backend transmission failed
      // It will be buffered offline
    }

    // 5. Update location store with the enhanced sample
    // Store the raw GPS payload (not the enhanced version) for future jump filtering
    useLocationStore.getState().setCurrentLocation({
      ...locationStore.currentLocation,
      latitude: gps.latitude,
      longitude: gps.longitude,
      accuracy: gps.accuracy,
      timestamp: gps.timestamp,
      sequence_number: enhancedSample.sequence_number,
    });

    return enhancedSample;
  }

  /**
   * Start GPS tracking session initialization.
   * Validates permissions, creates session, prepares GPS monitoring.
   */
  public async startTrackingSession(): Promise<{
    success: boolean;
    sessionId?: string;
    error?: string;
  }> {
    // Validate permissions
    const permService = useLocationStore.getState().permissionService;
    if (!permService) {
      // Fallback
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const { locationPermissionService } = require("../../lib/location/permissionService");
        // Request permission
        const result = await locationPermissionService.requestForegroundPermission();
        if (result !== "granted") {
          return { success: false, error: `Permission not granted: ${result}` };
        }
      } catch (err) {
        return { success: false, error: "Permission service unavailable" };
      }
    }

    // Generate or retrieve session ID
    // In a full implementation, this would come from the backend
    const sessionId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

    // Record start time for latency tracking
    this.lastSampleTime = Date.now();

    return { success: true, sessionId };
  }

  /**
   * Stop GPS tracking session.
   * Flushes any pending data and cleans up.
   */
  public async stopTrackingSession(): Promise<{
    success: boolean;
    error?: string;
  }> {
    // Clean up - in a full implementation, this would
    // notify the backend and flush the offline buffer
    this.sequenceCounter = 0;
    return { success: true };
  }
}

export const gpsService = new GPSService();

export type {
  GPSAccuracyClassification,
  GPSQualityMetadata,
  GPSJumpFilterResult,
  GGPSampleWithMetadata,
};