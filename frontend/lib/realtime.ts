import { createClient } from "@/lib/supabase";
import type { Alert, SOSEvent, TouristLocation } from "@/types";

type AlertCallback = (alert: Alert) => void;
type SOSCallback = (event: SOSEvent) => void;
type LocationCallback = (locations: TouristLocation[]) => void;

export function subscribeToAlerts(onAlert: AlertCallback) {
  const supabase = createClient();
  return supabase
    .channel("alerts-realtime")
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "alerts" },
      (payload: { new: Alert }) => onAlert(payload.new)
    )
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "alerts" },
      (payload: { new: Alert }) => onAlert(payload.new)
    )
    .subscribe();
}

export function subscribeToSOSEvents(onSOS: SOSCallback) {
  const supabase = createClient();
  return supabase
    .channel("sos-realtime")
    .on(
      "postgres_changes",
      {
        event: "INSERT",
        schema: "public",
        table: "incidents",
        filter: "type=eq.sos",
      },
      (payload: { new: SOSEvent }) => onSOS(payload.new)
    )
    .subscribe();
}

export function subscribeToLocations(onLocations: LocationCallback) {
  const supabase = createClient();
  return supabase
    .channel("locations-realtime")
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "tourist_locations" },
      (payload: { new: TouristLocation }) => onLocations([payload.new])
    )
    .subscribe();
}

export function subscribeTouristLocation(
  touristId: string,
  onLocation: (loc: TouristLocation) => void
) {
  const supabase = createClient();
  return supabase
    .channel(`tourist-location-${touristId}`)
    .on(
      "postgres_changes",
      {
        event: "INSERT",
        schema: "public",
        table: "tourist_locations",
        filter: `tourist_id=eq.${touristId}`,
      },
      (payload: { new: TouristLocation }) => onLocation(payload.new)
    )
    .subscribe();
}
