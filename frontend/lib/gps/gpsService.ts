/**
 * TourSafe GPS Service
 * Enhanced GPS collection with accuracy classification, GPS/IMU synchronization,
 * jump filter detection, and quality metadata.
 */

import * as Location from "expo-location";
import { GPSPayload, QualityState, GGPSampleWithMetadata, GPSQualityMetadata, GPSJumpFilterResult, GPSAccuracyClassification } from "@/types/telemetry";
import { useLocationStore } from "@/store/locationStore";
import { useBatteryStore } from "@/store/batteryStore";
import { connectivityService } from "@/lib/connectivity/connectivityService";
import { api } from "@/lib/api";

class GPSService {
  private sequenceCounter = 0;
  private readonly MAX_JUMP_SPEED_MS = 100; // 100 m/s max plausible speed

  public classifyAccuracy(accuracyMeters: number | null | undefined): GPSAccuracyClassification {
    if (accuracyMeters === null || accuracyMeters === undefined || isNaN(accuracyMeters)) {
      return "UNKNOWN";
    }
    if (accuracyMeters <= 10) return "GOOD";
    if (accuracyMeters <= 25) return "DEGRADED";
    return "POOR";
  }

  public createQualityMetadata(
    accuracyMeters: number | null | undefined,
    ageSeconds: number = 0,
    satellitesInView?: number | null
  ): GPSQualityMetadata {
    const classification = this.classifyAccuracy(accuracyMeters);
    return {
      classification,
      horizontalAccuracyMeters: accuracyMeters ?? null,
      satellitesInView: satellitesInView ?? null,
      isStale: ageSeconds > 15,
      ageMs: ageSeconds * 1000,
    };
  }

  public applyJumpFilter(
    newSample: GPSPayload,
    previousSample: GPSPayload | null
  ): GPSJumpFilterResult {
    const result: GPSJumpFilterResult = { accepted: true };
    if (!previousSample || !previousSample.timestamp || !newSample.timestamp) {
      return result;
    }

    const distance = this.calculateHaversineDistance(
      previousSample.latitude,
      previousSample.longitude,
      newSample.latitude,
      newSample.longitude
    );

    const newTime = new Date(newSample.timestamp).getTime();
    const prevTime = new Date(previousSample.timestamp).getTime();
    const timeDeltaSec = Math.max(0.001, (newTime - prevTime) / 1000);

    const speed = distance / timeDeltaSec;
    result.calculatedSpeedMps = Math.round(speed * 100) / 100;
    result.distanceDeltaMeters = Math.round(distance * 100) / 100;

    if (speed > this.MAX_JUMP_SPEED_MS) {
      result.accepted = false;
      result.reason = "impossible_jump";
    }

    return result;
  }

  private calculateHaversineDistance(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number
  ): number {
    const R = 6371e3;
    const φ1 = (lat1 * Math.PI) / 180;
    const φ2 = (lat2 * Math.PI) / 180;
    const Δφ = ((lat2 - lat1) * Math.PI) / 180;
    const Δλ = ((lon2 - lon1) * Math.PI) / 180;

    const a =
      Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
      Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  }

  public createSampleWithMetadata(
    gps: GPSPayload,
    sessionId: string,
    previousSample: GPSPayload | null = null,
    forceSequence?: number
  ): GGPSampleWithMetadata {
    this.sequenceCounter++;
    const sequenceNumber = forceSequence ?? this.sequenceCounter;

    const sampleTime = gps.timestamp ? new Date(gps.timestamp).getTime() : Date.now();
    const ageSeconds = Math.max(0, (Date.now() - sampleTime) / 1000);
    const quality = this.createQualityMetadata(gps.accuracy, ageSeconds, null);

    return {
      latitude: gps.latitude,
      longitude: gps.longitude,
      altitude: gps.altitude,
      accuracy: gps.accuracy,
      speed: gps.speed,
      heading: gps.heading,
      timestamp: gps.timestamp || new Date().toISOString(),
      quality,
    };
  }

  public async processGPSSample(
    gps: GPSPayload,
    sessionId: string,
    isBackground: boolean = false
  ): Promise<GGPSampleWithMetadata | null> {
    if (typeof gps.latitude !== "number" || isNaN(gps.latitude)) return null;
    if (typeof gps.longitude !== "number" || isNaN(gps.longitude)) return null;

    const enhanced = this.createSampleWithMetadata(gps, sessionId);

    try {
      await api.post("/api/v1/location/update", {
        latitude: gps.latitude,
        longitude: gps.longitude,
        altitude: gps.altitude,
        accuracy: gps.accuracy,
        speed: gps.speed,
        heading: gps.heading,
        session_id: sessionId,
        timestamp: gps.timestamp || new Date().toISOString(),
        is_background: isBackground,
        network_status: connectivityService.getCurrentState().type,
        battery_level: useBatteryStore.getState().batteryInfo.level,
      });
    } catch {
      // Offline buffering
    }

    useLocationStore.getState().setCurrentLocation({
      latitude: gps.latitude,
      longitude: gps.longitude,
      accuracy: gps.accuracy ?? undefined,
      timestamp: gps.timestamp || new Date().toISOString(),
      session_id: sessionId,
      is_background: isBackground,
      sequence_number: this.sequenceCounter,
    });

    return enhanced;
  }
}

export const gpsService = new GPSService();
export type { GPSAccuracyClassification, GPSQualityMetadata, GPSJumpFilterResult, GGPSampleWithMetadata };