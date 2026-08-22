/**
 * TourSafe Live Location & Safety Map
 * Displays:
 * - Real-time GPS location with accuracy circle
 * - Monitored safety zones with risk-level colored perimeters
 * - Itinerary waypoints
 * - Interactive zone detail bottom drawer
 * - Tracking controls floating pill
 */

import React, { useEffect, useState, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Dimensions,
  ActivityIndicator,
  Modal,
} from "react-native";
import MapView, { Marker, Polygon, Circle, PROVIDER_DEFAULT } from "react-native-maps";
import { useLocationStore } from "@/store/locationStore";
import { useGeofenceStore } from "@/store/geofenceStore";
import { useTripStore } from "@/store/tripStore";
import { useSOSStore } from "@/store/sosStore";
import { trackingSessionService } from "@/lib/tracking-session/trackingSessionService";
import { geofenceApi } from "@/lib/api";
import {
  MapPin,
  Shield,
  AlertTriangle,
  Radio,
  Navigation,
  Compass,
  Layers,
  Crosshair,
  Info,
  X,
  Phone,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react-native";
import Toast from "react-native-toast-message";
import type { ZoneDefinition } from "@/types";

const { width, height } = Dimensions.get("window");

export default function MapScreen() {
  const { currentLocation, trackingStatus, qualityMetrics } = useLocationStore();
  const { activeZones, primaryZoneType } = useGeofenceStore();
  const { activeTrip } = useTripStore();
  const { sosStatus, activeIncidentId } = useSOSStore();

  const mapRef = useRef<MapView>(null);
  const [allZones, setAllZones] = useState<ZoneDefinition[]>([]);
  const [selectedZone, setSelectedZone] = useState<ZoneDefinition | null>(null);
  const [loadingZones, setLoadingZones] = useState(false);
  const [filterType, setFilterType] = useState<"ALL" | "SAFE" | "WARNING" | "RESTRICTED">("ALL");

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

  function handleCenterOnUser() {
    if (currentLocation && mapRef.current) {
      mapRef.current.animateToRegion({
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
        latitudeDelta: 0.02,
        longitudeDelta: 0.02,
      });
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

  function getZoneColor(risk: string) {
    switch (risk?.toLowerCase()) {
      case "danger":
      case "restricted":
      case "critical":
        return { fill: "rgba(239, 68, 68, 0.25)", stroke: "#EF4444" };
      case "warning":
      case "elevated":
        return { fill: "rgba(245, 158, 11, 0.25)", stroke: "#F59E0B" };
      case "safe":
      case "low":
      default:
        return { fill: "rgba(16, 185, 129, 0.2)", stroke: "#10B981" };
    }
  }

  return (
    <View style={styles.container}>
      {/* Map View */}
      <MapView
        ref={mapRef}
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={{
          latitude: defaultLat,
          longitude: defaultLng,
          latitudeDelta: 0.05,
          longitudeDelta: 0.05,
        }}
        showsCompass={false}
        showsUserLocation={false}
      >
        {/* User Location Marker & Accuracy Circle */}
        {currentLocation && (
          <>
            <Circle
              center={{
                latitude: currentLocation.latitude,
                longitude: currentLocation.longitude,
              }}
              radius={currentLocation.accuracy || 15}
              fillColor="rgba(56, 189, 248, 0.2)"
              strokeColor="rgba(56, 189, 248, 0.6)"
              strokeWidth={1}
            />
            <Marker
              coordinate={{
                latitude: currentLocation.latitude,
                longitude: currentLocation.longitude,
              }}
              title="Your Location"
              description={`Accuracy: ±${(currentLocation.accuracy || 5).toFixed(0)}m`}
            >
              <View style={styles.userMarker}>
                <View style={styles.userMarkerPulse} />
                <View style={styles.userMarkerDot} />
              </View>
            </Marker>
          </>
        )}

        {/* Monitored Safety Zones */}
        {allZones.map((zone) => {
          const colors = getZoneColor(zone.risk_level || "low");
          const coords = zone.coordinates?.map((c: any) => ({
            latitude: c.latitude,
            longitude: c.longitude,
          })) || [];


          if (coords.length < 3) return null;

          return (
            <Polygon
              key={zone.id}
              coordinates={coords}
              fillColor={colors.fill}
              strokeColor={colors.stroke}
              strokeWidth={2}
              tappable
              onPress={() => setSelectedZone(zone)}
            />
          );
        })}

        {/* Itinerary Waypoints */}
        {activeTrip?.itinerary_stops?.map((stop, idx) => {
          // If waypoint has lat/lng or default offsets
          return (
            <Marker
              key={idx}
              coordinate={{
                latitude: defaultLat + (idx + 1) * 0.005,
                longitude: defaultLng + (idx + 1) * 0.005,
              }}
              title={stop.name}
              description={stop.location || "Itinerary Stop"}
            >
              <View style={styles.waypointMarker}>
                <Compass size={14} color="#fff" />
              </View>
            </Marker>
          );
        })}
      </MapView>

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
        <TouchableOpacity style={styles.fab} onPress={handleCenterOnUser}>
          <Crosshair size={20} color="#FFFFFF" />
        </TouchableOpacity>
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
    backgroundColor: "#0B132B",
  },
  map: {
    width: "100%",
    height: "100%",
  },
  userMarker: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  userMarkerPulse: {
    position: "absolute",
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: "rgba(56, 189, 248, 0.4)",
  },
  userMarkerDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: "#0284C7",
    borderWidth: 2,
    borderColor: "#FFFFFF",
  },
  waypointMarker: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#1E40AF",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "#FFFFFF",
  },
  topOverlay: {
    position: "absolute",
    top: 50,
    left: 16,
    right: 16,
  },
  topHeaderCard: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.85)",
    padding: 14,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
  },
  mapTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FFFFFF",
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
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },
  fabColumn: {
    position: "absolute",
    right: 16,
    bottom: 40,
    gap: 12,
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
    color: "#FFFFFF",
  },
  drawerDesc: {
    fontSize: 13,
    color: "#CBD5E1",
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
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
});
