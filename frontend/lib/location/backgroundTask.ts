/**
 * TourSafe Background Location Task Definition
 * Safely processes background GPS updates outside the React component lifecycle.
 */

import { Platform } from "react-native";
import * as Location from "expo-location";
import type { LocationSample } from "@/types/location";

export const TOURSAFE_BACKGROUND_LOCATION_TASK = "TOURSAFE_BACKGROUND_LOCATION_TRACKING";

type BackgroundLocationCallback = (samples: LocationSample[]) => void;
let onBackgroundUpdateCallback: BackgroundLocationCallback | null = null;

export function registerBackgroundUpdateCallback(cb: BackgroundLocationCallback) {
  onBackgroundUpdateCallback = cb;
}

export function unregisterBackgroundUpdateCallback() {
  onBackgroundUpdateCallback = null;
}

// Define the background task if running on native mobile platform
if (Platform.OS !== "web") {
  try {
    // Dynamic require so Web bundle does not fail on TaskManager
    const TaskManager = require("expo-task-manager");
    if (TaskManager && TaskManager.defineTask) {
      TaskManager.defineTask(
        TOURSAFE_BACKGROUND_LOCATION_TASK,
        async ({ data, error }: { data: any; error: any }) => {
          if (error) {
            console.warn("[BackgroundTask] Error receiving background location:", error);
            return;
          }
          if (data && data.locations && Array.isArray(data.locations)) {
            const rawLocations = data.locations as Location.LocationObject[];
            const normalizedSamples: LocationSample[] = rawLocations.map((loc) => ({
              session_id: "bg_session",
              timestamp: new Date(loc.timestamp).toISOString(),
              latitude: loc.coords.latitude,
              longitude: loc.coords.longitude,
              altitude: loc.coords.altitude,
              accuracy: loc.coords.accuracy,
              speed: loc.coords.speed,
              heading: loc.coords.heading,
              provider: "gps_background",
              is_background: true,
              sequence_number: 1,
              network_status: "online",
            }));

            if (onBackgroundUpdateCallback) {
              onBackgroundUpdateCallback(normalizedSamples);
            }
          }
        }
      );
    }
  } catch (err) {
    console.debug("[BackgroundTask] TaskManager registration skipped:", err);
  }
}
