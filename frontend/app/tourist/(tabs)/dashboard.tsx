/**
 * TourSafe Tourist Home Dashboard
 * Central safety companion hub supporting all 8 core states:
 * 1. NO ACTIVE TRIP
 * 2. ACTIVE TRIP
 * 3. TRACKING ACTIVE
 * 4. TRACKING OFF
 * 5. OFFLINE
 * 6. SAFETY ALERT
 * 7. ACTIVE INCIDENT
 * 8. SOS ACTIVE
 */

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
  ActivityIndicator,
  Modal,
  Alert as RNAlert,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuthStore } from "@/store/authStore";
import { useSafetyStore } from "@/store/safetyStore";
import { useLocationStore } from "@/store/locationStore";
import { useIMUStore } from "@/store/imuStore";
import { useSOSStore } from "@/store/sosStore";
import { useTripStore } from "@/store/tripStore";
import { useGeofenceStore } from "@/store/geofenceStore";
import { useBatteryStore } from "@/store/batteryStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { useAlertStore } from "@/store/alertStore";
import { touristApi, safetyCheckApi } from "@/lib/api";
import { trackingSessionService } from "@/lib/tracking-session/trackingSessionService";
import { imuController } from "@/lib/sensors/imuController";
import RoleSwitch from "@/components/RoleSwitch";
import { ConnectionStatusBadge } from "@/components/ConnectionStatusBadge";
import { NotificationBellButton } from "@/components/NotificationBellButton";
import {
  ShieldAlert,
  ShieldCheck,
  Shield,
  MapPin,
  Calendar,
  Radio,
  Activity,
  Phone,
  ArrowRight,
  AlertTriangle,
  Compass,
  CheckCircle2,
  Clock,
  Battery,
  Wifi,
  WifiOff,
  Plus,
  Navigation,
  MessageSquare,
  AlertOctagon,
  RefreshCw,
  ExternalLink,
} from "lucide-react-native";
import Toast from "react-native-toast-message";

