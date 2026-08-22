import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  SafeAreaView,
  Platform,
} from "react-native";
import { Bell, X, CheckCircle2, AlertCircle, ArrowRight } from "lucide-react-native";
import { useRouter } from "expo-router";
import { realtimeClient } from "@/lib/realtimeClient";
import type { NotificationRecord, NotificationPriority, NotificationCategory } from "@/types/notification";

interface NotificationCenterProps {
  visible: boolean;
  onClose: () => void;
  apiBaseUrl?: string;
  authToken?: string;
  onSelectNotification?: (notif: NotificationRecord) => void;
}

const DEFAULT_API_BASE = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";

export function NotificationCenterModal({
  visible,
  onClose,
  apiBaseUrl = DEFAULT_API_BASE,
  authToken,
  onSelectNotification,
}: NotificationCenterProps) {
  const router = useRouter();
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [filterTab, setFilterTab] = useState<"ALL" | "UNREAD" | "CRITICAL" | "SAFETY" | "INCIDENT">("ALL");

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const res = await fetch(`${apiBaseUrl}/api/v1/notifications?limit=50`, { headers });
      if (res.ok) {
        const data: NotificationRecord[] = await res.json();
        setNotifications(data);
        const unread = data.filter((n) => !n.is_read).length;
        setUnreadCount(unread);
      }
    } catch (err) {
      console.warn("Failed to fetch notifications:", err);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, authToken]);

  useEffect(() => {
    if (visible) {
      fetchNotifications();
    }
  }, [visible, fetchNotifications]);

  // Subscribe to realtime notification events
  useEffect(() => {
    const unsub = realtimeClient.onEvent("notification.created", (envelope: any) => {
      const payload = envelope.payload || envelope;
      const newNotif: NotificationRecord = {
        notification_id: payload.notification_id || `notif_${Date.now()}`,
        event_id: payload.event_id || `evt_${Date.now()}`,
        recipient_id: payload.user_id || "self",
        recipient_type: "TOURIST",
        channel: "REALTIME",
        priority: (payload.priority as NotificationPriority) || "NORMAL",
        category: (payload.category as NotificationCategory) || "SYSTEM",
        idempotency_key: `rt_${Date.now()}`,
        status: "DELIVERED",
        payload: {
          title: payload.title || "New Notification",
          body: payload.body || "",
          incident_id: payload.incident_id,
          deep_link: payload.deep_link,
          data: payload.data,
        },
        created_at: payload.timestamp || new Date().toISOString(),
        provider: "TourSafeRealtimeProvider",
        retry_count: 0,
        max_retries: 3,
        is_read: false,
      };

      setNotifications((prev) => [newNotif, ...prev]);
      setUnreadCount((prev) => prev + 1);
    });

    return () => {
      unsub();
    };
  }, []);

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      await fetch(`${apiBaseUrl}/api/v1/notifications/${notificationId}/read`, {
        method: "POST",
        headers,
      });

      setNotifications((prev) =>
        prev.map((n) => (n.notification_id === notificationId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.warn("Failed to mark notification read:", err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      await fetch(`${apiBaseUrl}/api/v1/notifications/read-all`, {
        method: "POST",
        headers,
      });

      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.warn("Failed to mark all read:", err);
    }
  };

  const handleItemPress = (notif: NotificationRecord) => {
    if (!notif.is_read) {
      handleMarkAsRead(notif.notification_id);
    }

    if (onSelectNotification) {
      onSelectNotification(notif);
      onClose();
      return;
    }

    if (notif.payload.incident_id) {
      onClose();
      try {
        router.push(`/admin/(tabs)/alerts` as any);
      } catch {
        // Fallback navigation
      }
    }
  };

  const filteredList = notifications.filter((n) => {
    if (filterTab === "UNREAD") return !n.is_read;
    if (filterTab === "CRITICAL") return n.priority === "CRITICAL";
    if (filterTab === "SAFETY") return n.category === "SAFETY" || n.category === "SOS";
    if (filterTab === "INCIDENT") return n.category === "INCIDENT" || n.category === "ASSIGNMENT";
    return true;
  });

  const getPriorityBadgeStyle = (priority: NotificationPriority) => {
    switch (priority) {
      case "CRITICAL":
        return { bg: "rgba(239, 68, 68, 0.15)", text: "#EF4444", border: "rgba(239, 68, 68, 0.3)" };
      case "HIGH":
        return { bg: "rgba(245, 158, 11, 0.15)", text: "#F59E0B", border: "rgba(245, 158, 11, 0.3)" };
      case "NORMAL":
        return { bg: "rgba(16, 185, 129, 0.15)", text: "#10B981", border: "rgba(16, 185, 129, 0.3)" };
      case "LOW":
      default:
        return { bg: "rgba(100, 116, 139, 0.15)", text: "#94A3B8", border: "rgba(100, 116, 139, 0.3)" };
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <SafeAreaView style={styles.modalOverlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <View style={styles.bellIconContainer}>
                <Bell size={18} color="#38BDF8" />
              </View>
              <Text style={styles.headerTitle}>Notifications</Text>
              {unreadCount > 0 && (
                <View style={styles.unreadBadge}>
                  <Text style={styles.unreadBadgeText}>{unreadCount}</Text>
                </View>
              )}
            </View>
            <View style={styles.headerRight}>
              {unreadCount > 0 && (
                <TouchableOpacity onPress={handleMarkAllRead} style={styles.markAllBtn} accessibilityRole="button">
                  <Text style={styles.markAllText}>Mark all read</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityRole="button" accessibilityLabel="Close notifications">
                <X size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>
          </View>

          {/* Filter Tabs */}
          <View style={styles.filterRow}>
            {(["ALL", "UNREAD", "CRITICAL", "SAFETY", "INCIDENT"] as const).map((tab) => (
              <TouchableOpacity
                key={tab}
                onPress={() => setFilterTab(tab)}
                style={[styles.filterChip, filterTab === tab && styles.filterChipActive]}
                accessibilityRole="tab"
                accessibilityState={{ selected: filterTab === tab }}
              >
                <Text style={[styles.filterChipText, filterTab === tab && styles.filterChipTextActive]}>
                  {tab === "ALL" ? "All" : tab === "UNREAD" ? `Unread (${unreadCount})` : tab.charAt(0) + tab.slice(1).toLowerCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Notification List */}
          {loading && notifications.length === 0 ? (
            <View style={styles.centerBox}>
              <ActivityIndicator size="large" color="#38BDF8" />
              <Text style={styles.loadingText}>Syncing notification feed...</Text>
            </View>
          ) : filteredList.length === 0 ? (
            <View style={styles.centerBox}>
              <CheckCircle2 size={44} color="#475569" />
              <Text style={styles.emptyTitle}>No notifications</Text>
              <Text style={styles.emptySubtitle}>You are all caught up with your security and operational alerts.</Text>
            </View>
          ) : (
            <FlatList
              data={filteredList}
              keyExtractor={(item) => item.notification_id}
              contentContainerStyle={styles.listContent}
              renderItem={({ item }) => {
                const pStyle = getPriorityBadgeStyle(item.priority);
                return (
                  <TouchableOpacity
                    style={[styles.card, !item.is_read && styles.cardUnread]}
                    onPress={() => handleItemPress(item)}
                    activeOpacity={0.8}
                    accessibilityRole="button"
                  >
                    <View style={styles.cardHeader}>
                      <View style={styles.cardHeaderLeft}>
                        {!item.is_read && <View style={styles.dotUnread} />}
                        <View style={[styles.priorityBadge, { backgroundColor: pStyle.bg, borderColor: pStyle.border }]}>
                          <Text style={[styles.priorityText, { color: pStyle.text }]}>{item.priority}</Text>
                        </View>
                        <Text style={styles.categoryText}>{item.category}</Text>
                      </View>
                      <Text style={styles.timeText}>
                        {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </Text>
                    </View>

                    <Text style={[styles.cardTitle, !item.is_read && styles.cardTitleUnread]}>
                      {item.payload.title}
                    </Text>
                    <Text style={styles.cardBody} numberOfLines={3}>
                      {item.payload.body}
                    </Text>

                    {item.payload.incident_id && (
                      <View style={styles.actionFooter}>
                        <View style={styles.incidentTag}>
                          <AlertCircle size={14} color="#F59E0B" />
                          <Text style={styles.incidentTagText}>Ref: {item.payload.incident_id}</Text>
                        </View>
                        <Text style={styles.deepLinkText}>View Incident →</Text>
                      </View>
                    )}
                  </TouchableOpacity>
                );
              }}
            />
          )}
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    justifyContent: "flex-end",
  },
  container: {
    flex: 1,
    marginTop: Platform.OS === "ios" ? 44 : 20,
    backgroundColor: "#0B1120",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.06)",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  bellIconContainer: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: "rgba(56, 189, 248, 0.12)",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#F8FAFC",
  },
  unreadBadge: {
    backgroundColor: "#EF4444",
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginLeft: 8,
  },
  unreadBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  headerRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  markAllBtn: {
    marginRight: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  markAllText: {
    fontSize: 12,
    color: "#38BDF8",
    fontWeight: "600",
  },
  closeBtn: {
    padding: 6,
  },
  filterRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255, 255, 255, 0.04)",
  },
  filterChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.06)",
  },
  filterChipActive: {
    backgroundColor: "rgba(56, 189, 248, 0.15)",
    borderColor: "rgba(56, 189, 248, 0.4)",
  },
  filterChipText: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "500",
  },
  filterChipTextActive: {
    color: "#38BDF8",
    fontWeight: "700",
  },
  listContent: {
    padding: 16,
    paddingBottom: 40,
  },
  card: {
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.06)",
  },
  cardUnread: {
    backgroundColor: "rgba(30, 41, 59, 0.8)",
    borderColor: "rgba(56, 189, 248, 0.25)",
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  cardHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  dotUnread: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#38BDF8",
    marginRight: 6,
  },
  priorityBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
    marginRight: 8,
  },
  priorityText: {
    fontSize: 10,
    fontWeight: "700",
  },
  categoryText: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "600",
  },
  timeText: {
    fontSize: 11,
    color: "#64748B",
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#E2E8F0",
    marginBottom: 4,
  },
  cardTitleUnread: {
    color: "#F8FAFC",
    fontWeight: "700",
  },
  cardBody: {
    fontSize: 13,
    color: "#94A3B8",
    lineHeight: 18,
  },
  actionFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.04)",
  },
  incidentTag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  incidentTagText: {
    fontSize: 11,
    color: "#F59E0B",
    fontWeight: "600",
  },
  deepLinkText: {
    fontSize: 12,
    color: "#38BDF8",
    fontWeight: "600",
  },
  centerBox: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  loadingText: {
    color: "#94A3B8",
    fontSize: 13,
    marginTop: 12,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#E2E8F0",
    marginTop: 12,
  },
  emptySubtitle: {
    fontSize: 13,
    color: "#64748B",
    textAlign: "center",
    marginTop: 6,
    lineHeight: 18,
  },
});
