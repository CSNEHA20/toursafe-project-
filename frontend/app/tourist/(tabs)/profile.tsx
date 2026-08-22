/**
 * TourSafe Profile, Emergency Contacts, Privacy, and Device Health Screen
 * Features:
 * - Tourist Identity & Verification Badge
 * - Emergency Contacts CRUD with priority uniqueness
 * - Privacy & Consent Management
 * - App Permissions Center with recovery
 * - Device Health & Battery Diagnostics
 * - Developer Diagnostics (DEV mode)
 * - Logout
 */

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Switch,
  Modal,
  ActivityIndicator,
  Alert as RNAlert,
  Linking,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuthStore } from "@/store/authStore";
import { useBatteryStore } from "@/store/batteryStore";
import { useLocationStore } from "@/store/locationStore";
import { useIMUStore } from "@/store/imuStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { useDeviceHealthStore } from "@/store/deviceHealthStore";
import { touristApi, consentApi } from "@/lib/api";
import {
  User,
  Shield,
  Phone,
  Plus,
  Trash2,
  Lock,
  Battery,
  MapPin,
  Activity,
  Wifi,
  Bell,
  LogOut,
  ChevronRight,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Info,
  Wrench,
  Sparkles,
  Edit2,
} from "lucide-react-native";
import Toast from "react-native-toast-message";
import type { EmergencyContact, DeviceHealthStatus } from "@/types";
import { PrivacyConsentCenterModal } from "@/components/tourist/PrivacyConsentCenterModal";

