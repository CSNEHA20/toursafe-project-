/**
 * TourSafe Safety & Alerts Center (Prompt 23 Advanced Safety Intelligence)
 * Displays:
 * - Authoritative multi-signal safety index & status
 * - Proactive Safety Check response UX ("Are you okay?" with direct backend sync)
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
import { touristApi, api } from "@/lib/api";
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
  Gauge,
  Activity,
  HeartHandshake,
} from "lucide-react-native";
import Toast from "react-native-toast-message";

export default function SafetyScreen() {
  const router = useRouter();
  const { touristSafetyStatus, setTouristSafetyStatus } = useSafetyStore();
  const { activeZones, primaryZoneType } = useGeofenceStore();
  const { alerts } = useAlertStore();
  const { currentLocation, trackingStatus } = useLocationStore();

  const [loading, setLoading] = useState(false);
  const [submittingCheck, setSubmittingCheck] = useState(false);

  useEffect(() => {
    loadSafetyStatus();
  }, []);

  async function loadSafetyStatus() {
    setLoading(true);
    try {
      const res = await api.get("/tourists/me/safety");
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
    setSubmittingCheck(true);
    try {
      await api.post("/tourists/me/safety/check-response", {
        response_type: "SAFE_CONFIRMED",
        user_note: "Tourist confirmed safe from mobile app.",
        timestamp: new Date().toISOString(),
      });
      Toast.show({
        type: "success",
        text1: "Status Confirmed Safe",
        text2: "Your verification has been recorded with TourSafe.",
      });
      await loadSafetyStatus();
    } catch (e) {
      console.warn(e);
      Toast.show({
        type: "error",
        text1: "Submission Failed",
        text2: "Unable to update status. Please check your connection.",
      });
    } finally {
      setSubmittingCheck(false);
    }
  }

  async function handleTriggerEmergency() {
    try {
      await api.post("/tourists/me/safety/check-response", {
        response_type: "ASSISTANCE_REQUESTED",
        user_note: "Assistance requested via prompt response.",
        timestamp: new Date().toISOString(),
      });
    } catch (e) {
      console.warn(e);
    }
    router.push("/tourist/(tabs)/sos");
  }

  const rawStatus = touristSafetyStatus?.safety_status || "Normal";
  const isSafe = rawStatus.toLowerCase() === "normal" || rawStatus.toLowerCase() === "safe";
  const isElevated = rawStatus.toLowerCase() === "elevated" || rawStatus.toLowerCase() === "attention required" || rawStatus.toLowerCase() === "watch";
  const isIncident = rawStatus.toLowerCase() === "incident" || rawStatus.toLowerCase() === "assistance available";
  const isUnknown = rawStatus.toLowerCase() === "unknown" || rawStatus.toLowerCase() === "reconnecting";

  const safetyIndex = touristSafetyStatus?.safety_index ?? (isSafe ? 98 : isElevated ? 65 : isIncident ? 20 : 50);
  const showPrompt = touristSafetyStatus?.proactive_check_required;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerKicker}>OFFICIAL SAFETY INTELLIGENCE</Text>
        <Text style={styles.headerTitle}>Safety & Alerts Center</Text>
        <Text style={styles.headerSub}>
          Real-time multi-signal safety analysis, hazard boundaries, and active protection.
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
                ? "STATUS: NORMAL / SECURE"
                : isElevated
                ? "STATUS: ATTENTION REQUIRED"
                : isIncident
                ? "STATUS: ASSISTANCE AVAILABLE"
                : "STATUS: RECONNECTING"}
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

        {/* Safety Index Rating Metric */}
        <View style={styles.metricRow}>
          <View style={styles.metricBox}>
            <Text style={styles.metricLabel}>SAFETY SCORE</Text>
            <Text style={[styles.metricValue, { color: isSafe ? "#10B981" : isElevated ? "#F59E0B" : "#EF4444" }]}>
              {safetyIndex}/100
            </Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricBox}>
            <Text style={styles.metricLabel}>GEOFENCE ZONE</Text>
            <Text style={styles.metricValueText}>
              {touristSafetyStatus?.zone_name || "Standard Area"}
            </Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricBox}>
            <Text style={styles.metricLabel}>GPS ACCURACY</Text>
            <Text style={styles.metricValueText}>
              {touristSafetyStatus?.gps_connected ? "Locked (High)" : "Searching"}
            </Text>
          </View>
        </View>

        {/* Action Suggestion */}
        <View style={styles.heroActionBox}>
          <Info size={16} color="#E2E8F0" />
          <Text style={styles.heroActionText}>
            {isSafe
              ? "All telemetry nominal. Stay on designated tourist routes."
              : isElevated
              ? "Heightened awareness advised. Check local perimeter notifications."
              : isIncident
              ? "Responders alerted. Maintain your position if safe."
              : "Enable continuous GPS tracking so safety services can monitor your area."}
          </Text>
        </View>
      </View>

      {/* PROACTIVE SAFETY CHECK PROMPT ("Are you okay?") */}
      {showPrompt && (
        <View style={styles.checkCard}>
          <View style={styles.checkHeader}>
            <AlertTriangle size={22} color="#F59E0B" />
            <Text style={styles.checkTitle}>Proactive Safety Check</Text>
          </View>
          <Text style={styles.checkDesc}>
            {touristSafetyStatus?.proactive_check_message ||
              "We noticed an unexpected change in your route or movement dynamics. Please confirm your status:"}
          </Text>
          <View style={styles.checkButtons}>
            <TouchableOpacity
              style={[styles.btnSafe, submittingCheck && { opacity: 0.6 }]}
              onPress={handleConfirmSafe}
              disabled={submittingCheck}
            >
              {submittingCheck ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <CheckCircle2 size={16} color="#fff" />
                  <Text style={styles.btnSafeText}>YES, I'M SAFE</Text>
                </>
              )}
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.btnEmergency}
              onPress={handleTriggerEmergency}
              disabled={submittingCheck}
            >
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
    backgroundColor: "rgba(16, 185, 129, 0.1)",
    borderColor: "rgba(16, 185, 129, 0.4)",
  },
  heroElevated: {
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    borderColor: "rgba(245, 158, 11, 0.4)",
  },
  heroIncident: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    borderColor: "rgba(239, 68, 68, 0.5)",
  },
  heroUnknown: {
    backgroundColor: "rgba(148, 163, 184, 0.08)",
    borderColor: "rgba(148, 163, 184, 0.25)",
  },
  heroTop: {
    flexDirection: "row",
    gap: 14,
    alignItems: "flex-start",
  },
  heroIconBox: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroStatusLevel: {
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.6,
    color: "#E2E8F0",
    marginBottom: 4,
  },
  heroMainMessage: {
    fontSize: 14,
    color: "#FFFFFF",
    lineHeight: 20,
    fontWeight: "500",
  },
  metricRow: {
    flexDirection: "row",
    backgroundColor: "rgba(0, 0, 0, 0.2)",
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    alignItems: "center",
  },
  metricBox: {
    flex: 1,
    alignItems: "center",
  },
  metricDivider: {
    width: 1,
    height: 24,
    backgroundColor: "rgba(255, 255, 255, 0.1)",
  },
  metricLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: "#94A3B8",
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  metricValue: {
    fontSize: 14,
    fontWeight: "800",
  },
  metricValueText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#E2E8F0",
  },
  heroActionBox: {
    flexDirection: "row",
    gap: 10,
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    padding: 12,
    borderRadius: 12,
    alignItems: "center",
  },
  heroActionText: {
    fontSize: 12,
    color: "#CBD5E1",
    flex: 1,
    lineHeight: 16,
  },
  checkCard: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1.5,
    borderColor: "#F59E0B",
    borderRadius: 18,
    padding: 16,
    gap: 12,
  },
  checkHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  checkTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#F59E0B",
  },
  checkDesc: {
    fontSize: 13,
    color: "#FEF3C7",
    lineHeight: 18,
  },
  checkButtons: {
    flexDirection: "row",
    gap: 10,
    marginTop: 4,
  },
  btnSafe: {
    flex: 1,
    backgroundColor: "#10B981",
    paddingVertical: 12,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  btnSafeText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  btnEmergency: {
    flex: 1,
    backgroundColor: "#EF4444",
    paddingVertical: 12,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  btnEmergencyText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  section: {
    gap: 10,
  },
  sectionKicker: {
    fontSize: 10,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.6,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#F8FAFC",
  },
  zonesList: {
    gap: 10,
  },
  zoneCard: {
    backgroundColor: "rgba(255, 255, 255, 0.04)",
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
    flex: 1,
    fontSize: 14,
    fontWeight: "700",
    color: "#E2E8F0",
  },
  zoneRiskBadge: {
    backgroundColor: "rgba(13, 148, 136, 0.2)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  zoneRiskText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#2DD4BF",
  },
  zoneDesc: {
    fontSize: 12,
    color: "#94A3B8",
    lineHeight: 16,
  },
  emptyZonesCard: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    borderRadius: 14,
    padding: 24,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.06)",
    gap: 8,
  },
  emptyZonesTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#CBD5E1",
  },
  emptyZonesSub: {
    fontSize: 12,
    color: "#64748B",
    textAlign: "center",
    lineHeight: 16,
  },
  alertsList: {
    gap: 8,
  },
  alertCard: {
    backgroundColor: "rgba(255, 255, 255, 0.04)",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 6,
  },
  alertTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  alertTitle: {
    flex: 1,
    fontSize: 13,
    fontWeight: "600",
    color: "#F1F5F9",
  },
  alertTime: {
    fontSize: 11,
    color: "#64748B",
  },
  emptyAlertsCard: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    borderRadius: 14,
    padding: 24,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.06)",
    gap: 8,
  },
  emptyAlertsTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#10B981",
  },
  emptyAlertsSub: {
    fontSize: 12,
    color: "#64748B",
    textAlign: "center",
    lineHeight: 16,
  },
});
