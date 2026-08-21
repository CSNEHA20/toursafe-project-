/**
 * TourSafe - Geofencing Store (Zustand)
 * Central store for real-time active safety zones, dwell times, risk alerts, and transition feed.
 */

import { create } from "zustand";
import type {
  ActiveZoneMembershipItem,
  TouristGeofenceSnapshotResponse,
  ZoneTransitionHistoryRecord,
} from "@/types/geofence";

interface GeofenceState {
  activeSnapshot: TouristGeofenceSnapshotResponse | null;
  activeZones: ActiveZoneMembershipItem[];
  highestRiskLevel: "low" | "medium" | "high" | "critical";
  primaryZoneType: "safe" | "warning" | "restricted";
  isStale: boolean;
  recentTransitions: ZoneTransitionHistoryRecord[];
  lastEventNotice: string | null;
  isLoading: boolean;
  error: string | null;

  setSnapshot: (snapshot: TouristGeofenceSnapshotResponse | null) => void;
  handleRealtimeZoneEvent: (eventPayload: any) => void;
  setRecentTransitions: (transitions: ZoneTransitionHistoryRecord[]) => void;
  appendTransition: (transition: ZoneTransitionHistoryRecord) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearLastEventNotice: () => void;
  reset: () => void;
}

export const useGeofenceStore = create<GeofenceState>((set, get) => ({
  activeSnapshot: null,
  activeZones: [],
  highestRiskLevel: "low",
  primaryZoneType: "safe",
  isStale: false,
  recentTransitions: [],
  lastEventNotice: null,
  isLoading: false,
  error: null,

  setSnapshot: (snapshot) => {
    if (!snapshot) {
      set({
        activeSnapshot: null,
        activeZones: [],
        highestRiskLevel: "low",
        primaryZoneType: "safe",
        isStale: false,
      });
      return;
    }
    set({
      activeSnapshot: snapshot,
      activeZones: snapshot.active_zones || [],
      highestRiskLevel: snapshot.highest_risk_level || "low",
      primaryZoneType: snapshot.primary_zone_type || "safe",
      isStale: snapshot.is_stale || false,
    });
  },

  handleRealtimeZoneEvent: (eventPayload) => {
    if (!eventPayload) return;
    const { event_type, zone_id, zone_name, zone_type, risk_level, message } = eventPayload;

    const notice = message || `${event_type}: ${zone_name || zone_id}`;
    const currentZones = get().activeZones;

    if (event_type === "zone.entered") {
      const existing = currentZones.find((z) => z.zone_id === zone_id);
      let updatedZones: ActiveZoneMembershipItem[];
      if (existing) {
        updatedZones = currentZones.map((z) =>
          z.zone_id === zone_id
            ? { ...z, state: "inside", dwell_duration_seconds: 0 }
            : z
        );
      } else {
        const newZone: ActiveZoneMembershipItem = {
          zone_id,
          name: zone_name || zone_id,
          zone_type: zone_type || "safe",
          risk_level: risk_level || "low",
          state: "inside",
          confidence_level: "high",
          confidence_score: 1.0,
          entered_at: eventPayload.timestamp || new Date().toISOString(),
          last_seen_inside: eventPayload.timestamp || new Date().toISOString(),
          dwell_duration_seconds: 0,
          dwell_threshold_notified: false,
          last_location_timestamp: eventPayload.timestamp || new Date().toISOString(),
          distance_to_boundary_meters: eventPayload.distance_to_boundary_m || 50,
          accuracy_meters: eventPayload.accuracy || 5,
        };
        updatedZones = [...currentZones, newZone];
      }
      set({
        activeZones: updatedZones,
        lastEventNotice: notice,
      });
    } else if (event_type === "zone.exited") {
      const updatedZones = currentZones.filter((z) => z.zone_id !== zone_id);
      set({
        activeZones: updatedZones,
        lastEventNotice: notice,
      });
    } else if (event_type === "zone.dwell.threshold_reached") {
      set({ lastEventNotice: notice });
    } else if (event_type === "zone.membership.stale") {
      set({ isStale: true, lastEventNotice: notice });
    }
  },

  setRecentTransitions: (recentTransitions) => set({ recentTransitions }),
  appendTransition: (transition) => {
    const current = get().recentTransitions;
    set({ recentTransitions: [transition, ...current.slice(0, 49)] });
  },
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  clearLastEventNotice: () => set({ lastEventNotice: null }),
  reset: () =>
    set({
      activeSnapshot: null,
      activeZones: [],
      highestRiskLevel: "low",
      primaryZoneType: "safe",
      isStale: false,
      recentTransitions: [],
      lastEventNotice: null,
      isLoading: false,
      error: null,
    }),
}));
