/**
 * TourSafe Realtime Subscriptions Interface
 * Hooks directly into the centralized RealtimeClient WebSocket event pipeline.
 */

import { realtimeClient } from "./realtimeClient";
import { initRealtimeEventDispatcher } from "./eventDispatcher";
import type { Alert, SOSEvent, TouristLocation } from "@/types";

type AlertCallback = (alert: Alert) => void;
type SOSCallback = (event: SOSEvent) => void;
type LocationCallback = (locations: TouristLocation[]) => void;

// Initialize dispatcher on first load
initRealtimeEventDispatcher();

export function subscribeToAlerts(onAlert: AlertCallback) {
  const unsubCreated = realtimeClient.onEvent<Alert>("alert.created", onAlert);
  const unsubUpdated = realtimeClient.onEvent<Alert>("alert.updated", onAlert);

  return {
    unsubscribe: () => {
      unsubCreated();
      unsubUpdated();
    },
  };
}

export function subscribeToSOSEvents(onSOS: SOSCallback) {
  const unsubCreated = realtimeClient.onEvent<SOSEvent>("sos.created", onSOS);
  const unsubUpdated = realtimeClient.onEvent<SOSEvent>("sos.updated", onSOS);

  return {
    unsubscribe: () => {
      unsubCreated();
      unsubUpdated();
    },
  };
}

export function subscribeToLocations(onLocations: LocationCallback) {
  const unsub = realtimeClient.onEvent<TouristLocation | TouristLocation[]>(
    "location.updated",
    (payload) => {
      if (Array.isArray(payload)) {
        onLocations(payload);
      } else if (payload) {
        onLocations([payload]);
      }
    }
  );

  return {
    unsubscribe: unsub,
  };
}

export function subscribeTouristLocation(
  touristId: string,
  onLocation: (loc: TouristLocation) => void
) {
  // Subscribe to specific tourist channel
  realtimeClient.subscribe(`tourist:${touristId}`);

  const unsub = realtimeClient.onEvent<TouristLocation>(
    "location.updated",
    (payload) => {
      if (payload && (payload.tourist_id === touristId || payload.id === touristId)) {
        onLocation(payload);
      }
    }
  );

  return {
    unsubscribe: () => {
      unsub();
      realtimeClient.unsubscribe(`tourist:${touristId}`);
    },
  };
}