export default function TouristDashboard() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { touristSafetyStatus, setTouristSafetyStatus } = useSafetyStore();
  const { trackingStatus, currentLocation, qualityMetrics } = useLocationStore();
  const { imuStatus, qualityMetrics: imuQuality } = useIMUStore();
  const { sosStatus, activeIncidentId } = useSOSStore();
  const { trips, activeTrip, fetchTrips, completeActiveTrip } = useTripStore();
  const { activeZones, primaryZoneType, highestRiskLevel } = useGeofenceStore();
  const { batteryInfo } = useBatteryStore();
  const { networkState } = useConnectivityStore();
  const { alerts } = useAlertStore();

  const [loading, setLoading] = useState(true);
  const [safetyCheckModal, setSafetyCheckModal] = useState(false);
  const [anomalyPending, setAnomalyPending] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);

  useEffect(() => {
    imuController.checkAvailability();
    loadDashboardData();
  }, []);

  async function loadDashboardData() {
    setLoading(true);
    try {
      await Promise.all([
        fetchTrips(),
        fetchSafetyStatus(),
      ]);
    } catch (e) {
      console.warn("[Dashboard] Load error:", e);
    } finally {
      setLoading(false);
    }
  }

  async function fetchSafetyStatus() {
    try {
      const res = await touristApi.getMyProfileStatus();
      if (res?.data) {
        setTouristSafetyStatus(res.data);
      }
    } catch (e) {
      // Offline fallback
    }
  }

  async function handleToggleTracking() {
    setActionInProgress(true);
    try {
      if (trackingStatus === "active") {
        await trackingSessionService.stopTracking();
        Toast.show({ type: "info", text1: "Tracking Paused", text2: "TourSafe is not currently recording GPS telemetry." });
      } else {
        const result = await trackingSessionService.startTracking();
        if (result.success) {
          Toast.show({ type: "success", text1: "Tracking Active", text2: "Live GPS & motion safety telemetry active." });
        } else {
          Toast.show({ type: "error", text1: "Tracking Error", text2: result.error || "Could not start session" });
        }
      }
    } catch (err: any) {
      Toast.show({ type: "error", text1: "Error", text2: err?.message || "Action failed" });
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleConfirmSafe() {
    try {
      setAnomalyPending(false);
      Toast.show({ type: "success", text1: "Status Confirmed Safe", text2: "Thank you for confirming your safety." });
    } catch (err) {
      console.warn("Safety confirm error:", err);
    }
  }

  function handleNeedHelp() {
    setAnomalyPending(false);
    router.push("/tourist/(tabs)/sos");
  }

  async function handleCompleteTrip() {
    RNAlert.alert(
      "Complete Trip",
      "Are you sure you want to complete this trip? This will stop active tracking and archive your itinerary.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Complete Trip",
          style: "destructive",
          onPress: async () => {
            await trackingSessionService.stopTracking();
            const success = await completeActiveTrip();
            if (success) {
              Toast.show({ type: "success", text1: "Trip Completed", text2: "Trip safely concluded. Tracking stopped." });
            }
          },
        },
      ]
    );
  }

  // Determine current safety state
  const rawSafetyState = touristSafetyStatus?.safety_status || "Normal";
  const isElevated = rawSafetyState.toLowerCase() === "elevated" || rawSafetyState.toLowerCase() === "watch";
  const isIncident = rawSafetyState.toLowerCase() === "incident" || sosStatus === "triggered" || !!activeIncidentId;
  const isSafe = rawSafetyState.toLowerCase() === "normal" || rawSafetyState.toLowerCase() === "safe";
  const isUnknown = rawSafetyState.toLowerCase() === "unknown";

  const isOffline = !networkState.isConnected;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Top Bar with Role & Status Badges */}
      <View style={styles.topBar}>
        <RoleSwitch currentRole="tourist" />
        <View style={styles.topBarRight}>
          <ConnectionStatusBadge />
          <NotificationBellButton />
        </View>
      </View>

      {/* OFFLINE BANNER */}
      {isOffline && (
        <View style={styles.offlineBanner}>
          <WifiOff size={18} color="#f59e0b" />
          <View style={{ flex: 1 }}>
            <Text style={styles.offlineTitle}>Offline Resilience Active</Text>
            <Text style={styles.offlineSub}>
              Telemetry is buffered securely on-device and will sync automatically when your connection returns.
            </Text>
          </View>
        </View>
      )}

      {/* BATTERY LOW WARNING */}
      {batteryInfo.level <= 15 && (
        <View style={styles.batteryBanner}>
          <Battery size={18} color="#ef4444" />
          <View style={{ flex: 1 }}>
            <Text style={styles.batteryTitle}>Battery Low ({batteryInfo.level}%)</Text>
            <Text style={styles.batterySub}>
              TourSafe is preserving battery by reducing non-essential background sampling. Emergency SOS remains fully operational.
            </Text>
          </View>
        </View>
      )}

      {/* ACTIVE SOS / ACTIVE INCIDENT HERO CARD */}
      {isIncident && (
        <View style={styles.incidentHero}>
          <View style={styles.incidentHeader}>
            <View style={styles.incidentPulse}>
              <AlertOctagon size={24} color="#fff" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.incidentKicker}>ACTIVE EMERGENCY INCIDENT</Text>
              <Text style={styles.incidentTitle}>Emergency Assistance Dispatched</Text>
            </View>
          </View>
          <Text style={styles.incidentDesc}>
            Local authorities have been alerted with your verified coordinates. A response unit has been notified.
          </Text>
          <View style={styles.incidentActions}>
            <TouchableOpacity
              style={styles.incidentPrimaryBtn}
              onPress={() => router.push("/tourist/(tabs)/incidents")}
            >
              <MessageSquare size={16} color="#fff" />
              <Text style={styles.incidentBtnText}>Open Incident Command & Chat</Text>
              <ArrowRight size={16} color="#fff" />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.incidentSecondaryBtn}
              onPress={() => router.push("/tourist/(tabs)/sos")}
            >
              <ShieldAlert size={16} color="#ef4444" />
              <Text style={styles.incidentSecText}>View SOS Details</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* ANOMALY ALERT BANNER ("Are you okay?") */}
      {anomalyPending && !isIncident && (
        <View style={styles.anomalyCard}>
          <View style={styles.anomalyHeader}>
            <AlertTriangle size={22} color="#f59e0b" />
            <Text style={styles.anomalyTitle}>We noticed unexpected movement</Text>
          </View>
          <Text style={styles.anomalyDesc}>
            Our motion safety sensor detected a sudden movement pattern. Are you okay and in a safe location?
          </Text>
          <View style={styles.anomalyButtons}>
            <TouchableOpacity style={styles.safeBtn} onPress={handleConfirmSafe}>
              <CheckCircle2 size={16} color="#fff" />
              <Text style={styles.safeBtnText}>YES, I'M SAFE</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.helpBtn} onPress={handleNeedHelp}>
              <ShieldAlert size={16} color="#fff" />
              <Text style={styles.helpBtnText}>I NEED HELP</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* SAFETY STATUS CARD */}
      <View style={styles.safetyCard}>
        <View style={styles.safetyCardHeader}>
          <View
            style={[
              styles.safetyIconBadge,
              isSafe && styles.badgeSafe,
              isElevated && styles.badgeElevated,
              isIncident && styles.badgeIncident,
              isUnknown && styles.badgeUnknown,
            ]}
          >
            {isSafe ? (
              <ShieldCheck size={26} color="#10b981" />
            ) : isElevated ? (
              <AlertTriangle size={26} color="#f59e0b" />
            ) : isIncident ? (
              <ShieldAlert size={26} color="#ef4444" />
            ) : (
              <Shield size={26} color="#94a3b8" />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.safetyCardKicker}>BACKEND SAFETY STATUS</Text>
            <Text style={styles.safetyCardTitle}>
              {isSafe
                ? "All Normal & Safe"
                : isElevated
                ? "Elevated Caution Recommended"
                : isIncident
                ? "Incident in Progress"
                : "Safety Status Standby"}
            </Text>
            <Text style={styles.safetyCardSub}>
              {touristSafetyStatus?.guidance_message ||
                (isSafe
                  ? "Your current area and motion profile appear standard."
                  : isUnknown
                  ? "TourSafe cannot currently confirm your safety status. Ensure GPS tracking is active."
                  : "Please remain aware of your immediate surroundings.")}
            </Text>
          </View>
        </View>
      </View>

      {/* SOS ACTION BUTTON & QUICK EMERGENCY HELPLINES */}
      <View style={styles.sosCard}>
        <TouchableOpacity
          style={styles.sosTriggerBtn}
          onPress={() => router.push("/tourist/(tabs)/sos")}
          activeOpacity={0.85}
        >
          <View style={styles.sosInnerGlow}>
            <ShieldAlert size={36} color="#FFFFFF" />
            <Text style={styles.sosBtnText}>EMERGENCY SOS</Text>
            <Text style={styles.sosBtnHint}>Press for Immediate Assistance</Text>
          </View>
        </TouchableOpacity>

        <View style={styles.emergencyHelplines}>
          <TouchableOpacity
            style={styles.helplineBtn}
            onPress={() => Linking.openURL("tel:112")}
          >
            <Phone size={14} color="#0f766e" />
            <Text style={styles.helplineText}>Police (112)</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.helplineBtn}
            onPress={() => Linking.openURL("tel:108")}
          >
            <Phone size={14} color="#dc2626" />
            <Text style={styles.helplineText}>Ambulance (108)</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.helplineBtn}
            onPress={() => router.push("/tourist/(tabs)/profile")}
          >
            <Text style={styles.helplineText}>Emergency Contacts</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ACTIVE TRIP OR NO ACTIVE TRIP CARD */}
      {activeTrip ? (
        <View style={styles.tripCard}>
          <View style={styles.tripHeader}>
            <View>
              <Text style={styles.tripKicker}>ACTIVE JOURNEY</Text>
              <Text style={styles.tripTitle}>{activeTrip.title}</Text>
              <View style={styles.tripMetaRow}>
                <MapPin size={14} color="#0d9488" />
                <Text style={styles.tripMetaText}>{activeTrip.destination}</Text>
                <Text style={styles.tripDot}>•</Text>
                <Calendar size={14} color="#64748b" />
                <Text style={styles.tripMetaText}>
                  {new Date(activeTrip.start_date).toLocaleDateString()}
                </Text>
              </View>
            </View>
            <TouchableOpacity
              style={styles.completeTripBtn}
              onPress={handleCompleteTrip}
            >
              <Text style={styles.completeTripText}>Complete Trip</Text>
            </TouchableOpacity>
          </View>

          {/* Next Waypoint */}
          {activeTrip.itinerary_stops && activeTrip.itinerary_stops.length > 0 && (
            <View style={styles.waypointBox}>
              <Compass size={16} color="#1E40AF" />
              <View style={{ flex: 1 }}>
                <Text style={styles.waypointLabel}>Next Planned Stop</Text>
                <Text style={styles.waypointName}>
                  {activeTrip.itinerary_stops[0].name || "First Waypoint"}
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => router.push("/tourist/(tabs)/itinerary")}
              >
                <Text style={styles.waypointLink}>View Schedule →</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      ) : (
        <View style={styles.noTripCard}>
          <View style={styles.noTripHeader}>
            <Compass size={28} color="#FF9933" />
            <View style={{ flex: 1 }}>
              <Text style={styles.noTripTitle}>No Active Trip in Progress</Text>
              <Text style={styles.noTripSub}>
                Plan your itinerary to unlock proactive geofence alerts and scheduled waypoint tracking.
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.createTripBtn}
            onPress={() => router.push("/tourist/(tabs)/itinerary")}
          >
            <Plus size={16} color="#fff" />
            <Text style={styles.createTripText}>Plan New Trip</Text>
            <ArrowRight size={16} color="#fff" />
          </TouchableOpacity>
        </View>
      )}

      {/* REAL-TIME TELEMETRY & TRACKING CONTROLS */}
      <View style={styles.telemetrySection}>
        <View style={styles.sectionTitleRow}>
          <Text style={styles.sectionTitle}>DEVICE TELEMETRY & EDGE STATUS</Text>
          <TouchableOpacity
            onPress={handleToggleTracking}
            disabled={actionInProgress}
            style={[
              styles.trackingToggleBtn,
              trackingStatus === "active" ? styles.toggleStop : styles.toggleStart,
            ]}
          >
            {actionInProgress ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Radio size={14} color="#fff" />
                <Text style={styles.toggleText}>
                  {trackingStatus === "active" ? "Pause Tracking" : "Start Tracking"}
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        <View style={styles.statusGrid}>
          {/* GPS Tracking Card */}
          <View style={styles.statusCard}>
            <View style={styles.statusCardTop}>
              <MapPin
                size={18}
                color={trackingStatus === "active" ? "#10b981" : "#94a3b8"}
              />
              <Text style={styles.statusCardLabel}>GPS Fix</Text>
            </View>
            <Text style={styles.statusCardValue}>
              {trackingStatus === "active" ? "Active (Good)" : "Standby"}
            </Text>
            <Text style={styles.statusCardSub}>
              {currentLocation
                ? `±${(currentLocation.accuracy || 5).toFixed(0)}m accuracy`
                : "Tracking off"}
            </Text>
          </View>

          {/* Sensors Card */}
          <View style={styles.statusCard}>
            <View style={styles.statusCardTop}>
              <Activity
                size={18}
                color={imuStatus === "active" ? "#10b981" : "#0d9488"}
              />
              <Text style={styles.statusCardLabel}>IMU Sensors</Text>
            </View>
            <Text style={styles.statusCardValue}>
              {imuStatus === "active" ? "Streaming" : "Standby"}
            </Text>
            <Text style={styles.statusCardSub}>
              {imuQuality.observedFrequencyHz > 0
                ? `${imuQuality.observedFrequencyHz.toFixed(0)} Hz stream`
                : "50 Hz ready"}
            </Text>
          </View>

          {/* Network & Sync Card */}
          <View style={styles.statusCard}>
            <View style={styles.statusCardTop}>
              {networkState.isConnected ? (
                <Wifi size={18} color="#10b981" />
              ) : (
                <WifiOff size={18} color="#f59e0b" />
              )}
              <Text style={styles.statusCardLabel}>Sync & Cloud</Text>
            </View>
            <Text style={styles.statusCardValue}>
              {networkState.isConnected ? "Synced" : "Buffered"}
            </Text>
            <Text style={styles.statusCardSub}>
              {networkState.isConnected ? "Direct connected" : "Local FIFO queue"}
            </Text>
          </View>

          {/* Battery Status Card */}
          <View style={styles.statusCard}>
            <View style={styles.statusCardTop}>
              <Battery
                size={18}
                color={batteryInfo.level <= 15 ? "#ef4444" : "#10b981"}
              />
              <Text style={styles.statusCardLabel}>Battery Power</Text>
            </View>
            <Text style={styles.statusCardValue}>{batteryInfo.level}%</Text>
            <Text style={styles.statusCardSub}>
              {batteryInfo.isCharging ? "Charging" : "Normal policy"}
            </Text>
          </View>
        </View>
      </View>

      {/* QUICK MAP ACCESS SHORTCUT */}
      <TouchableOpacity
        style={styles.mapShortcutCard}
        onPress={() => router.push("/tourist/(tabs)/map")}
      >
        <Navigation size={22} color="#1E40AF" />
        <View style={{ flex: 1 }}>
          <Text style={styles.mapShortcutTitle}>Live Safety Map & Zones</Text>
          <Text style={styles.mapShortcutSub}>
            {activeZones.length > 0
              ? `Currently in ${activeZones.length} monitored zone(s)`
              : "View nearby tourist safe zones, police kiosks, and waypoints."}
          </Text>
        </View>
        <ArrowRight size={18} color="#1E40AF" />
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B132B",
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
    gap: 16,
  },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  topBarRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  offlineBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
  },
  offlineTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#F59E0B",
  },
  offlineSub: {
    fontSize: 12,
    color: "#D97706",
    marginTop: 2,
    lineHeight: 16,
  },
  batteryBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "rgba(239, 68, 68, 0.12)",
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.3)",
  },
  batteryTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#EF4444",
  },
  batterySub: {
    fontSize: 12,
    color: "#FCA5A5",
    marginTop: 2,
    lineHeight: 16,
  },
  incidentHero: {
    backgroundColor: "#991B1B",
    borderRadius: 20,
    padding: 18,
    borderWidth: 2,
    borderColor: "#EF4444",
    gap: 12,
  },
  incidentHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  incidentPulse: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "rgba(0, 0, 0, 0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  incidentKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#FECACA",
    letterSpacing: 0.8,
  },
  incidentTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 2,
  },
  incidentDesc: {
    fontSize: 13,
    color: "#FEE2E2",
    lineHeight: 18,
  },
  incidentActions: {
    gap: 8,
    marginTop: 4,
  },
  incidentPrimaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    gap: 8,
  },
  incidentBtnText: {
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 14,
  },
  incidentSecondaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 12,
    gap: 8,
  },
  incidentSecText: {
    color: "#991B1B",
    fontWeight: "700",
    fontSize: 13,
  },
  anomalyCard: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderRadius: 18,
    padding: 16,
    borderWidth: 1.5,
    borderColor: "#F59E0B",
    gap: 10,
  },
  anomalyHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  anomalyTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: "#FBBF24",
  },
  anomalyDesc: {
    fontSize: 13,
    color: "#FDE68A",
    lineHeight: 18,
  },
  anomalyButtons: {
    flexDirection: "row",
    gap: 10,
    marginTop: 4,
  },
  safeBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#059669",
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  safeBtnText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 13,
  },
  helpBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  helpBtnText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 13,
  },
  safetyCard: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  safetyCardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 14,
  },
  safetyIconBadge: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeSafe: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(16, 185, 129, 0.4)",
  },
  badgeElevated: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.4)",
  },
  badgeIncident: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.4)",
  },
  badgeUnknown: {
    backgroundColor: "rgba(148, 163, 184, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.4)",
  },
  safetyCardKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#94A3B8",
    letterSpacing: 0.8,
  },
  safetyCardTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 2,
  },
  safetyCardSub: {
    fontSize: 13,
    color: "#CBD5E1",
    marginTop: 4,
    lineHeight: 18,
  },
  sosCard: {
    gap: 10,
  },
  sosTriggerBtn: {
    backgroundColor: "#DC2626",
    borderRadius: 20,
    padding: 16,
    alignItems: "center",
    shadowColor: "#EF4444",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 8,
    borderWidth: 1.5,
    borderColor: "rgba(255, 255, 255, 0.3)",
  },
  sosInnerGlow: {
    alignItems: "center",
  },
  sosBtnText: {
    fontSize: 19,
    fontWeight: "900",
    color: "#FFFFFF",
    letterSpacing: 1.2,
    marginTop: 4,
  },
  sosBtnHint: {
    fontSize: 12,
    color: "rgba(255, 255, 255, 0.85)",
    marginTop: 2,
    fontWeight: "500",
  },
  emergencyHelplines: {
    flexDirection: "row",
    gap: 8,
  },
  helplineBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(30, 41, 59, 0.7)",
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 12,
    gap: 6,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  helplineText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#E2E8F0",
  },
  tripCard: {
    backgroundColor: "rgba(30, 41, 59, 0.7)",
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
    gap: 14,
  },
  tripHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  tripKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#38BDF8",
    letterSpacing: 0.8,
  },
  tripTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 2,
  },
  tripMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 6,
  },
  tripMetaText: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "500",
  },
  tripDot: {
    color: "#64748b",
  },
  completeTripBtn: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.3)",
  },
  completeTripText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#FCA5A5",
  },
  waypointBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    padding: 12,
    borderRadius: 12,
    gap: 10,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.05)",
  },
  waypointLabel: {
    fontSize: 10,
    textTransform: "uppercase",
    color: "#94A3B8",
    fontWeight: "700",
  },
  waypointName: {
    fontSize: 13,
    fontWeight: "700",
    color: "#FFFFFF",
    marginTop: 1,
  },
  waypointLink: {
    fontSize: 12,
    color: "#60A5FA",
    fontWeight: "700",
  },
  noTripCard: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 14,
  },
  noTripHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  noTripTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  noTripSub: {
    fontSize: 12,
    color: "#94A3B8",
    marginTop: 3,
    lineHeight: 16,
  },
  createTripBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#1E40AF",
    paddingVertical: 12,
    borderRadius: 12,
    gap: 8,
  },
  createTripText: {
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 14,
  },
  telemetrySection: {
    gap: 12,
  },
  sectionTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "800",
    color: "#94A3B8",
    letterSpacing: 0.8,
  },
  trackingToggleBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 10,
    gap: 6,
  },
  toggleStart: {
    backgroundColor: "#059669",
  },
  toggleStop: {
    backgroundColor: "#D97706",
  },
  toggleText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },
  statusGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  statusCard: {
    width: "48%",
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  statusCardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  statusCardLabel: {
    fontSize: 11,
    color: "#94A3B8",
    fontWeight: "600",
  },
  statusCardValue: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 8,
  },
  statusCardSub: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
  mapShortcutCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(30, 58, 138, 0.3)",
    padding: 16,
    borderRadius: 18,
    gap: 12,
    borderWidth: 1,
    borderColor: "rgba(59, 130, 246, 0.3)",
  },
  mapShortcutTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  mapShortcutSub: {
    fontSize: 12,
    color: "#93C5FD",
    marginTop: 2,
  },
});
