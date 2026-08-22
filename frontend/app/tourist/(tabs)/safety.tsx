/**
 * TourSafe Safety & Alerts Center
 * Displays:
 * - Backend authoritative safety status (SAFE, WATCH, ELEVATED, INCIDENT, UNKNOWN)
 * - Anomaly / Safety Check response UX ("Are you okay?")
 * - Monitored Geofence Zones & Safety Guidance
 * - Live Alert Feed with filtering
 */

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafetyStore } from "@/store/safetyStore";
import { useGeofenceStore } from "@/store/geofenceStore";
import { useAlertStore } from "@/store/alertStore";
import { useLocationStore } from "@/store/locationStore";
import { touristApi, safetyCheckApi } from "@/lib/api";
import {
  ShieldCheck,
  ShieldAlert,
  Shield,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Phone,
  ArrowRight,
  Info,
  MapPin,
  Clock,
  ExternalLink,
  ChevronRight,
  Sparkles,
} from "lucide-react-native";
import Toast from "react-native-toast-message";

export default function SafetyScreen() {
  const router = useRouter();
  const { touristSafetyStatus, setTouristSafetyStatus } = useSafetyStore();
  const { activeZones, primaryZoneType } = useGeofenceStore();
  const { alerts } = useAlertStore();
  const { currentLocation, trackingStatus } = useLocationStore();

  const [loading, setLoading] = useState(false);
  const [activeCheckPrompt, setActiveCheckPrompt] = useState<string | null>(null);
  const [safetyFilter, setSafetyFilter] = useState<"ALL" | "CRITICAL" | "INFO">("ALL");

  useEffect(() => {
    loadSafetyStatus();
  }, []);

  async function loadSafetyStatus() {
    setLoading(true);
    try {
      const res = await touristApi.getMyProfileStatus();
      if (res?.data) {
        setTouristSafetyStatus(res.data);
      }
    } catch (e) {
      console.warn("Safety load error:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmSafe() {
    try {
      setActiveCheckPrompt(null);
      Toast.show({
        type: "success",
        text1: "Confirmed Safe",
        text2: "Your status has been updated with the safety center.",
      });
      loadSafetyStatus();
    } catch (e) {
      console.warn(e);
    }
  }

  function handleTriggerEmergency() {
    setActiveCheckPrompt(null);
    router.push("/tourist/(tabs)/sos");
  }

  const rawStatus = touristSafetyStatus?.safety_status || "Normal";
  const isSafe = rawStatus.toLowerCase() === "normal" || rawStatus.toLowerCase() === "safe";
  const isElevated = rawStatus.toLowerCase() === "elevated" || rawStatus.toLowerCase() === "watch";
  const isIncident = rawStatus.toLowerCase() === "incident";
  const isUnknown = rawStatus.toLowerCase() === "unknown";

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerKicker}>OFFICIAL SAFETY STATUS</Text>
        <Text style={styles.headerTitle}>Safety & Alerts Center</Text>
        <Text style={styles.headerSub}>
          Backend-verified travel safety analysis and automated zone alerts.
        </Text>
      </View>

      {/* Safety Status Hero Card */}
      <View
        style={[
          styles.heroStatusCard,
          isSafe && styles.heroSafe,
          isElevated && styles.heroElevated,
          isIncident && styles.heroIncident,
          isUnknown && styles.heroUnknown,
        ]}
      >
        <View style={styles.heroTop}>
          <View style={styles.heroIconBox}>
            {isSafe ? (
              <ShieldCheck size={32} color="#10B981" />
            ) : isElevated ? (
              <AlertTriangle size={32} color="#F59E0B" />
            ) : isIncident ? (
              <AlertOctagon size={32} color="#EF4444" />
            ) : (
              <Shield size={32} color="#94A3B8" />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.heroStatusLevel}>
              {isSafe
                ? "STATUS: NORMAL / SAFE"
                : isElevated
                ? "STATUS: ELEVATED CAUTION"
                : isIncident
                ? "STATUS: ACTIVE INCIDENT"
                : "STATUS: UNKNOWN"}
            </Text>
            <Text style={styles.heroMainMessage}>
              {touristSafetyStatus?.guidance_message ||
                (isSafe
                  ? "You are currently within verified safe parameters."
                  : isElevated
                  ? "Unusual environmental conditions or perimeter alerts near your location."
                  : isIncident
                  ? "Emergency coordination protocol is active."
                  : "Tracking is inactive or location signal unavailable.")}
            </Text>
          </View>
        </View>

        {/* Action Suggestion */}
        <View style={styles.heroActionBox}>
          <Info size={16} color="#E2E8F0" />
          <Text style={styles.heroActionText}>
            {isSafe
              ? "No immediate safety actions required. Enjoy your journey!"
              : isElevated
              ? "Stay on marked tourist trails and monitor local updates."
              : isIncident
              ? "Stay in a secure location while responders proceed."
              : "Enable GPS tracking so safety services can monitor your area."}
          </Text>
        </View>
      </View>

      {/* ANOMALY CONFIRMATION PROMPT ("Are you okay?") */}
      {activeCheckPrompt && (
        <View style={styles.checkCard}>
          <View style={styles.checkHeader}>
            <AlertTriangle size={22} color="#F59E0B" />
            <Text style={styles.checkTitle}>Safety Check Required</Text>
          </View>
          <Text style={styles.checkDesc}>
            {activeCheckPrompt || "We noticed an unexpected stop or sudden movement. Are you okay?"}
          </Text>
          <View style={styles.checkButtons}>
            <TouchableOpacity style={styles.btnSafe} onPress={handleConfirmSafe}>
              <CheckCircle2 size={16} color="#fff" />
              <Text style={styles.btnSafeText}>YES, I'M SAFE</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.btnEmergency} onPress={handleTriggerEmergency}>
              <ShieldAlert size={16} color="#fff" />
              <Text style={styles.btnEmergencyText}>I NEED HELP</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* MONITORED ZONES AWARENESS */}
      <View style={styles.section}>
        <Text style={styles.sectionKicker}>GEOFENCE ENVIRONMENT</Text>
        <Text style={styles.sectionTitle}>Active Monitored Zones</Text>

        {activeZones.length > 0 ? (
          <View style={styles.zonesList}>
            {activeZones.map((zone, idx) => (
              <View key={zone.zone_id || zone.id || idx} style={styles.zoneCard}>
                <View style={styles.zoneCardTop}>
                  <MapPin size={16} color="#0D9488" />
                  <Text style={styles.zoneName}>{zone.name || "Monitored Zone"}</Text>
                  <View style={styles.zoneRiskBadge}>

                    <Text style={styles.zoneRiskText}>{zone.risk_level?.toUpperCase()}</Text>
                  </View>
                </View>
                {zone.description ? (
                  <Text style={styles.zoneDesc}>{zone.description}</Text>
                ) : null}
              </View>
            ))}
          </View>
        ) : (
          <View style={styles.emptyZonesCard}>
            <MapPin size={28} color="#64748B" />
            <Text style={styles.emptyZonesTitle}>Standard Travel Corridor</Text>
            <Text style={styles.emptyZonesSub}>
              You are currently outside designated high-risk or restricted perimeters.
            </Text>
          </View>
        )}
      </View>

      {/* RECENT SAFETY ALERTS FEED */}
      <View style={styles.section}>
        <Text style={styles.sectionKicker}>INCIDENT LOG</Text>
        <Text style={styles.sectionTitle}>Recent Safety Broadcasts</Text>

        {alerts.length > 0 ? (
          <View style={styles.alertsList}>
            {alerts.slice(0, 5).map((a) => (
              <View key={a.id} style={styles.alertCard}>
                <View style={styles.alertTop}>
                  <AlertTriangle
                    size={16}
                    color={a.severity === "high" || a.severity === "critical" ? "#EF4444" : "#F59E0B"}
                  />
                  <Text style={styles.alertTitle}>{a.title || a.description}</Text>
                </View>
                <Text style={styles.alertTime}>
                  {new Date(a.created_at || a.timestamp || Date.now()).toLocaleTimeString()}
                </Text>
              </View>
            ))}
          </View>
        ) : (

          <View style={styles.emptyAlertsCard}>
            <ShieldCheck size={28} color="#10B981" />
            <Text style={styles.emptyAlertsTitle}>No Active Safety Alerts</Text>
            <Text style={styles.emptyAlertsSub}>
              There are no active weather, crowd, or hazard alerts in your region.
            </Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B132B",
  },
  scrollContent: {
    padding: 20,
    paddingTop: 54,
    paddingBottom: 40,
    gap: 20,
  },
  header: {
    gap: 4,
  },
  headerKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#38BDF8",
    letterSpacing: 0.8,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  headerSub: {
    fontSize: 13,
    color: "#94A3B8",
    marginTop: 2,
    lineHeight: 18,
  },
  heroStatusCard: {
    borderRadius: 20,
    padding: 18,
    borderWidth: 1.5,
    gap: 14,
  },
  heroSafe: {
    backgroundColor: "rgba(16, 185, 129, 0.12)",
    borderColor: "#10B981",
  },
  heroElevated: {
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderColor: "#F59E0B",
  },
  heroIncident: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    borderColor: "#EF4444",
  },
  heroUnknown: {
    backgroundColor: "rgba(148, 163, 184, 0.12)",
    borderColor: "#94A3B8",
  },
  heroTop: {
    flexDirection: "row",
    gap: 14,
    alignItems: "flex-start",
  },
  heroIconBox: {
    width: 52,
    height: 52,
    borderRadius: 16,
    backgroundColor: "rgba(0, 0, 0, 0.25)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroStatusLevel: {
    fontSize: 11,
    fontWeight: "800",
    color: "#E2E8F0",
    letterSpacing: 0.8,
  },
  heroMainMessage: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 3,
    lineHeight: 22,
  },
  heroActionBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(0, 0, 0, 0.25)",
    padding: 12,
    borderRadius: 12,
    gap: 8,
  },
  heroActionText: {
    fontSize: 12,
    color: "#E2E8F0",
    flex: 1,
    lineHeight: 16,
    fontWeight: "500",
  },
  checkCard: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderRadius: 18,
    padding: 16,
    borderWidth: 1.5,
    borderColor: "#F59E0B",
    gap: 10,
  },
  checkHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  checkTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FBBF24",
  },
  checkDesc: {
    fontSize: 13,
    color: "#FDE68A",
    lineHeight: 18,
  },
  checkButtons: {
    flexDirection: "row",
    gap: 10,
    marginTop: 4,
  },
  btnSafe: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#059669",
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  btnSafeText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 13,
  },
  btnEmergency: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  btnEmergencyText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 13,
  },
  section: {
    gap: 10,
  },
  sectionKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#38BDF8",
    letterSpacing: 0.8,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  zonesList: {
    gap: 10,
  },
  zoneCard: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 6,
  },
  zoneCardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  zoneName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
    flex: 1,
  },
  zoneRiskBadge: {
    backgroundColor: "rgba(56, 189, 248, 0.15)",
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  zoneRiskText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#38BDF8",
  },
  zoneDesc: {
    fontSize: 12,
    color: "#94A3B8",
    lineHeight: 16,
  },
  emptyZonesCard: {
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.5)",
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 6,
  },
  emptyZonesTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  emptyZonesSub: {
    fontSize: 12,
    color: "#94A3B8",
    textAlign: "center",
  },
  alertsList: {
    gap: 8,
  },
  alertCard: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 4,
  },
  alertTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  alertTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: "#FFFFFF",
    flex: 1,
  },
  alertTime: {
    fontSize: 11,
    color: "#64748B",
    marginLeft: 24,
  },
  emptyAlertsCard: {
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.5)",
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 6,
  },
  emptyAlertsTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  emptyAlertsSub: {
    fontSize: 12,
    color: "#94A3B8",
    textAlign: "center",
  },
});