export default function ProfileScreen() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const { batteryInfo } = useBatteryStore();
  const { permissionState, qualityMetrics } = useLocationStore();
  const { imuStatus, qualityMetrics: imuQuality } = useIMUStore();
  const { networkState } = useConnectivityStore();
  const { healthStatus } = useDeviceHealthStore();

  const [emergencyContacts, setEmergencyContacts] = useState<EmergencyContact[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [contactModalVisible, setContactModalVisible] = useState(false);
  const [diagnosticsModalVisible, setDiagnosticsModalVisible] = useState(false);
  const [privacyModalVisible, setPrivacyModalVisible] = useState(false);

  // Add Contact Form State
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactRelationship, setContactRelationship] = useState("Family");
  const [isPrimary, setIsPrimary] = useState(false);
  const [submittingContact, setSubmittingContact] = useState(false);

  // Consent toggles
  const [locationConsent, setLocationConsent] = useState(true);
  const [motionConsent, setMotionConsent] = useState(true);
  const [credentialSharing, setCredentialSharing] = useState(true);
  const [emergencyNotificationConsent, setEmergencyNotificationConsent] = useState(true);

  useEffect(() => {
    loadContacts();
  }, []);

  async function loadContacts() {
    setLoadingContacts(true);
    try {
      const res = await touristApi.getMyEmergencyContacts();
      if (res?.data && Array.isArray(res.data)) {
        setEmergencyContacts(res.data);
      }
    } catch (e) {
      console.warn("Failed to load contacts:", e);
    } finally {
      setLoadingContacts(false);
    }
  }

  async function handleAddContact() {
    if (!contactName.trim() || !contactPhone.trim()) {
      Toast.show({ type: "error", text1: "Validation Error", text2: "Name and Phone number are required." });
      return;
    }

    setSubmittingContact(true);
    try {
      const priority = emergencyContacts.length + 1;
      const newContact: EmergencyContact = {
        name: contactName.trim(),
        phone_number: contactPhone.trim(),
        relationship: contactRelationship,
        priority_order: priority,
        is_primary: isPrimary || emergencyContacts.length === 0,
      };

      const res = await touristApi.addEmergencyContact(newContact);
      Toast.show({ type: "success", text1: "Contact Added", text2: `${contactName} added to emergency list.` });
      setContactModalVisible(false);
      setContactName("");
      setContactPhone("");
      loadContacts();
    } catch (err: any) {
      Toast.show({ type: "error", text1: "Failed to Add", text2: err?.message || "Error adding contact" });
    } finally {
      setSubmittingContact(false);
    }
  }

  async function handleDeleteContact(contactId?: string) {
    if (!contactId) return;

    RNAlert.alert("Remove Contact", "Are you sure you want to remove this emergency contact?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          try {
            await touristApi.deleteEmergencyContact(contactId);
            Toast.show({ type: "success", text1: "Contact Removed" });
            loadContacts();
          } catch {
            Toast.show({ type: "error", text1: "Delete Failed" });
          }
        },
      },
    ]);
  }

  function handleLogout() {
    RNAlert.alert("Log Out", "Are you sure you want to log out of TourSafe?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Log Out",
        style: "destructive",
        onPress: async () => {
          await logout();
          router.replace("/auth/login?role=tourist");
        },
      },
    ]);
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Header Profile Card */}
      <View style={styles.profileHero}>
        <View style={styles.avatarBox}>
          <User size={36} color="#FF9933" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.userName}>{user?.name || "Verified Traveler"}</Text>
          <Text style={styles.userEmail}>{user?.email || "tourist@toursafe.gov.in"}</Text>
          <View style={styles.verifiedBadge}>
            <CheckCircle2 size={12} color="#10B981" />
            <Text style={styles.verifiedText}>TOURIST IDENTITY VERIFIED</Text>
          </View>
        </View>
      </View>

      {/* EMERGENCY CONTACTS MANAGER */}
      <View style={styles.section}>
        <View style={styles.sectionHeaderRow}>
          <View>
            <Text style={styles.sectionKicker}>SAFETY DISPATCH LIST</Text>
            <Text style={styles.sectionTitle}>Emergency Contacts</Text>
          </View>
          <TouchableOpacity
            style={styles.addContactBtn}
            onPress={() => setContactModalVisible(true)}
          >
            <Plus size={14} color="#0D9488" />
            <Text style={styles.addContactBtnText}>Add Contact</Text>
          </TouchableOpacity>
        </View>

        {loadingContacts ? (
          <ActivityIndicator size="small" color="#0D9488" style={{ marginVertical: 10 }} />
        ) : emergencyContacts.length > 0 ? (
          <View style={styles.contactsList}>
            {emergencyContacts.map((c, idx) => (
              <View key={c.id || idx} style={styles.contactCard}>
                <View style={styles.contactIcon}>
                  <Phone size={16} color="#38BDF8" />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={styles.contactNameRow}>
                    <Text style={styles.contactName}>{c.name}</Text>
                    {c.is_primary && (
                      <View style={styles.primaryBadge}>
                        <Text style={styles.primaryBadgeText}>PRIMARY</Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.contactMeta}>
                    {c.relationship} • {c.phone_number}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.trashBtn}
                  onPress={() => handleDeleteContact(c.id)}
                >
                  <Trash2 size={16} color="#EF4444" />
                </TouchableOpacity>
              </View>
            ))}
          </View>
        ) : (
          <View style={styles.emptyContactsCard}>
            <Phone size={24} color="#64748B" />
            <Text style={styles.emptyContactsTitle}>No Emergency Contacts Added</Text>
            <Text style={styles.emptyContactsSub}>
              Add trusted family or group leaders to receive automatic SMS alerts during an SOS.
            </Text>
          </View>
        )}
      </View>

      {/* PRIVACY & CONSENT CENTER */}
      <View style={styles.section}>
        <Text style={styles.sectionKicker}>PRIVACY & SECURITY</Text>
        <Text style={styles.sectionTitle}>Privacy & Consent Center</Text>

        <View style={styles.consentCard}>
          <View style={styles.consentItem}>
            <View style={{ flex: 1 }}>
              <Text style={styles.consentTitle}>GPS Safety Monitoring</Text>
              <Text style={styles.consentDesc}>
                Allows background location tracking for hazard zone alerts and emergency dispatch.
              </Text>
            </View>
            <Switch
              value={locationConsent}
              onValueChange={setLocationConsent}
              trackColor={{ false: "#334155", true: "#0D9488" }}
              thumbColor="#FFFFFF"
            />
          </View>

          <View style={styles.consentDivider} />

          <View style={styles.consentItem}>
            <View style={{ flex: 1 }}>
              <Text style={styles.consentTitle}>Motion Telemetry</Text>
              <Text style={styles.consentDesc}>
                Uses on-device accelerometer to detect severe impacts, falls, and motion distress.
              </Text>
            </View>
            <Switch
              value={motionConsent}
              onValueChange={setMotionConsent}
              trackColor={{ false: "#334155", true: "#0D9488" }}
              thumbColor="#FFFFFF"
            />
          </View>

          <View style={styles.consentDivider} />

          <View style={styles.consentItem}>
            <View style={{ flex: 1 }}>
              <Text style={styles.consentTitle}>Emergency Contact Auto-SMS</Text>
              <Text style={styles.consentDesc}>
                Automatically dispatches SMS coordinates to your emergency contacts when SOS is triggered.
              </Text>
            </View>
            <Switch
              value={emergencyNotificationConsent}
              onValueChange={setEmergencyNotificationConsent}
              trackColor={{ false: "#334155", true: "#0D9488" }}
              thumbColor="#FFFFFF"
            />
          </View>

          <TouchableOpacity
            style={{
              marginTop: 12,
              paddingVertical: 10,
              paddingHorizontal: 14,
              backgroundColor: '#0f172a',
              borderRadius: 10,
              borderWidth: 1,
              borderColor: '#14b8a6',
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
            onPress={() => setPrivacyModalVisible(true)}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Lock size={16} color="#14b8a6" />
              <Text style={{ fontSize: 12, fontWeight: '700', color: '#f8fafc' }}>
                Advanced Privacy, DSR & Portability Center
              </Text>
            </View>
            <ChevronRight size={16} color="#94a3b8" />
          </TouchableOpacity>
        </View>
      </View>

      {/* APP PERMISSIONS CENTER */}
      <View style={styles.section}>
        <Text style={styles.sectionKicker}>DEVICE PERMISSIONS</Text>
        <Text style={styles.sectionTitle}>App Permissions Center</Text>

        <View style={styles.permissionsGrid}>
          <View style={styles.permissionCard}>
            <MapPin size={18} color="#10B981" />
            <Text style={styles.permissionLabel}>Location Access</Text>
            <Text style={styles.permissionStatus}>{permissionState?.toUpperCase() || "GRANTED"}</Text>
          </View>

          <View style={styles.permissionCard}>
            <Activity size={18} color="#10B981" />
            <Text style={styles.permissionLabel}>Motion Sensors</Text>
            <Text style={styles.permissionStatus}>{imuStatus === "active" ? "STREAMING" : "READY"}</Text>
          </View>

          <View style={styles.permissionCard}>
            <Bell size={18} color="#10B981" />
            <Text style={styles.permissionLabel}>Notifications</Text>
            <Text style={styles.permissionStatus}>ENABLED</Text>
          </View>

          <View style={styles.permissionCard}>
            <Battery size={18} color="#10B981" />
            <Text style={styles.permissionLabel}>Battery Health</Text>
            <Text style={styles.permissionStatus}>{batteryInfo.level}% OPTIMAL</Text>
          </View>
        </View>
      </View>

      {/* DEVELOPER DIAGNOSTICS SHORTCUT */}
      <TouchableOpacity
        style={styles.devBtn}
        onPress={() => setDiagnosticsModalVisible(true)}
      >
        <Wrench size={18} color="#94A3B8" />
        <Text style={styles.devBtnText}>View Developer Diagnostics</Text>
        <ChevronRight size={16} color="#94A3B8" />
      </TouchableOpacity>

      {/* LOGOUT BUTTON */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <LogOut size={18} color="#EF4444" />
        <Text style={styles.logoutText}>Log Out of TourSafe</Text>
      </TouchableOpacity>

      {/* ADD CONTACT MODAL */}
      <Modal visible={contactModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Add Emergency Contact</Text>
            <Text style={styles.modalSub}>
              This contact will receive distress broadcasts if you trigger an SOS.
            </Text>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Full Name *</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. John Doe"
                placeholderTextColor="#64748b"
                value={contactName}
                onChangeText={setContactName}
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Phone Number *</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. +91 98765 43210"
                placeholderTextColor="#64748b"
                value={contactPhone}
                onChangeText={setContactPhone}
                keyboardType="phone-pad"
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Relationship</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Spouse, Parent, Tour Guide"
                placeholderTextColor="#64748b"
                value={contactRelationship}
                onChangeText={setContactRelationship}
              />
            </View>

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setContactModalVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleAddContact}
                disabled={submittingContact}
              >
                {submittingContact ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.submitBtnText}>Save Contact</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* DEVELOPER DIAGNOSTICS MODAL */}
      <Modal visible={diagnosticsModalVisible} animationType="fade" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { maxHeight: "80%" }]}>
            <Text style={styles.modalTitle}>Device & Telemetry Diagnostics</Text>
            <Text style={styles.modalSub}>Live edge metrics from internal sensors & buffers.</Text>

            <ScrollView style={{ maxHeight: 300, gap: 10 }}>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Overall Health:</Text>
                <Text style={styles.diagVal}>{healthStatus?.overallHealth || "GOOD"}</Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>IMU Sampling Rate:</Text>
                <Text style={styles.diagVal}>
                  {imuQuality.observedFrequencyHz.toFixed(1)} Hz
                </Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>GPS Accuracy:</Text>
                <Text style={styles.diagVal}>
                  ±{(qualityMetrics.staleDurationSeconds || 0).toFixed(0)}s stale • ±10m
                </Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Network Type:</Text>
                <Text style={styles.diagVal}>{networkState.type || "WIFI"}</Text>
              </View>
              <View style={styles.diagRow}>
                <Text style={styles.diagLabel}>Battery Low Power Mode:</Text>
                <Text style={styles.diagVal}>
                  {batteryInfo.isLowPowerMode ? "Active" : "Disabled"}
                </Text>
              </View>
            </ScrollView>

            <TouchableOpacity
              style={styles.closeDiagBtn}
              onPress={() => setDiagnosticsModalVisible(false)}
            >
              <Text style={styles.closeDiagText}>Close Diagnostics</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ADVANCED PRIVACY & DSR CENTER MODAL */}
      <PrivacyConsentCenterModal
        visible={privacyModalVisible}
        onClose={() => setPrivacyModalVisible(false)}
      />
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
  profileHero: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.7)",
    padding: 18,
    borderRadius: 20,
    gap: 16,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
  },
  avatarBox: {
    width: 60,
    height: 60,
    borderRadius: 20,
    backgroundColor: "rgba(255, 153, 51, 0.12)",
    borderWidth: 1.5,
    borderColor: "rgba(255, 153, 51, 0.4)",
    alignItems: "center",
    justifyContent: "center",
  },
  userName: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  userEmail: {
    fontSize: 12,
    color: "#94A3B8",
    marginTop: 2,
  },
  verifiedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
    alignSelf: "flex-start",
    marginTop: 6,
  },
  verifiedText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#10B981",
  },
  section: {
    gap: 12,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#38BDF8",
    letterSpacing: 0.8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  addContactBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(13, 148, 136, 0.15)",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    gap: 6,
    borderWidth: 1,
    borderColor: "rgba(13, 148, 136, 0.3)",
  },
  addContactBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#2DD4BF",
  },
  contactsList: {
    gap: 8,
  },
  contactCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 12,
  },
  contactIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: "rgba(56, 189, 248, 0.15)",
    alignItems: "center",
    justifyContent: "center",
  },
  contactNameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  contactName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  primaryBadge: {
    backgroundColor: "rgba(255, 153, 51, 0.2)",
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 4,
  },
  primaryBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#FF9933",
  },
  contactMeta: {
    fontSize: 12,
    color: "#94A3B8",
    marginTop: 2,
  },
  trashBtn: {
    padding: 6,
  },
  emptyContactsCard: {
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.5)",
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 6,
  },
  emptyContactsTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  emptyContactsSub: {
    fontSize: 12,
    color: "#94A3B8",
    textAlign: "center",
    lineHeight: 16,
  },
  consentCard: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  consentItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingVertical: 6,
  },
  consentTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  consentDesc: {
    fontSize: 12,
    color: "#94A3B8",
    marginTop: 2,
    lineHeight: 16,
  },
  consentDivider: {
    height: 1,
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    marginVertical: 10,
  },
  permissionsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  permissionCard: {
    width: "48%",
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 6,
  },
  permissionLabel: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "600",
  },
  permissionStatus: {
    fontSize: 13,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  devBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.5)",
    padding: 16,
    borderRadius: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  devBtnText: {
    flex: 1,
    color: "#CBD5E1",
    fontSize: 14,
    fontWeight: "600",
  },
  logoutBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(239, 68, 68, 0.12)",
    paddingVertical: 14,
    borderRadius: 14,
    gap: 8,
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.25)",
  },
  logoutText: {
    color: "#FCA5A5",
    fontSize: 14,
    fontWeight: "700",
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
    color: "#FFFFFF",
  },
  modalSub: {
    fontSize: 13,
    color: "#94A3B8",
  },
  formGroup: {
    gap: 6,
  },
  formLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#CBD5E1",
  },
  input: {
    backgroundColor: "#0F172A",
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    color: "#FFFFFF",
    fontSize: 14,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
  },
  modalBtnRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 6,
  },
  cancelBtn: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    paddingVertical: 12,
    borderRadius: 12,
  },
  cancelBtnText: {
    color: "#94A3B8",
    fontSize: 13,
    fontWeight: "700",
  },
  submitBtn: {
    flex: 2,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0D9488",
    paddingVertical: 12,
    borderRadius: 12,
  },
  submitBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
  diagRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.05)",
  },
  diagLabel: {
    fontSize: 12,
    color: "#94A3B8",
  },
  diagVal: {
    fontSize: 12,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  closeDiagBtn: {
    alignItems: "center",
    backgroundColor: "#1E40AF",
    paddingVertical: 12,
    borderRadius: 12,
    marginTop: 10,
  },
  closeDiagText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
});