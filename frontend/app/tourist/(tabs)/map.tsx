/**
 * TourSafe Live Location & Safety Map
 * Displays:
 * - Real-time GPS location with accuracy circle
 * - Monitored safety zones with risk-level colored perimeters
 * - Itinerary waypoints
 * - Interactive zone detail bottom drawer
 * - Tracking controls floating pill
 */

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
} from "react-native";
import RealMap, { ZonePolygonProp, MapMarkerProp } from "@/components/RealMap";
import { useLocationStore } from "@/store/locationStore";
import { useGeofenceStore } from "@/store/geofenceStore";
import { useTripStore } from "@/store/tripStore";
import { useSOSStore } from "@/store/sosStore";
import { trackingSessionService } from "@/lib/tracking-session/trackingSessionService";
import { geofenceApi } from "@/lib/api";
import {
  Shield,
  Radio,
  Layers,
  Crosshair,
  X,
  Phone,
} from "lucide-react-native";
import Toast from "react-native-toast-message";
import type { ZoneDefinition } from "@/types";

export default function MapScreen() {
  const { currentLocation, trackingStatus } = useLocationStore();
  const { activeZones } = useGeofenceStore();
  const { activeTrip } = useTripStore();
  const { sosStatus } = useSOSStore();

  const [allZones, setAllZones] = useState<ZoneDefinition[]>([]);
  const [selectedZone, setSelectedZone] = useState<ZoneDefinition | null>(null);
  const [loadingZones, setLoadingZones] = useState(false);

  const defaultLat = currentLocation?.latitude || 15.2993;
  const defaultLng = currentLocation?.longitude || 74.124;

  useEffect(() => {
    loadZones();
  }, []);

  async function loadZones() {
    setLoadingZones(true);
    try {
      const res = await geofenceApi.getZones();
      if (res?.data && Array.isArray(res.data)) {
        setAllZones(res.data);
      }
    } catch (e) {
      console.warn("[Map] Failed to load geofence zones:", e);
    } finally {
      setLoadingZones(false);
    }
  }

  async function handleToggleTracking() {
    if (trackingStatus === "active") {
      await trackingSessionService.stopTracking();
      Toast.show({ type: "info", text1: "Tracking Stopped" });
    } else {
      const res = await trackingSessionService.startTracking();
      if (res.success) {
        Toast.show({ type: "success", text1: "Tracking Active" });
      }
    }
  }

  // Convert zones to RealMap polygon format
  const mapPolygons: ZonePolygonProp[] = allZones
    .map((zone) => {
      const coords =
        zone.coordinates?.map((c: any) => ({
          latitude: c.latitude,
          longitude: c.longitude,
        })) || [];
      return {
        coordinates: coords,
        name: `${zone.name} (${(zone.risk_level || "low").toUpperCase()})`,
        risk_level: zone.risk_level || "low",
      };
    })
    .filter((p) => p.coordinates.length > 2);

  // Build markers for user location and itinerary waypoints
  const mapMarkers: MapMarkerProp[] = [];
  if (currentLocation) {
    mapMarkers.push({
      latitude: currentLocation.latitude,
      longitude: currentLocation.longitude,
      title: "Your Location",
      subtitle: `Accuracy: ±${(currentLocation.accuracy || 5).toFixed(0)}m`,
      color: "#0284C7",
      icon: "📍",
    });
  }

  if (activeTrip?.itinerary_stops) {
    activeTrip.itinerary_stops.forEach((stop, idx) => {
      mapMarkers.push({
        latitude: defaultLat + (idx + 1) * 0.005,
        longitude: defaultLng + (idx + 1) * 0.005,
        title: stop.name,
        subtitle: stop.location || "Itinerary Stop",
        color: "#1E40AF",
        icon: "🧭",
      });
    });
  }

  return (
    <View style={styles.container}>
      {/* Platform-Agnostic Map View */}
      <View style={styles.mapContainer}>
        <RealMap
          region={{
            latitude: defaultLat,
            longitude: defaultLng,
            latitudeDelta: 0.05,
            longitudeDelta: 0.05,
            zoom: 14,
          }}
          markers={mapMarkers}
          polygons={mapPolygons}
          height="100%"
        />
      </View>

      {/* Top Floating Header & Filter Bar */}
      <View style={styles.topOverlay}>
        <View style={styles.topHeaderCard}>
          <View style={{ flex: 1 }}>
            <Text style={styles.mapTitle}>Live Safety Map</Text>
            <Text style={styles.mapSub}>
              {allZones.length} Monitored Zones • {activeZones.length} Active
            </Text>
          </View>
          <TouchableOpacity
            style={[
              styles.trackingBtn,
              trackingStatus === "active" ? styles.btnActive : styles.btnInactive,
            ]}
            onPress={handleToggleTracking}
          >
            <Radio size={14} color="#fff" />
            <Text style={styles.trackingBtnText}>
              {trackingStatus === "active" ? "Tracking On" : "Tracking Off"}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Floating Action Buttons */}
      <View style={styles.fabColumn}>
        <TouchableOpacity style={styles.fab} onPress={loadZones}>
          <Layers size={20} color="#FFFFFF" />
        </TouchableOpacity>
      </View>

      {/* Bottom Zone Info Sheet (if selected) */}
      {selectedZone && (
        <View style={styles.zoneDrawer}>
          <View style={styles.drawerHeader}>
            <View
              style={[
                styles.drawerBadge,
                selectedZone.risk_level?.toLowerCase() === "danger"
                  ? styles.drawerBadgeDanger
                  : styles.drawerBadgeSafe,
              ]}
            >
              <Text style={styles.drawerBadgeText}>
                {selectedZone.risk_level?.toUpperCase() || "MONITORED ZONE"}
              </Text>
            </View>
            <TouchableOpacity onPress={() => setSelectedZone(null)}>
              <X size={20} color="#94A3B8" />
            </TouchableOpacity>
          </View>

          <Text style={styles.drawerTitle}>{selectedZone.name}</Text>
          <Text style={styles.drawerDesc}>
            {selectedZone.description || "Official tourism corridor with active emergency response surveillance."}
          </Text>

          <View style={styles.drawerActions}>
            <TouchableOpacity
              style={styles.drawerCallBtn}
              onPress={() => Toast.show({ type: "info", text1: "Helpline", text2: "Tourist Police: 112" })}
            >
              <Phone size={15} color="#fff" />
              <Text style={styles.drawerCallText}>Local Emergency (112)</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  mapContainer: {
    flex: 1,
    width: "100%",
    height: "100%",
  },
  topOverlay: {
    position: "absolute",
    top: 50,
    left: 16,
    right: 16,
    zIndex: 10,
  },
  topHeaderCard: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.92)",
    padding: 14,
    borderRadius: 18,
    borderWidth: 1,
    bordercolor: "#475569",
  },
  mapTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#0F172A",
  },
  mapSub: {
    fontSize: 11,
    color: "#94A3B8",
    marginTop: 2,
  },
  trackingBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 10,
    gap: 6,
  },
  btnActive: {
    backgroundColor: "#059669",
  },
  btnInactive: {
    backgroundColor: "#64748B",
  },
  trackingBtnText: {
    color: "#0F172A",
    fontSize: 12,
    fontWeight: "700",
  },
  fabColumn: {
    position: "absolute",
    right: 16,
    bottom: 40,
    gap: 12,
    zIndex: 10,
  },
  fab: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#1E293B",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.15)",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 6,
  },
  zoneDrawer: {
    position: "absolute",
    bottom: 20,
    left: 16,
    right: 16,
    backgroundColor: "#1E293B",
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.12)",
    gap: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 10,
    zIndex: 20,
  },
  drawerHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  drawerBadge: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  drawerBadgeSafe: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
  },
  drawerBadgeDanger: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
  },
  drawerBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#38BDF8",
  },
  drawerTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: "#0F172A",
  },
  drawerDesc: {
    fontSize: 13,
    color: "#475569",
    lineHeight: 18,
  },
  drawerActions: {
    marginTop: 6,
  },
  drawerCallBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0F766E",
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  drawerCallText: {
    color: "#0F172A",
    fontSize: 13,
    fontWeight: "700",
  },
});

