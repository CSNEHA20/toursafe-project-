import React, { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { realtimeClient } from "@/lib/realtimeClient";
import { NotificationCenterModal } from "./NotificationCenterModal";

interface Props {
  apiBaseUrl?: string;
  authToken?: string;
}

export function NotificationBellButton({ apiBaseUrl = "http://localhost:8000", authToken }: Props) {
  const [modalVisible, setModalVisible] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchUnread = async () => {
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
      const res = await fetch(`${apiBaseUrl}/api/v1/notifications/unread-count`, { headers });
      if (res.ok) {
        const data = await res.json();
        setUnreadCount(data.unread_count || 0);
      }
    } catch {
      // offline/dev fallback
    }
  };

  useEffect(() => {
    fetchUnread();
    const unsub = realtimeClient.onEvent("notification.created", () => {
      setUnreadCount((prev) => prev + 1);
    });
    return () => {
      unsub();
    };
  }, [authToken]);

  return (
    <>
      <TouchableOpacity
        style={styles.btn}
        onPress={() => setModalVisible(true)}
        activeOpacity={0.7}
      >
        <Ionicons name="notifications-outline" size={20} color="#F8FAFC" />
        {unreadCount > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>
              {unreadCount > 99 ? "99+" : unreadCount}
            </Text>
          </View>
        )}
      </TouchableOpacity>

      <NotificationCenterModal
        visible={modalVisible}
        onClose={() => {
          setModalVisible(false);
          fetchUnread();
        }}
        apiBaseUrl={apiBaseUrl}
        authToken={authToken}
      />
    </>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(15, 23, 42, 0.75)",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  badge: {
    position: "absolute",
    top: -2,
    right: -2,
    backgroundColor: "#EF4444",
    borderRadius: 8,
    minWidth: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  badgeText: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: "700",
  },
});
