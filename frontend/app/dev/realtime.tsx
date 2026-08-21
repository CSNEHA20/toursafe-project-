import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft, RefreshCw, Send, ShieldAlert, Radio } from "lucide-react-native";
import { realtimeClient } from "@/lib/realtimeClient";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { RealtimeDiagnostics, RealtimeEnvelope } from "@/types/realtime";

export default function RealtimeDevScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [diag, setDiag] = useState<RealtimeDiagnostics>(realtimeClient.getDiagnostics());
  const [eventLogs, setEventLogs] = useState<RealtimeEnvelope[]>([]);
  const [eventType, setEventType] = useState("zone.status_changed");
  const [targetChannel, setTargetChannel] = useState("authority:operations");
  const [customPayload, setCustomPayload] = useState('{"zone_id": "test_zone_1", "status": "active"}');
  const [isSending, setIsSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);

  useEffect(() => {
    const updateStats = () => {
      setDiag(realtimeClient.getDiagnostics());
    };

    const interval = setInterval(updateStats, 1000);
    const unsubState = realtimeClient.onStateChange(updateStats);

    const unsubWildcard = realtimeClient.onEvent("*", (payload, envelope) => {
      setEventLogs((prev) => [envelope, ...prev.slice(0, 49)]);
      updateStats();
    });

    return () => {
      clearInterval(interval);
      unsubState();
      unsubWildcard();
    };
  }, []);

  const handleReconnect = () => {
    realtimeClient.disconnect();
    setTimeout(() => {
      realtimeClient.connect();
    }, 500);
  };

  const handleSendTestEvent = async () => {
    try {
      setIsSending(true);
      setSendResult(null);
      let parsed = {};
      try {
        parsed = JSON.parse(customPayload);
      } catch {
        parsed = { message: customPayload };
      }

      const res = await api.post("/dev/realtime/test-event", {
        event_type: eventType,
        channel: targetChannel || undefined,
        payload: parsed,
      });

      setSendResult(`Success: Dispatched ${res.data.event_id}`);
    } catch (err: any) {
      setSendResult(`Error: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <ArrowLeft color="#fff" size={20} />
        </TouchableOpacity>
        <View>
          <Text style={styles.headerTitle}>Realtime Diagnostics</Text>
          <Text style={styles.headerSubtitle}>WebSocket & Event Bus Telemetry</Text>
        </View>
        <TouchableOpacity onPress={handleReconnect} style={styles.refreshBtn}>
          <RefreshCw color="#38BDF8" size={18} />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
        {/* Status Card */}
        <View style={styles.statusCard}>
          <View style={styles.statusRow}>
            <View style={styles.statusPill}>
              <View
                style={[
                  styles.statusDot,
                  {
                    backgroundColor:
                      diag.state === "connected"
                        ? "#10B981"
                        : diag.state === "reconnecting" || diag.state === "connecting"
                        ? "#F59E0B"
                        : "#EF4444",
                  },
                ]}
              />
              <Text style={styles.statusText}>{diag.state.toUpperCase()}</Text>
            </View>
            <Text style={styles.connId}>
              {diag.connectionId ? diag.connectionId : "No active socket"}
            </Text>
          </View>

          {diag.lastError && (
            <View style={styles.errorBox}>
              <ShieldAlert color="#EF4444" size={16} />
              <Text style={styles.errorText}>{diag.lastError}</Text>
            </View>
          )}
        </View>

        {/* Metrics Grid */}
        <Text style={styles.sectionTitle}>Telemetry & Metrics</Text>
        <View style={styles.grid}>
          <View style={styles.gridCard}>
            <Text style={styles.gridLabel}>User / Role</Text>
            <Text style={styles.gridValue}>
              {user ? `${user.role}` : "Anonymous"}
            </Text>
            <Text style={styles.gridSub}>{user?.email || "No token"}</Text>
          </View>

          <View style={styles.gridCard}>
            <Text style={styles.gridLabel}>Reconnects</Text>
            <Text style={styles.gridValue}>{diag.reconnectCount}</Text>
            <Text style={styles.gridSub}>Total attempts</Text>
          </View>

          <View style={styles.gridCard}>
            <Text style={styles.gridLabel}>Received</Text>
            <Text style={[styles.gridValue, { color: "#38BDF8" }]}>{diag.eventsReceived}</Text>
            <Text style={styles.gridSub}>Frames inbound</Text>
          </View>

          <View style={styles.gridCard}>
            <Text style={styles.gridLabel}>Sent</Text>
            <Text style={[styles.gridValue, { color: "#10B981" }]}>{diag.eventsSent}</Text>
            <Text style={styles.gridSub}>Frames outbound</Text>
          </View>
        </View>

        {/* Subscribed Channels */}
        <Text style={styles.sectionTitle}>Subscribed Channels</Text>
        <View style={styles.channelContainer}>
          {diag.subscribedChannels.length === 0 ? (
            <Text style={styles.noDataText}>No active channel subscriptions</Text>
          ) : (
            diag.subscribedChannels.map((ch) => (
              <View key={ch} style={styles.channelTag}>
                <Radio color="#38BDF8" size={12} style={{ marginRight: 6 }} />
                <Text style={styles.channelTagText}>{ch}</Text>
              </View>
            ))
          )}
        </View>

        {/* Dev Test Event Dispatcher */}
        <Text style={styles.sectionTitle}>Dispatch Test Event (Dev Only)</Text>
        <View style={styles.testCard}>
          <Text style={styles.inputLabel}>Event Type</Text>
          <TextInput
            value={eventType}
            onChangeText={setEventType}
            style={styles.input}
            placeholder="e.g. zone.status_changed"
            placeholderTextColor="#64748B"
          />

          <Text style={styles.inputLabel}>Target Channel (optional)</Text>
          <TextInput
            value={targetChannel}
            onChangeText={setTargetChannel}
            style={styles.input}
            placeholder="e.g. authority:operations"
            placeholderTextColor="#64748B"
          />

          <Text style={styles.inputLabel}>JSON Payload</Text>
          <TextInput
            value={customPayload}
            onChangeText={setCustomPayload}
            style={[styles.input, { height: 60 }]}
            multiline
            placeholder='{"key": "value"}'
            placeholderTextColor="#64748B"
          />

          <TouchableOpacity
            style={styles.sendButton}
            onPress={handleSendTestEvent}
            disabled={isSending}
          >
            {isSending ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Send color="#fff" size={16} style={{ marginRight: 8 }} />
                <Text style={styles.sendButtonText}>Publish to Event Bus</Text>
              </>
            )}
          </TouchableOpacity>

          {sendResult && (
            <Text
              style={[
                styles.resultText,
                { color: sendResult.startsWith("Success") ? "#10B981" : "#EF4444" },
              ]}
            >
              {sendResult}
            </Text>
          )}
        </View>

        {/* Live Event Stream */}
        <Text style={styles.sectionTitle}>Live Event Log ({eventLogs.length})</Text>
        <View style={styles.logsContainer}>
          {eventLogs.length === 0 ? (
            <Text style={styles.noDataText}>Waiting for incoming realtime events...</Text>
          ) : (
            eventLogs.map((evt, idx) => (
              <View key={evt.event_id || idx} style={styles.logItem}>
                <View style={styles.logHeader}>
                  <Text style={styles.logType}>{evt.event_type}</Text>
                  <Text style={styles.logTime}>
                    {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ""}
                  </Text>
                </View>
                <Text style={styles.logSource}>
                  ID: {evt.event_id} | v{evt.version} | {evt.source}
                </Text>
                <Text style={styles.logJson}>
                  {JSON.stringify(evt.payload, null, 2)}
                </Text>
              </View>
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#0B0F17",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderColor: "#1E293B",
  },
  backBtn: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: "#1E293B",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#F8FAFC",
    textAlign: "center",
  },
  headerSubtitle: {
    fontSize: 11,
    color: "#94A3B8",
    textAlign: "center",
  },
  refreshBtn: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: "#1E293B",
  },
  container: {
    flex: 1,
    padding: 16,
  },
  statusCard: {
    backgroundColor: "#1E293B",
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.06)",
  },
  statusRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#0F172A",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#F8FAFC",
  },
  connId: {
    fontSize: 12,
    color: "#94A3B8",
    fontFamily: "monospace",
  },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
    backgroundColor: "rgba(239, 68, 68, 0.1)",
    padding: 8,
    borderRadius: 8,
  },
  errorText: {
    fontSize: 12,
    color: "#EF4444",
    marginLeft: 6,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#CBD5E1",
    marginBottom: 10,
    marginTop: 10,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  gridCard: {
    width: "48%",
    backgroundColor: "#1E293B",
    padding: 12,
    borderRadius: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.04)",
  },
  gridLabel: {
    fontSize: 11,
    color: "#94A3B8",
  },
  gridValue: {
    fontSize: 16,
    fontWeight: "700",
    color: "#F8FAFC",
    marginVertical: 4,
  },
  gridSub: {
    fontSize: 10,
    color: "#64748B",
  },
  channelContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    backgroundColor: "#1E293B",
    padding: 12,
    borderRadius: 10,
    marginBottom: 16,
  },
  channelTag: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#0F172A",
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 6,
    marginRight: 8,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: "#334155",
  },
  channelTagText: {
    fontSize: 11,
    color: "#E2E8F0",
    fontWeight: "500",
  },
  noDataText: {
    fontSize: 12,
    color: "#64748B",
    fontStyle: "italic",
  },
  testCard: {
    backgroundColor: "#1E293B",
    padding: 14,
    borderRadius: 10,
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 11,
    color: "#94A3B8",
    marginBottom: 4,
  },
  input: {
    backgroundColor: "#0F172A",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: "#F8FAFC",
    fontSize: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#334155",
  },
  sendButton: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#2563EB",
    paddingVertical: 10,
    borderRadius: 8,
    marginTop: 4,
  },
  sendButtonText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "600",
  },
  resultText: {
    fontSize: 12,
    marginTop: 8,
    textAlign: "center",
  },
  logsContainer: {
    backgroundColor: "#0F172A",
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: "#1E293B",
  },
  logItem: {
    backgroundColor: "#1E293B",
    padding: 10,
    borderRadius: 8,
    marginBottom: 8,
  },
  logHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  logType: {
    fontSize: 12,
    fontWeight: "700",
    color: "#38BDF8",
  },
  logTime: {
    fontSize: 10,
    color: "#64748B",
  },
  logSource: {
    fontSize: 10,
    color: "#94A3B8",
    marginVertical: 2,
  },
  logJson: {
    fontSize: 11,
    fontFamily: "monospace",
    color: "#CBD5E1",
    backgroundColor: "#0B0F17",
    padding: 6,
    borderRadius: 4,
    marginTop: 4,
  },
});
