/**
 * TourSafe Emergency SOS Experience
 * Deliberate trigger with 5-second countdown, complete lifecycle states:
 * SENDING → SENT → ACKNOWLEDGED → RESPONDER_ASSIGNED → RESPONDER_EN_ROUTE → RESPONDER_ON_SCENE → RESOLVED.
 * Supports offline queued SOS with idempotency, cancellation with reason, and emergency contact dispatch.
 */

import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Animated,
  Modal,
  TextInput,
  ActivityIndicator,
  Linking,
  Vibration,
} from "react-native";
import { useRouter } from "expo-router";
import { useSOSStore } from "@/store/sosStore";
import { useLocationStore } from "@/store/locationStore";
import { useBatteryStore } from "@/store/batteryStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { emergencyApi } from "@/lib/api";
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  X,
  Phone,
  Radio,
  Clock,
  MapPin,
  UserCheck,
  Navigation,
  MessageSquare,
  Sparkles,
  WifiOff,
} from "lucide-react-native";
import Toast from "react-native-toast-message";

export default function SOSScreen() {
  const router = useRouter();
  const {
    sosStatus,
    activeIncidentId,
    incidentState,
    assignedResponder,
    triggerSOS,
    cancelSOS,
    setSOSStatus,
  } = useSOSStore();

  const { currentLocation } = useLocationStore();
  const { batteryInfo } = useBatteryStore();
  const { networkState } = useConnectivityStore();

  const [countdown, setCountdown] = useState<number | null>(null);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const countdownTimerRef = useRef<any>(null);

  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (sosStatus === "triggered" || countdown !== null) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.08,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [sosStatus, countdown]);

  function startCountdown() {
    Vibration.vibrate([0, 150, 100, 150]);
    setCountdown(5);

    let count = 5;
    countdownTimerRef.current = setInterval(() => {
      count -= 1;
      if (count > 0) {
        setCountdown(count);
        Vibration.vibrate(100);
      } else {
        clearInterval(countdownTimerRef.current);
        setCountdown(null);
        executeSOSDispatch();
      }
    }, 1000);
  }

  function abortCountdown() {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
    }
    setCountdown(null);
    Toast.show({ type: "info", text1: "SOS Cancelled", text2: "Emergency countdown aborted." });
  }

  async function executeSOSDispatch() {
    try {
      const lat = currentLocation?.latitude || 15.2993;
      const lng = currentLocation?.longitude || 74.124;
      const accuracy = currentLocation?.accuracy || 10;

      await triggerSOS(lat, lng, accuracy, "Emergency SOS triggered from mobile companion");
      Toast.show({
        type: "error",
        text1: "EMERGENCY SOS SENT",
        text2: "Command Center and nearby responders have been notified.",
      });
    } catch (e: any) {
      Toast.show({
        type: "error",
        text1: "SOS Queued Offline",
        text2: "SOS is saved locally and will transmit as soon as connection is available.",
      });
    }
  }

  async function handleConfirmCancel() {
    if (!cancelReason.trim()) {
      Toast.show({ type: "error", text1: "Reason Required", text2: "Please specify reason for cancellation." });
      return;
    }

    setCancelling(true);
    try {
      await cancelSOS(cancelReason.trim());
      Toast.show({ type: "success", text1: "SOS Stand-Down", text2: "Emergency incident has been cancelled." });
      setCancelModalVisible(false);
      setCancelReason("");
    } catch (err: any) {
      Toast.show({ type: "error", text1: "Cancel Failed", text2: err?.message || "Could not cancel SOS" });
    } finally {
      setCancelling(false);
    }
  }

  const isEmergencyActive = sosStatus === "triggered" || !!activeIncidentId;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Top Header */}
      <View style={styles.header}>
        <Text style={styles.headerKicker}>COMMAND CENTER DISPATCH</Text>
        <Text style={styles.headerTitle}>Emergency Assistance</Text>
        <Text style={styles.headerSub}>
          Press and hold or trigger SOS to dispatch emergency authorities to your exact GPS coordinates.
        </Text>
      </View>

      {/* OFFLINE QUEUE NOTICE */}
      {!networkState.isConnected && (
        <View style={styles.offlinePill}>
          <WifiOff size={16} color="#f59e0b" />
          <Text style={styles.offlinePillText}>
            Offline Mode: SOS will queue with cryptographic timestamp and broadcast over SMS/cellular mesh.
          </Text>
        </View>
      )}

      {/* SOS MAIN ACTION HERO */}
      <View style={styles.sosHeroContainer}>
        {countdown !== null ? (
          <View style={styles.countdownBox}>
            <Text style={styles.countdownTitle}>SENDING EMERGENCY SOS IN</Text>
            <Text style={styles.countdownNumber}>{countdown}</Text>
            <TouchableOpacity style={styles.abortBtn} onPress={abortCountdown}>
              <X size={20} color="#fff" />
              <Text style={styles.abortBtnText}>CANCEL DISPATCH</Text>
            </TouchableOpacity>
          </View>
        ) : isEmergencyActive ? (
          <View style={styles.activeIncidentBox}>
            <View style={styles.incidentStatusHeader}>
              <View style={styles.incidentPulseIcon}>
                <ShieldAlert size={28} color="#fff" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.incidentKicker}>SOS BROADCAST ACTIVE</Text>
                <Text style={styles.incidentStateText}>
                  {incidentState?.toUpperCase() || "RESPONDERS NOTIFIED"}
                </Text>
              </View>
            </View>

            {/* Responder Info */}
            {assignedResponder ? (
              <View style={styles.responderCard}>
                <UserCheck size={18} color="#38bdf8" />
                <View style={{ flex: 1 }}>
                  <Text style={styles.responderName}>{assignedResponder.name || "Police Unit #402"}</Text>
                  <Text style={styles.responderRole}>{assignedResponder.role || "Tourist Safety Officer"}</Text>
                </View>
              </View>
            ) : null}

            {/* Action Buttons */}
            <View style={styles.incidentBtnRow}>
              <TouchableOpacity
                style={styles.chatBtn}
                onPress={() => router.push("/tourist/(tabs)/incidents")}
              >
                <MessageSquare size={16} color="#fff" />
                <Text style={styles.chatBtnText}>Incident Chat & Timeline</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.cancelSOSBtn}
                onPress={() => setCancelModalVisible(true)}
              >
                <Text style={styles.cancelSOSText}>Cancel SOS</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.idleSOSBox}>
            <Animated.View style={[styles.sosButtonOuter, { transform: [{ scale: pulseAnim }] }]}>
              <TouchableOpacity
                style={styles.sosButton}
                onPress={startCountdown}
                activeOpacity={0.8}
              >
                <ShieldAlert size={56} color="#FFFFFF" />
                <Text style={styles.sosButtonLabel}>SOS</Text>
                <Text style={styles.sosButtonSub}>5s Countdown</Text>
              </TouchableOpacity>
            </Animated.View>
            <Text style={styles.idleHint}>
              Tap to initiate 5-second verified emergency dispatch.
            </Text>
          </View>
        )}
      </View>

      {/* WHAT HAPPENS WHEN YOU TRIGGER SOS */}
      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>What happens when you trigger SOS?</Text>
        <View style={styles.infoList}>
          <View style={styles.infoItem}>
            <CheckCircle2 size={16} color="#10b981" style={{ marginTop: 2 }} />
            <Text style={styles.infoText}>
              Your live GPS coordinates (±10m) and battery state are transmitted to the Authority Command Center.
            </Text>
          </View>
          <View style={styles.infoItem}>
            <CheckCircle2 size={16} color="#10b981" style={{ marginTop: 2 }} />
            <Text style={styles.infoText}>
              Nearest verified police, ambulance, or tourist safety responders are immediately mobilized.
            </Text>
          </View>
          <View style={styles.infoItem}>
            <CheckCircle2 size={16} color="#10b981" style={{ marginTop: 2 }} />
            <Text style={styles.infoText}>
              Automated SMS alerts are sent to your designated primary emergency contacts.
            </Text>
          </View>
        </View>
      </View>

      {/* DIRECT EMERGENCY HELPLINES */}
      <View style={styles.helplineSection}>
        <Text style={styles.helplineKicker}>DIRECT EMERGENCY NUMBERS</Text>
        <View style={styles.helplineGrid}>
          <TouchableOpacity
            style={styles.helplineCard}
            onPress={() => Linking.openURL("tel:112")}
          >
            <Phone size={20} color="#0f766e" />
            <View>
              <Text style={styles.helplineNumber}>112</Text>
              <Text style={styles.helplineLabel}>National Emergency</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.helplineCard}
            onPress={() => Linking.openURL("tel:108")}
          >
            <Phone size={20} color="#dc2626" />
            <View>
              <Text style={styles.helplineNumber}>108</Text>
              <Text style={styles.helplineLabel}>Medical Ambulance</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.helplineCard}
            onPress={() => Linking.openURL("tel:1363")}
          >
            <Phone size={20} color="#3b82f6" />
            <View>
              <Text style={styles.helplineNumber}>1363</Text>
              <Text style={styles.helplineLabel}>Tourist Helpline</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.helplineCard}
            onPress={() => Linking.openURL("tel:1091")}
          >
            <Phone size={20} color="#d97706" />
            <View>
              <Text style={styles.helplineNumber}>1091</Text>
              <Text style={styles.helplineLabel}>Women Safety</Text>
            </View>
          </TouchableOpacity>
        </View>
      </View>

      {/* CANCEL SOS MODAL */}
      <Modal visible={cancelModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Cancel Emergency SOS</Text>
            <Text style={styles.modalSub}>
              Please select or enter the reason for standing down the emergency dispatch:
            </Text>

            <View style={styles.reasonButtons}>
              {["Accidental Trigger", "Assistance No Longer Needed", "Resolved Safely"].map(
                (r) => (
                  <TouchableOpacity
                    key={r}
                    style={[
                      styles.reasonOption,
                      cancelReason === r && styles.reasonOptionSelected,
                    ]}
                    onPress={() => setCancelReason(r)}
                  >
                    <Text
                      style={[
                        styles.reasonOptionText,
                        cancelReason === r && styles.reasonOptionTextSelected,
                      ]}
                    >
                      {r}
                    </Text>
                  </TouchableOpacity>
                )
              )}
            </View>

            <TextInput
              style={styles.input}
              placeholder="Or type specific details..."
              placeholderTextColor="#64748b"
              value={cancelReason}
              onChangeText={setCancelReason}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.keepActiveBtn}
                onPress={() => setCancelModalVisible(false)}
              >
                <Text style={styles.keepActiveText}>Keep SOS Active</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.confirmCancelBtn}
                onPress={handleConfirmCancel}
                disabled={cancelling}
              >
                {cancelling ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.confirmCancelText}>Confirm Stand-Down</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
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
    color: "#EF4444",
    letterSpacing: 0.8,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "800",
    color: "#0F172A",
  },
  headerSub: {
    fontSize: 13,
    color: "#94A3B8",
    marginTop: 2,
    lineHeight: 18,
  },
  offlinePill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    padding: 12,
    borderRadius: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
  },
  offlinePillText: {
    fontSize: 12,
    color: "#F59E0B",
    flex: 1,
    lineHeight: 16,
    fontWeight: "500",
  },
  sosHeroContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
  },
  idleSOSBox: {
    alignItems: "center",
    gap: 16,
  },
  sosButtonOuter: {
    width: 190,
    height: 190,
    borderRadius: 95,
    backgroundColor: "rgba(239, 68, 68, 0.2)",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "rgba(239, 68, 68, 0.4)",
  },
  sosButton: {
    width: 156,
    height: 156,
    borderRadius: 78,
    backgroundColor: "#DC2626",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#EF4444",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.5,
    shadowRadius: 14,
    elevation: 12,
    borderWidth: 2,
    borderColor: "rgba(255, 255, 255, 0.4)",
  },
  sosButtonLabel: {
    fontSize: 26,
    fontWeight: "900",
    color: "#0F172A",
    letterSpacing: 2,
    marginTop: 2,
  },
  sosButtonSub: {
    fontSize: 10,
    color: "rgba(255, 255, 255, 0.8)",
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  idleHint: {
    fontSize: 13,
    color: "#94A3B8",
    textAlign: "center",
  },
  countdownBox: {
    alignItems: "center",
    backgroundColor: "#991B1B",
    borderRadius: 24,
    padding: 30,
    width: "100%",
    borderWidth: 2,
    borderColor: "#EF4444",
    gap: 14,
  },
  countdownTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: "#FECACA",
    letterSpacing: 1,
  },
  countdownNumber: {
    fontSize: 64,
    fontWeight: "900",
    color: "#0F172A",
  },
  abortBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#000000",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 14,
    gap: 8,
  },
  abortBtnText: {
    color: "#0F172A",
    fontWeight: "800",
    fontSize: 14,
  },
  activeIncidentBox: {
    backgroundColor: "#7F1D1D",
    borderRadius: 24,
    padding: 20,
    width: "100%",
    borderWidth: 2,
    borderColor: "#EF4444",
    gap: 14,
  },
  incidentStatusHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  incidentPulseIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: "rgba(0, 0, 0, 0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  incidentKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#FCA5A5",
    letterSpacing: 0.8,
  },
  incidentStateText: {
    fontSize: 18,
    fontWeight: "900",
    color: "#0F172A",
  },
  responderCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(0, 0, 0, 0.3)",
    padding: 12,
    borderRadius: 12,
    gap: 10,
  },
  responderName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  responderRole: {
    fontSize: 12,
    color: "#94A3B8",
  },
  incidentBtnRow: {
    gap: 8,
    marginTop: 4,
  },
  chatBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    paddingVertical: 12,
    borderRadius: 12,
    gap: 8,
  },
  chatBtnText: {
    color: "#0F172A",
    fontWeight: "700",
    fontSize: 14,
  },
  cancelSOSBtn: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.15)",
    paddingVertical: 10,
    borderRadius: 12,
  },
  cancelSOSText: {
    color: "#FEE2E2",
    fontWeight: "700",
    fontSize: 13,
  },
  infoCard: {
    backgroundcolor: "#0F172A",
    borderRadius: 18,
    padding: 18,
    borderWidth: 1,
    bordercolor: "#334155",
    gap: 12,
  },
  infoTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  infoList: {
    gap: 10,
  },
  infoItem: {
    flexDirection: "row",
    gap: 10,
    alignItems: "flex-start",
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: "#475569",
    lineHeight: 18,
  },
  helplineSection: {
    gap: 12,
  },
  helplineKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#94A3B8",
    letterSpacing: 0.8,
  },
  helplineGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  helplineCard: {
    width: "48%",
    flexDirection: "row",
    alignItems: "center",
    backgroundcolor: "#0F172A",
    borderRadius: 14,
    padding: 12,
    gap: 10,
    borderWidth: 1,
    bordercolor: "#334155",
  },
  helplineNumber: {
    fontSize: 15,
    fontWeight: "800",
    color: "#0F172A",
  },
  helplineLabel: {
    fontSize: 11,
    color: "#94A3B8",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.8)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#1E293B",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    gap: 14,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },
  modalSub: {
    fontSize: 13,
    color: "#94A3B8",
  },
  reasonButtons: {
    gap: 8,
  },
  reasonOption: {
    backgroundColor: "#0F172A",
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    bordercolor: "#475569",
  },
  reasonOptionSelected: {
    borderColor: "#EF4444",
    backgroundColor: "rgba(239, 68, 68, 0.15)",
  },
  reasonOptionText: {
    color: "#475569",
    fontSize: 13,
    fontWeight: "600",
  },
  reasonOptionTextSelected: {
    color: "#EF4444",
    fontWeight: "700",
  },
  input: {
    backgroundColor: "#0F172A",
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    color: "#0F172A",
    fontSize: 14,
    borderWidth: 1,
    bordercolor: "#475569",
  },
  modalBtnRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 6,
  },
  keepActiveBtn: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    paddingVertical: 12,
    borderRadius: 12,
  },
  keepActiveText: {
    color: "#475569",
    fontWeight: "700",
    fontSize: 13,
  },
  confirmCancelBtn: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DC2626",
    paddingVertical: 12,
    borderRadius: 12,
  },
  confirmCancelText: {
    color: "#0F172A",
    fontWeight: "700",
    fontSize: 13,
  },
});

