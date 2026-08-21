/**
 * TourSafe Location Tracking Types & Interfaces
 * Canonical definitions for physical device GPS samples, sessions, permissions, and quality.
 */

export type LocationPermissionState =
  | "unknown"
  | "requesting"
  | "granted"
  | "denied"
  | "blocked"
  | "unavailable";

export type LocationTrackingStatus =
  | "idle"
  | "starting"
  | "active"
  | "paused"
  | "reconnecting"
  | "stopped"
  | "error";

export type LocationQualityState =
  | "excellent"    // accuracy <= 10m, fresh <= 3s
  | "good"         // accuracy <= 25m, fresh <= 8s
  | "degraded"     // accuracy <= 50m, fresh <= 15s
  | "poor"         // accuracy > 50m
  | "stale"        // last sample > 15s ago
  | "unavailable"; // no GPS fix

export interface LocationQualityMetrics {
  qualityState: LocationQualityState;
  sampleCount: number;
  observedFrequencyHz: number;
  averageIntervalMs: number;
  minIntervalMs: number;
  maxIntervalMs: number;
  currentAccuracyMeters: number | null;
  staleDurationSeconds: number;
  lastUpdateTimestamp: string | null;
}

export interface LocationSample {
  location_id?: string;
  tourist_id?: string;
  device_id?: string;
  session_id: string;
  timestamp: string; // ISO 8601 UTC
  latitude: number;  // degrees [-90, 90]
  longitude: number; // degrees [-180, 180]
  altitude?: number | null; // meters
  accuracy?: number | null; // horizontal accuracy in meters
  speed?: number | null;    // meters/second
  heading?: number | null;  // degrees [0, 360]
  provider?: string;
  is_background: boolean;
  network_status?: string;
  sequence_number: number;
}

export interface TrackingSession {
  session_id: string;
  tourist_id: string;
  device_id?: string;
  started_at: string;
  ended_at?: string | null;
  status: LocationTrackingStatus;
  last_sequence_number: number;
  last_location_timestamp?: string | null;
  source: string;
  sample_count: number;
}

export interface LiveLocationUpdateEvent {
  tourist_id: string;
  session_id: string;
  location: {
    latitude: number;
    longitude: number;
    altitude?: number | null;
    accuracy?: number | null;
    speed?: number | null;
    heading?: number | null;
    is_background: boolean;
  };
  timestamp: string;
  sequence_number: number;
  tracking_status: string;
}
