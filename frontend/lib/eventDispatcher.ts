import { realtimeClient } from "./realtimeClient";
import { useAlertStore } from "@/store/alertStore";
import { useMapStore } from "@/store/mapStore";
import { useSOSStore } from "@/store/sosStore";
import { useAnomalyStore } from "@/store/anomalyStore";
import { useSafetyStore } from "@/store/safetyStore";
import { useGeofenceStore } from "@/store/geofenceStore";
import { useTripStore } from "@/store/tripStore";
import { useCommandCenterStore } from "@/store/commandCenterStore";
import type { Alert, GeoZone, SOSEvent } from "@/types";
import type { AnomalyDetectedPayload, AnomalyClearedPayload } from "@/types/anomaly";

let isInitialized = false;
let unsubscribers: (() => void)[] = [];
const processedEventIds = new Set<string>();

export function initRealtimeEventDispatcher() {
  if (isInitialized) return;
  isInitialized = true;

  // Track realtime connection status into stores
  const unsubState = realtimeClient.onStateChange((state) => {
    useCommandCenterStore.getState().setConnectionState(state);
    if (state === "connected") {
      useCommandCenterStore.getState().reconcileSnapshot();
      useTripStore.getState().fetchTrips();
    }
  });

  // Global operational router for Command Center & state reconciliation
  const unsubCommandCenterWildcard = realtimeClient.onEvent(
    "*",
    (payload, envelope) => {
      if (envelope) {
        if (envelope.event_id) {
          if (processedEventIds.has(envelope.event_id)) {
            return; // Duplicate event suppression
          }
          processedEventIds.add(envelope.event_id);
          if (processedEventIds.size > 2000) {
            const first = processedEventIds.values().next().value;
            if (first) processedEventIds.delete(first);
          }
        }
        useCommandCenterStore.getState().applyRealtimeEvent(envelope);
      }
    }
  );

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

  const unsubZoneEntered = realtimeClient.onEvent<any>(
    "zone.entered",
    (data) => {
      if (!data) return;
      useGeofenceStore.getState().handleRealtimeZoneEvent({ event_type: "zone.entered", data });
      if (data.zone_name) {
        useAlertStore.getState().addAlert({
          id: `zone_enter_${Date.now()}`,
          type: "system",
          severity: data.risk_level === "critical" ? "critical" : data.risk_level === "high" ? "high" : "low",
          status: "active",
          title: `Entered ${data.zone_name}`,
          description: `You have entered a monitored ${data.zone_type || "safety"} zone (${data.risk_level || "normal"} risk).`,
          created_at: new Date().toISOString(),
        });
      }
    }
  );

  const unsubZoneExited = realtimeClient.onEvent<any>(
    "zone.exited",
    (data) => {
      if (!data) return;
      useGeofenceStore.getState().handleRealtimeZoneEvent({ event_type: "zone.exited", data });
    }
  );

  // 2. Safety State Changed
  const unsubSafetyState = realtimeClient.onEvent<any>(
    "safety.state_changed",
    (data, envelope) => {
      if (!data) return;
      useSafetyStore.getState().handleRealtimeSafetyEvent({
        event_type: "safety.state_changed",
        data,
      });
    }
  );

  // 3. Incident Lifecycle Events
  const unsubIncidentCreated = realtimeClient.onEvent<any>(
    "incident.created",
    (data) => {
      if (!data) return;
      useSafetyStore.getState().handleRealtimeSafetyEvent({
        event_type: "incident.created",
        data,
      });
      if (data.is_sos || data.severity === "CRITICAL") {
        useSOSStore.getState().setActiveIncidentId(data.incident_id);
        useSOSStore.getState().setSosStatus("triggered");
      }
    }
  );

  const unsubIncidentUpdated = realtimeClient.onEvent<any>(
    "incident.updated",
    (data) => {
      if (!data) return;
      useSafetyStore.getState().handleRealtimeSafetyEvent({
        event_type: "incident.updated",
        data,
      });
      if (data.status === "RESOLVED" || data.status === "CLOSED") {
        useSOSStore.getState().setSosStatus("resolved");
      } else if (data.status === "IN_PROGRESS" || data.status === "ASSIGNED") {
        useSOSStore.getState().setSosStatus("responding");
      }
    }
  );

  const unsubIncidentResolved = realtimeClient.onEvent<any>(
    "incident.resolved",
    (data) => {
      if (!data) return;
      useSafetyStore.getState().handleRealtimeSafetyEvent({
        event_type: "incident.resolved",
        data,
      });
      useSOSStore.getState().setSosStatus("resolved");
    }
  );

  // 4. Alert Events
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

  // 5. SOS Events
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

  // 6. Location Events
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

  // 7. ML Sensor Anomaly Events
  const unsubAnomalyDetected = realtimeClient.onEvent<AnomalyDetectedPayload>(
    "anomaly.detected",
    (payload) => {
      if (!payload || !payload.tourist_id) return;
      useAnomalyStore.getState().addOrUpdateAnomaly(payload);

      const alertItem: Alert = {
        id: payload.anomaly_id,
        type: "anomaly",
        severity: payload.anomaly_score >= (payload.threshold * 1.3) ? "high" : "medium",
        status: "active",
        title: "Unusual Movement Noticed",
        description: "We noticed unexpected movement or motion patterns. Please check your safety status.",
        tourist_id: payload.tourist_id,
        latitude: payload.last_known_gps?.latitude,
        longitude: payload.last_known_gps?.longitude,
        created_at: payload.timestamp || new Date().toISOString(),
      };
      useAlertStore.getState().addAlert(alertItem);
    }
  );

  const unsubAnomalyCleared = realtimeClient.onEvent<AnomalyClearedPayload>(
    "anomaly.cleared",
    (payload) => {
      if (!payload || !payload.tourist_id) return;
      useAnomalyStore.getState().clearAnomaly(payload.tourist_id, payload.duration_seconds, payload.peak_score);
      if (payload.anomaly_id) {
        useAlertStore.getState().markRead(payload.anomaly_id);
      }
    }
  );

  // 8. Trip Events
  const unsubTripUpdated = realtimeClient.onEvent<any>(
    "trip.updated",
    () => {
      useTripStore.getState().fetchTrips();
    }
  );

  unsubscribers = [
    unsubState,
    unsubCommandCenterWildcard,
    unsubZoneCreated,
    unsubZoneUpdated,
    unsubZoneEntered,
    unsubZoneExited,
    unsubSafetyState,
    unsubIncidentCreated,
    unsubIncidentUpdated,
    unsubIncidentResolved,
    unsubAlertCreated,
    unsubAlertUpdated,
    unsubAlertResolved,
    unsubSOSCreated,
    unsubSOSUpdated,
    unsubLocationUpdated,
    unsubAnomalyDetected,
    unsubAnomalyCleared,
    unsubTripUpdated,
  ];

  console.log("[EventDispatcher] Realtime event subscriptions & state router initialized.");
}

export function cleanupRealtimeEventDispatcher() {
  unsubscribers.forEach((unsub) => unsub());
  unsubscribers = [];
  isInitialized = false;
  processedEventIds.clear();
}
