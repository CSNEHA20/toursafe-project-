/**
 * TourSafe Trips & Itinerary Management Screen
 * Complete lifecycle for tourist journeys:
 * - Active Trip tracking & Waypoint progress
 * - Create Trip with date ordering & required field validation
 * - Chronological Itinerary stops with add/complete actions
 * - Trip History & safe completion flow
 */

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Modal,
  ActivityIndicator,
  Alert as RNAlert,
} from "react-native";
import { useTripStore } from "@/store/tripStore";
import { useLocationStore } from "@/store/locationStore";
import { trackingSessionService } from "@/lib/tracking-session/trackingSessionService";
import {
  MapPin,
  Calendar,
  Plus,
  Compass,
  CheckCircle2,
  Clock,
  Navigation,
  Trash2,
  Check,
  ChevronRight,
  Sparkles,
  AlertCircle,
  Flag,
} from "lucide-react-native";
import Toast from "react-native-toast-message";
import type { TouristTrip, TripItineraryStop } from "@/types";

export default function ItineraryScreen() {
  const { trips, activeTrip, upcomingTrips, completedTrips, loading, fetchTrips, createTrip, addStopToTrip, completeActiveTrip } = useTripStore();
  const { trackingStatus } = useLocationStore();

  const [activeTab, setActiveTab] = useState<"active" | "upcoming" | "completed">("active");
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [addStopModalVisible, setAddStopModalVisible] = useState(false);

  // Create Trip form state
  const [tripTitle, setTripTitle] = useState("");
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [endDate, setEndDate] = useState(
    new Date(Date.now() + 5 * 86400000).toISOString().split("T")[0]
  );
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Add Stop form state
  const [stopName, setStopName] = useState("");
  const [stopLocation, setStopLocation] = useState("");
  const [stopTime, setStopTime] = useState("10:00 AM");

  useEffect(() => {
    fetchTrips();
  }, []);

  async function handleCreateTrip() {
    if (!tripTitle.trim()) {
      Toast.show({ type: "error", text1: "Validation Error", text2: "Trip title is required." });
      return;
    }
    if (!destination.trim()) {
      Toast.show({ type: "error", text1: "Validation Error", text2: "Destination is required." });
      return;
    }
    if (new Date(endDate) < new Date(startDate)) {
      Toast.show({ type: "error", text1: "Invalid Dates", text2: "End date cannot be earlier than start date." });
      return;
    }

    setSubmitting(true);
    try {
      const created = await createTrip({
        title: tripTitle.trim(),
        destination: destination.trim(),
        start_date: startDate,
        end_date: endDate,
        description: description.trim() || undefined,
        status: "active",
      });

      if (created) {
        Toast.show({ type: "success", text1: "Trip Created", text2: `Active journey set to ${destination}` });
        setCreateModalVisible(false);
        resetTripForm();
      }
    } catch (err: any) {
      Toast.show({ type: "error", text1: "Creation Failed", text2: err?.message || "Could not create trip" });
    } finally {
      setSubmitting(false);
    }
  }

  function resetTripForm() {
    setTripTitle("");
    setDestination("");
    setDescription("");
  }

  async function handleAddStop() {
    if (!stopName.trim() || !activeTrip) {
      Toast.show({ type: "error", text1: "Validation Error", text2: "Waypoint name is required." });
      return;
    }

    setSubmitting(true);
    try {
      const newStop: TripItineraryStop = {
        name: stopName.trim(),
        location: stopLocation.trim() || stopName.trim(),
        planned_arrival: stopTime.trim(),
        status: "pending",
        order_index: (activeTrip.itinerary_stops?.length || 0) + 1,
      };

      await addStopToTrip(activeTrip.id, newStop);
      Toast.show({ type: "success", text1: "Waypoint Added", text2: `${stopName} added to itinerary.` });
      setAddStopModalVisible(false);
      setStopName("");
      setStopLocation("");
    } catch (err: any) {
      Toast.show({ type: "error", text1: "Error", text2: err?.message || "Failed to add waypoint" });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCompleteTrip() {
    RNAlert.alert(
      "Complete Journey",
      "Are you sure you want to mark this trip as completed? This will conclude tracking and archive your itinerary history.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Yes, Complete Trip",
          style: "destructive",
          onPress: async () => {
            await trackingSessionService.stopTracking();
            const success = await completeActiveTrip();
            if (success) {
              Toast.show({ type: "success", text1: "Trip Safely Completed", text2: "Journey archived to completed trips." });
              setActiveTab("completed");
            }
          },
        },
      ]
    );
  }

  return (
    <View style={styles.container}>
      {/* Header with Title & Create Trip Button */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerKicker}>TOURIST JOURNEY PLANNER</Text>
          <Text style={styles.headerTitle}>Trips & Itinerary</Text>
        </View>
        <TouchableOpacity
          style={styles.newTripBtn}
          onPress={() => setCreateModalVisible(true)}
        >
          <Plus size={16} color="#fff" />
          <Text style={styles.newTripBtnText}>New Trip</Text>
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === "active" && styles.tabItemActive]}
          onPress={() => setActiveTab("active")}
        >
          <Text style={[styles.tabText, activeTab === "active" && styles.tabTextActive]}>
            Active Journey {activeTrip ? "•" : ""}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === "upcoming" && styles.tabItemActive]}
          onPress={() => setActiveTab("upcoming")}
        >
          <Text style={[styles.tabText, activeTab === "upcoming" && styles.tabTextActive]}>
            Upcoming ({upcomingTrips.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === "completed" && styles.tabItemActive]}
          onPress={() => setActiveTab("completed")}
        >
          <Text style={[styles.tabText, activeTab === "completed" && styles.tabTextActive]}>
            Completed ({completedTrips.length})
          </Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#0d9488" />
          <Text style={styles.loadingText}>Loading itinerary details…</Text>
        </View>
      ) : (
        <ScrollView style={styles.content} contentContainerStyle={styles.scrollContent}>
          {/* TAB 1: ACTIVE TRIP */}
          {activeTab === "active" && (
            <>
              {activeTrip ? (
                <View style={styles.activeTripSection}>
                  {/* Hero Card */}
                  <View style={styles.heroCard}>
                    <View style={styles.heroHeader}>
                      <View style={{ flex: 1 }}>
                        <View style={styles.heroBadge}>
                          <Text style={styles.heroBadgeText}>LIVE IN PROGRESS</Text>
                        </View>
                        <Text style={styles.heroTitle}>{activeTrip.title}</Text>
                        <View style={styles.heroMetaRow}>
                          <MapPin size={15} color="#38bdf8" />
                          <Text style={styles.heroMetaText}>{activeTrip.destination}</Text>
                          <Text style={styles.heroDot}>•</Text>
                          <Calendar size={15} color="#94a3b8" />
                          <Text style={styles.heroMetaText}>
                            {new Date(activeTrip.start_date).toLocaleDateString()} –{" "}
                            {new Date(activeTrip.end_date).toLocaleDateString()}
                          </Text>
                        </View>
                      </View>
                      <TouchableOpacity
                        style={styles.completeBtn}
                        onPress={handleCompleteTrip}
                      >
                        <CheckCircle2 size={16} color="#ef4444" />
                        <Text style={styles.completeBtnText}>End Trip</Text>
                      </TouchableOpacity>
                    </View>

                    {activeTrip.description ? (
                      <Text style={styles.heroDesc}>{activeTrip.description}</Text>
                    ) : null}

                    {/* Live Tracking Status Bar */}
                    <View style={styles.trackingStatusBar}>
                      <Navigation
                        size={16}
                        color={trackingStatus === "active" ? "#10b981" : "#94a3b8"}
                      />
                      <Text style={styles.trackingStatusText}>
                        {trackingStatus === "active"
                          ? "GPS Safety Monitoring: ACTIVE"
                          : "GPS Safety Monitoring: STANDBY"}
                      </Text>
                    </View>
                  </View>

                  {/* Itinerary Waypoints Header */}
                  <View style={styles.waypointsHeader}>
                    <View>
                      <Text style={styles.waypointsTitle}>Chronological Waypoints</Text>
                      <Text style={styles.waypointsSub}>
                        {activeTrip.itinerary_stops?.length || 0} scheduled stops
                      </Text>
                    </View>
                    <TouchableOpacity
                      style={styles.addStopBtn}
                      onPress={() => setAddStopModalVisible(true)}
                    >
                      <Plus size={14} color="#0d9488" />
                      <Text style={styles.addStopBtnText}>Add Stop</Text>
                    </TouchableOpacity>
                  </View>

                  {/* Waypoint List */}
                  {activeTrip.itinerary_stops && activeTrip.itinerary_stops.length > 0 ? (
                    <View style={styles.timelineList}>
                      {activeTrip.itinerary_stops.map((stop, index) => {
                        const isFirst = index === 0;
                        const isLast = index === (activeTrip.itinerary_stops?.length ?? 1) - 1;
                        const isCompleted = stop.status === "reached";


                        return (
                          <View key={index} style={styles.timelineItem}>
                            {/* Timeline Connector */}
                            <View style={styles.timelineColumn}>
                              <View
                                style={[
                                  styles.timelineDot,
                                  isCompleted
                                    ? styles.dotCompleted
                                    : isFirst
                                    ? styles.dotCurrent
                                    : styles.dotPending,
                                ]}
                              >
                                {isCompleted ? (
                                  <Check size={12} color="#fff" />
                                ) : (
                                  <Text style={styles.dotNumber}>{index + 1}</Text>
                                )}
                              </View>
                              {!isLast && <View style={styles.timelineLine} />}
                            </View>

                            {/* Waypoint Card */}
                            <View style={styles.stopCard}>
                              <View style={styles.stopCardTop}>
                                <Text style={styles.stopName}>{stop.name}</Text>
                                <View
                                  style={[
                                    styles.stopStatusBadge,
                                    isCompleted
                                      ? styles.statusReached
                                      : styles.statusPending,
                                  ]}
                                >
                                  <Text
                                    style={[
                                      styles.stopStatusText,
                                      isCompleted
                                        ? styles.statusReachedText
                                        : styles.statusPendingText,
                                    ]}
                                  >
                                    {isCompleted ? "Visited" : "Pending"}
                                  </Text>
                                </View>
                              </View>

                              {stop.location ? (
                                <View style={styles.stopMetaRow}>
                                  <MapPin size={13} color="#94a3b8" />
                                  <Text style={styles.stopLocationText}>{stop.location}</Text>
                                </View>
                              ) : null}

                              {stop.planned_arrival ? (
                                <View style={styles.stopMetaRow}>
                                  <Clock size={13} color="#94a3b8" />
                                  <Text style={styles.stopTimeText}>
                                    Planned: {stop.planned_arrival}
                                  </Text>
                                </View>
                              ) : null}
                            </View>
                          </View>
                        );
                      })}
                    </View>
                  ) : (
                    <View style={styles.emptyStopsCard}>
                      <Compass size={32} color="#64748b" />
                      <Text style={styles.emptyStopsTitle}>No stops added yet</Text>
                      <Text style={styles.emptyStopsSub}>
                        Add your planned tourist attractions, viewpoints, or hotels.
                      </Text>
                      <TouchableOpacity
                        style={styles.emptyAddBtn}
                        onPress={() => setAddStopModalVisible(true)}
                      >
                        <Plus size={14} color="#fff" />
                        <Text style={styles.emptyAddBtnText}>Add First Waypoint</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              ) : (
                <View style={styles.emptyTripsCard}>
                  <Compass size={48} color="#FF9933" />
                  <Text style={styles.emptyTripsTitle}>No Active Journey</Text>
                  <Text style={styles.emptyTripsDesc}>
                    You are not currently on an active trip. Create a new journey to enable automatic waypoint tracking and location safety corridors.
                  </Text>
                  <TouchableOpacity
                    style={styles.createFirstTripBtn}
                    onPress={() => setCreateModalVisible(true)}
                  >
                    <Plus size={18} color="#fff" />
                    <Text style={styles.createFirstTripText}>Plan a New Journey</Text>
                  </TouchableOpacity>
                </View>
              )}
            </>
          )}

          {/* TAB 2: UPCOMING TRIPS */}
          {activeTab === "upcoming" && (
            <View style={styles.tripList}>
              {upcomingTrips.length > 0 ? (
                upcomingTrips.map((t: TouristTrip) => (
                  <View key={t.id} style={styles.tripListItem}>
                    <View style={styles.tripListTop}>
                      <Text style={styles.tripListTitle}>{t.title}</Text>
                      <View style={styles.upcomingBadge}>
                        <Text style={styles.upcomingBadgeText}>Upcoming</Text>
                      </View>
                    </View>
                    <View style={styles.tripListMeta}>
                      <MapPin size={14} color="#0d9488" />
                      <Text style={styles.tripListMetaText}>{t.destination}</Text>
                      <Text style={styles.heroDot}>•</Text>
                      <Calendar size={14} color="#64748b" />
                      <Text style={styles.tripListMetaText}>
                        {new Date(t.start_date).toLocaleDateString()}
                      </Text>
                    </View>
                  </View>
                ))
              ) : (
                <View style={styles.emptyTripsCard}>
                  <Calendar size={40} color="#64748b" />
                  <Text style={styles.emptyTripsTitle}>No Upcoming Trips</Text>
                  <Text style={styles.emptyTripsDesc}>
                    Your scheduled future trips will appear here.
                  </Text>
                </View>
              )}
            </View>
          )}

          {/* TAB 3: COMPLETED TRIPS */}
          {activeTab === "completed" && (
            <View style={styles.tripList}>
              {completedTrips.length > 0 ? (
                completedTrips.map((t: TouristTrip) => (
                  <View key={t.id} style={styles.tripListItem}>
                    <View style={styles.tripListTop}>
                      <Text style={styles.tripListTitle}>{t.title}</Text>
                      <View style={styles.completedBadge}>
                        <CheckCircle2 size={12} color="#10b981" />
                        <Text style={styles.completedBadgeText}>Completed</Text>
                      </View>
                    </View>
                    <View style={styles.tripListMeta}>
                      <MapPin size={14} color="#0d9488" />
                      <Text style={styles.tripListMetaText}>{t.destination}</Text>
                      <Text style={styles.heroDot}>•</Text>
                      <Calendar size={14} color="#64748b" />
                      <Text style={styles.tripListMetaText}>
                        {new Date(t.start_date).toLocaleDateString()} –{" "}
                        {new Date(t.end_date).toLocaleDateString()}
                      </Text>
                    </View>
                  </View>
                ))
              ) : (
                <View style={styles.emptyTripsCard}>
                  <CheckCircle2 size={40} color="#64748b" />
                  <Text style={styles.emptyTripsTitle}>No Past Completed Trips</Text>
                  <Text style={styles.emptyTripsDesc}>
                    When you conclude a journey, it will be securely archived here with its safety timeline.
                  </Text>
                </View>
              )}
            </View>
          )}

        </ScrollView>
      )}

      {/* CREATE TRIP MODAL */}
      <Modal visible={createModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Plan New Journey</Text>
            <Text style={styles.modalSub}>
              Set up your destination and dates for proactive safety tracking.
            </Text>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Trip Title *</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Goa Coastal Vacation"
                placeholderTextColor="#64748b"
                value={tripTitle}
                onChangeText={setTripTitle}
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Destination / Region *</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. North Goa & Panaji"
                placeholderTextColor="#64748b"
                value={destination}
                onChangeText={setDestination}
              />
            </View>

            <View style={styles.formRow}>
              <View style={[styles.formGroup, { flex: 1 }]}>
                <Text style={styles.formLabel}>Start Date (YYYY-MM-DD)</Text>
                <TextInput
                  style={styles.input}
                  value={startDate}
                  onChangeText={setStartDate}
                />
              </View>
              <View style={[styles.formGroup, { flex: 1 }]}>
                <Text style={styles.formLabel}>End Date (YYYY-MM-DD)</Text>
                <TextInput
                  style={styles.input}
                  value={endDate}
                  onChangeText={setEndDate}
                />
              </View>
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Notes / Accommodations (Optional)</Text>
              <TextInput
                style={[styles.input, { height: 70, textAlignVertical: "top" }]}
                placeholder="e.g. Staying at Beachfront Resort..."
                placeholderTextColor="#64748b"
                value={description}
                onChangeText={setDescription}
                multiline
              />
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setCreateModalVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleCreateTrip}
                disabled={submitting}
              >
                {submitting ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.submitBtnText}>Create Active Trip</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ADD STOP MODAL */}
      <Modal visible={addStopModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Add Waypoint Stop</Text>
            <Text style={styles.modalSub}>
              Add an attraction, monument, or planned waypoint to your itinerary.
            </Text>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Stop Name *</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Fort Aguada Viewpoint"
                placeholderTextColor="#64748b"
                value={stopName}
                onChangeText={setStopName}
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Location / Landmark</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Candolim, Goa"
                placeholderTextColor="#64748b"
                value={stopLocation}
                onChangeText={setStopLocation}
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Planned Time</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 02:30 PM"
                placeholderTextColor="#64748b"
                value={stopTime}
                onChangeText={setStopTime}
              />
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setAddStopModalVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleAddStop}
                disabled={submitting}
              >
                {submitting ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.submitBtnText}>Add to Timeline</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B132B",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingTop: 54,
    paddingBottom: 14,
  },
  headerKicker: {
    fontSize: 11,
    fontWeight: "800",
    color: "#38BDF8",
    letterSpacing: 0.8,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 2,
  },
  newTripBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1E40AF",
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 12,
    gap: 6,
  },
  newTripBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
  tabBar: {
    flexDirection: "row",
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.08)",
  },
  tabItem: {
    paddingVertical: 12,
    marginRight: 20,
  },
  tabItemActive: {
    borderBottomWidth: 2,
    borderBottomColor: "#FF9933",
  },
  tabText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#94A3B8",
  },
  tabTextActive: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 30,
  },
  loadingText: {
    color: "#94A3B8",
    fontSize: 14,
    marginTop: 12,
  },
  activeTripSection: {
    gap: 20,
  },
  heroCard: {
    backgroundColor: "rgba(30, 41, 59, 0.7)",
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
    gap: 12,
  },
  heroHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  heroBadge: {
    backgroundColor: "rgba(56, 189, 248, 0.15)",
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 8,
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: "rgba(56, 189, 248, 0.3)",
    marginBottom: 6,
  },
  heroBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#38BDF8",
    letterSpacing: 0.6,
  },
  heroTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  heroMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 6,
  },
  heroMetaText: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "500",
  },
  heroDot: {
    color: "#64748b",
  },
  heroDesc: {
    fontSize: 13,
    color: "#CBD5E1",
    lineHeight: 18,
  },
  completeBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(239, 68, 68, 0.12)",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    gap: 6,
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.25)",
  },
  completeBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#FCA5A5",
  },
  trackingStatusBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    padding: 10,
    borderRadius: 10,
    gap: 8,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.05)",
  },
  trackingStatusText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#E2E8F0",
  },
  waypointsHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  waypointsTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  waypointsSub: {
    fontSize: 12,
    color: "#94A3B8",
    marginTop: 2,
  },
  addStopBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(13, 148, 136, 0.15)",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 10,
    gap: 6,
    borderWidth: 1,
    borderColor: "rgba(13, 148, 136, 0.3)",
  },
  addStopBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#2DD4BF",
  },
  timelineList: {
    gap: 0,
  },
  timelineItem: {
    flexDirection: "row",
    gap: 14,
  },
  timelineColumn: {
    alignItems: "center",
    width: 28,
  },
  timelineDot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
  },
  dotCompleted: {
    backgroundColor: "#059669",
  },
  dotCurrent: {
    backgroundColor: "#1E40AF",
  },
  dotPending: {
    backgroundColor: "#334155",
  },
  dotNumber: {
    color: "#fff",
    fontSize: 11,
    fontWeight: "700",
  },
  timelineLine: {
    width: 2,
    flex: 1,
    backgroundColor: "rgba(255, 255, 255, 0.12)",
    marginVertical: 4,
  },
  stopCard: {
    flex: 1,
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    marginBottom: 14,
    gap: 6,
  },
  stopCardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  stopName: {
    fontSize: 15,
    fontWeight: "700",
    color: "#FFFFFF",
    flex: 1,
  },
  stopStatusBadge: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  statusReached: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
  },
  statusPending: {
    backgroundColor: "rgba(148, 163, 184, 0.15)",
  },
  stopStatusText: {
    fontSize: 10,
    fontWeight: "700",
  },
  statusReachedText: {
    color: "#10b981",
  },
  statusPendingText: {
    color: "#94a3b8",
  },
  stopMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  stopLocationText: {
    fontSize: 12,
    color: "#CBD5E1",
  },
  stopTimeText: {
    fontSize: 12,
    color: "#94A3B8",
  },
  emptyStopsCard: {
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.5)",
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 8,
  },
  emptyStopsTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  emptyStopsSub: {
    fontSize: 12,
    color: "#94A3B8",
    textAlign: "center",
    marginBottom: 8,
  },
  emptyAddBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#0d9488",
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 10,
    gap: 6,
  },
  emptyAddBtnText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
  },
  emptyTripsCard: {
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 20,
    padding: 30,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 12,
  },
  emptyTripsTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  emptyTripsDesc: {
    fontSize: 13,
    color: "#94A3B8",
    textAlign: "center",
    lineHeight: 20,
  },
  createFirstTripBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FF9933",
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 14,
    gap: 8,
    marginTop: 6,
  },
  createFirstTripText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
  },
  tripList: {
    gap: 12,
  },
  tripListItem: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    gap: 8,
  },
  tripListTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  tripListTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  upcomingBadge: {
    backgroundColor: "rgba(56, 189, 248, 0.15)",
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  upcomingBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#38BDF8",
  },
  completedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  completedBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#10b981",
  },
  tripListMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  tripListMetaText: {
    fontSize: 12,
    color: "#94A3B8",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#1E293B",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    borderTopWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.1)",
    gap: 14,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  modalSub: {
    fontSize: 12,
    color: "#94A3B8",
  },
  formGroup: {
    gap: 6,
  },
  formRow: {
    flexDirection: "row",
    gap: 12,
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
  modalButtons: {
    flexDirection: "row",
    gap: 10,
    marginTop: 10,
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
    fontSize: 14,
    fontWeight: "700",
  },
  submitBtn: {
    flex: 2,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#1E40AF",
    paddingVertical: 12,
    borderRadius: 12,
  },
  submitBtnText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
});