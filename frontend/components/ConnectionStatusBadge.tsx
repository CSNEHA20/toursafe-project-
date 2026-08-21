import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { realtimeClient } from "@/lib/realtimeClient";
import type { RealtimeConnectionState } from "@/types/realtime";

interface Props {
  showLabel?: boolean;
  allowNavigateDev?: boolean;
}

export function ConnectionStatusBadge({
  showLabel = true,
  allowNavigateDev = true,
}: Props) {
  const [state, setState] = useState<RealtimeConnectionState>(
    realtimeClient.getConnectionState()
  );
  const router = useRouter();

  useEffect(() => {
    const unsub = realtimeClient.onStateChange((newState) => {
      setState(newState);
    });
    return unsub;
  }, []);

  const getStatusColor = () => {
    switch (state) {
      case "connected":
        return "#10B981"; // Emerald
      case "connecting":
      case "reconnecting":
        return "#F59E0B"; // Amber
      case "error":
        return "#EF4444"; // Rose/Red
      case "disconnected":
      default:
        return "#64748B"; // Slate/Gray
    }
  };

  const getStatusText = () => {
    switch (state) {
      case "connected":
        return "Live";
      case "connecting":
        return "Connecting";
      case "reconnecting":
        return "Reconnecting";
      case "error":
        return "Offline";
      case "disconnected":
      default:
        return "Disconnected";
    }
  };

  const handlePress = () => {
    if (allowNavigateDev && __DEV__) {
      try {
        router.push("/dev/realtime" as any);
      } catch {
        // ignore navigation if dev route is not in active layout
      }
    }
  };

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={handlePress}
      style={styles.container}
    >
      <View
        style={[
          styles.dot,
          { backgroundColor: getStatusColor() },
        ]}
      />
      {showLabel && (
        <Text style={[styles.label, { color: getStatusColor() }]}>
          {getStatusText()}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.7)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginRight: 6,
  },
  label: {
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.2,
  },
});
