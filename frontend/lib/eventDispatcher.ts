import { realtimeClient } from "./realtimeClient";
import { useAlertStore } from "@/store/alertStore";
import { useMapStore } from "@/store/mapStore";
import { useSOSStore } from "@/store/sosStore";
import type { Alert, GeoZone, SOSEvent } from "@/types";

let isInitialized = false;
let unsubscribers: (() => void)[] = [];


export function initRealtimeEventDispatcher() {
  if (isInitialized) return;
  isInitialized = true;

  // 1. Zone Events
  const unsubZoneCreated = realtimeClient.onEvent<GeoZone>(
    "zone.created",
    (zone) => {
      if (!zone || !zone.id) return;
      const currentZones = useMapStore.getState().zones;
      if (!currentZones.some((z) => z.id === zone.id)) {
        useMapStore.getState().setZones([...currentZones, zone]);
      }
    }
  );

  const unsubZoneUpdated = realtimeClient.onEvent<GeoZone>(
    "zone.updated",
    (zone) => {
      if (!zone || !zone.id) return;
      const currentZones = useMapStore.getState().zones;
      const updated = currentZones.map((z) => (z.id === zone.id ? zone : z));
      useMapStore.getState().setZones(updated);
    }
  );

  const unsubZoneStatus = realtimeClient.onEvent<{ zone_id: string; status: any }>(
    "zone.status_changed",
    (data) => {
      if (!data?.zone_id) return;
      const currentZones = useMapStore.getState().zones;
      const updated = currentZones.map((z) =>
        z.id === data.zone_id || z.zone_id === data.zone_id
          ? { ...z, status: data.status }
          : z
      );
      useMapStore.getState().setZones(updated);
    }
  );

  // 2. Alert Events
  const unsubAlertCreated = realtimeClient.onEvent<Alert>(
    "alert.created",
    (alert) => {
      if (!alert || !alert.id) return;
      useAlertStore.getState().addAlert(alert);
    }
  );

  const unsubAlertUpdated = realtimeClient.onEvent<Alert>(
    "alert.updated",
    (alert) => {
      if (!alert || !alert.id) return;
      useAlertStore.getState().updateAlert(alert);
    }
  );

  const unsubAlertResolved = realtimeClient.onEvent<{ id: string; status: string }>(
    "alert.resolved",
    (data) => {
      if (!data?.id) return;
      useAlertStore.getState().markRead(data.id);
    }
  );

  // 3. SOS Events
  const unsubSOSCreated = realtimeClient.onEvent<SOSEvent>(
    "sos.created",
    (sos) => {
      if (!sos || !sos.incident_id) return;
      useSOSStore.getState().addSOSEvent(sos);
    }
  );

  const unsubSOSUpdated = realtimeClient.onEvent<{ incident_id: string; status: any }>(
    "sos.updated",
    (data) => {
      if (!data?.incident_id) return;
      useSOSStore.getState().updateSOSEvent(data.incident_id, data.status);
    }
  );

  // 4. Location Events
  const unsubLocationUpdated = realtimeClient.onEvent<any>(
    "location.updated",
    (data) => {
      if (!data || !data.tourist_id || !data.location) return;
      const { tourist_id, location, timestamp, tracking_status } = data;
      useMapStore.getState().updateMarker({
        tourist_id,
        name: `Tourist ${tourist_id.slice(0, 6)}`,
        latitude: location.latitude,
        longitude: location.longitude,
        status: tracking_status === "active" ? "safe" : "inactive",
        last_seen: timestamp || new Date().toISOString(),
      });
    }
  );

  unsubscribers = [
    unsubZoneCreated,
    unsubZoneUpdated,
    unsubZoneStatus,
    unsubAlertCreated,
    unsubAlertUpdated,
    unsubAlertResolved,
    unsubSOSCreated,
    unsubSOSUpdated,
    unsubLocationUpdated,
  ];

  console.log("[EventDispatcher] Realtime event subscriptions initialized.");
}

export function cleanupRealtimeEventDispatcher() {
  unsubscribers.forEach((unsub) => unsub());
  unsubscribers = [];
  isInitialized = false;
}
