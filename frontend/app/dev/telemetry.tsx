import React, { useState, useEffect } from "react";
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Share,
} from "react-native";
import {
  Activity,
  Play,
  Square,
  ArrowLeft,
  Share2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Wifi,
  Database,
  Layers,
  ShieldAlert,
  Zap,
} from "lucide-react-native";
import { useRouter } from "expo-router";
import Toast from "react-native-toast-message";
import { useTelemetryStore } from "@/store/telemetryStore";
import { telemetryClient } from "@/lib/telemetry/telemetryClient";
import { telemetryOfflineBuffer } from "@/lib/telemetry/offlineBuffer";

export default function TelemetryPipelineDiagnosticsScreen() {
  const router = useRouter();
  const [bufferDepth, setBufferDepth] = useState(telemetryOfflineBuffer.length);
  const [clientInfo, setClientInfo] = useState(telemetryClient.getSessionInfo());

  const {
    sessionStatus,
    activeSessionId,
    sequenceNumber,
    highestContiguousAck,
    isOnline,
    quality,
    recentWindows,
    setSessionStatus,
    setActiveSessionId,
    updateSequenceProgress,
  } = useTelemetryStore();

  useEffect(() => {
    const unsub = telemetryClient.subscribe((info) => {
      setClientInfo(telemetryClient.getSessionInfo());
      setBufferDepth(info.bufferSize);
      setSessionStatus(info.status);
      setActiveSessionId(info.sessionId);
      updateSequenceProgress(
        info.sequenceNumber,
        info.highestContiguousAck,
        info.bufferSize,
        info.isOnline
      );
    });

    const interval = setInterval(() => {
      setBufferDepth(telemetryOfflineBuffer.length);
    }, 1000);

    return () => {
      unsub();
      clearInterval(interval);
    };
  }, []);

  const handleStartSession = async () => {
    try {
      const sessId = await telemetryClient.startSession("device_mobile_test");
      Toast.show({ type: "success", text1: "Telemetry Session Started", text2: sessId });
    } catch (e: any) {
      Toast.show({ type: "error", text1: "Failed to start session", text2: e?.message });
    }
  };

  const handleStopSession = async () => {
    try {
      await telemetryClient.stopSession();
      Toast.show({ type: "info", text1: "Telemetry Session Stopped" });
    } catch (e: any) {
      Toast.show({ type: "error", text1: "Failed to stop session", text2: e?.message });
    }
  };

  const handleSimulateSample = () => {
    if (!activeSessionId) {
      Toast.show({ type: "error", text1: "No Active Session", text2: "Start session first" });
      return;
    }

    // Push 5 mock IMU samples
    for (let i = 0; i < 5; i++) {
      telemetryClient.pushIMUSample(
        { x: 0.02 + Math.random() * 0.01, y: -0.01, z: 0.98 + Math.random() * 0.02 },
        { x: 0.001, y: 0.002, z: -0.001 },
        i === 0 ? { latitude: 12.9716, longitude: 77.5946, accuracy: 5.0 } : null
      );
    }
    Toast.show({ type: "success", text1: "Injected 5 Telemetry Samples" });
  };

  const handleExportDiagnostics = () => {
    const data = {
      client: clientInfo,
      buffer: telemetryOfflineBuffer.getStats(),
      quality,
      recentWindows,
      timestamp: new Date().toISOString(),
    };

    const jsonStr = JSON.stringify(data, null, 2);
    Share.share({
      message: jsonStr,
      title: "TourSafe Telemetry Pipeline Diagnostics",
    });
  };

  const getQualityColor = (st: string) => {
    switch (st) {
      case "excellent":
      case "good":
        return "#10B981";
      case "fair":
        return "#F59E0B";
      case "degraded":
      case "poor":
        return "#EF4444";
      default:
        return "#6B7280";
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.backButton}
          accessibilityLabel="Back"
        >
          <ArrowLeft color="#1E293B" size={24} />
        </TouchableOpacity>
        <View style={styles.headerTitleContainer}>
          <Text style={styles.headerTitle}>Telemetry Ingestion</Text>
          <Text style={styles.headerSubtitle}>Pipeline & Window Diagnostics</Text>
        </View>
        <TouchableOpacity
          onPress={handleExportDiagnostics}
          style={styles.actionButton}
          accessibilityLabel="Export"
        >
          <Share2 color="#3B82F6" size={20} />
        </TouchableOpacity>
      </View>

      {/* Pipeline Status Banner */}
      <View style={[styles.card, styles.statusCard]}>
        <View style={styles.statusRow}>
          <View style={styles.statusIconWrapper}>
            <Activity
              color={sessionStatus === "active" ? "#10B981" : "#6B7280"}
              size={24}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.statusLabel}>Session Status</Text>
            <Text style={styles.statusValue}>{sessionStatus.toUpperCase()}</Text>
          </View>
          <View
            style={[
              styles.onlineBadge,
              { backgroundColor: isOnline ? "#D1FAE5" : "#FEE2E2" },
            ]}
          >
            <Wifi color={isOnline ? "#059669" : "#DC2626"} size={14} />
            <Text
              style={[
                styles.onlineText,
                { color: isOnline ? "#059669" : "#DC2626" },
              ]}
            >
              {isOnline ? "Online" : "Offline Buffer"}
            </Text>
          </View>
        </View>

        <View style={styles.metricsGrid}>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Session ID</Text>
            <Text style={styles.metricValueSm} numberOfLines={1}>
              {activeSessionId || "None"}
            </Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Sequence</Text>
            <Text style={styles.metricValue}>{sequenceNumber}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Highest Ack</Text>
            <Text style={styles.metricValue}>{highestContiguousAck}</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Buffer Depth</Text>
            <Text style={[styles.metricValue, { color: bufferDepth > 0 ? "#F59E0B" : "#1E293B" }]}>
              {bufferDepth}
            </Text>
          </View>
        </View>
      </View>

      {/* Control Actions */}
      <View style={styles.controlsRow}>
        {sessionStatus !== "active" ? (
          <TouchableOpacity
            style={[styles.ctrlBtn, styles.startBtn]}
            onPress={handleStartSession}
          >
            <Play color="#FFFFFF" size={18} />
            <Text style={styles.btnText}>Start Ingestion</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={[styles.ctrlBtn, styles.stopBtn]}
            onPress={handleStopSession}
          >
            <Square color="#FFFFFF" size={18} />
            <Text style={styles.btnText}>Stop Session</Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity
          style={[styles.ctrlBtn, styles.simBtn]}
          onPress={handleSimulateSample}
        >
          <Zap color="#3B82F6" size={18} />
          <Text style={[styles.btnText, { color: "#3B82F6" }]}>Inject Samples</Text>
        </TouchableOpacity>
      </View>

      {/* Quality Assessment Card */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Layers color="#1E293B" size={18} />
          <Text style={styles.cardTitle}>Telemetry Quality Engine</Text>
        </View>
        <View style={styles.qualityRows}>
          <View style={styles.qRow}>
            <Text style={styles.qLabel}>Overall Composite</Text>
            <Text
              style={[
                styles.qValue,
                { color: getQualityColor(quality.overall_quality) },
              ]}
            >
              {quality.overall_quality.toUpperCase()}
            </Text>
          </View>
          <View style={styles.qRow}>
            <Text style={styles.qLabel}>GPS Quality</Text>
            <Text
              style={[
                styles.qValue,
                { color: getQualityColor(quality.gps_quality) },
              ]}
            >
              {quality.gps_quality.toUpperCase()}
            </Text>
          </View>
          <View style={styles.qRow}>
            <Text style={styles.qLabel}>IMU 50 Hz Quality</Text>
            <Text
              style={[
                styles.qValue,
                { color: getQualityColor(quality.imu_quality) },
              ]}
            >
              {quality.imu_quality.toUpperCase()}
            </Text>
          </View>
          <View style={styles.qRow}>
            <Text style={styles.qLabel}>Temporal Sync Delta</Text>
            <Text style={styles.qValue}>
              {quality.sync_delta_ms !== null && quality.sync_delta_ms !== undefined
                ? `${quality.sync_delta_ms.toFixed(1)} ms`
                : "N/A"}
            </Text>
          </View>
        </View>
      </View>

      {/* Offline Buffer & Backpressure */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Database color="#1E293B" size={18} />
          <Text style={styles.cardTitle}>Offline Buffer & Backpressure</Text>
        </View>
        <Text style={styles.cardDesc}>
          Packets are queued locally in AsyncStorage during network drops and automatically replayed with contiguous sequence validation upon reconnection.
        </Text>
        <View style={styles.bufferProgressContainer}>
          <View
            style={[
              styles.bufferProgressBar,
              { width: `${Math.min(100, (bufferDepth / 5000) * 100)}%` },
            ]}
          />
        </View>
        <Text style={styles.bufferCaption}>
          {bufferDepth} / 5000 packets buffered ({((bufferDepth / 5000) * 100).toFixed(1)}%)
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
    paddingTop: 8,
  },
  backButton: {
    padding: 8,
    marginRight: 8,
  },
  headerTitleContainer: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#0F172A",
  },
  headerSubtitle: {
    fontSize: 13,
    color: "#64748B",
  },
  actionButton: {
    padding: 8,
    backgroundColor: "#EFF6FF",
    borderRadius: 8,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  statusCard: {
    backgroundColor: "#FFFFFF",
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  statusIconWrapper: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  statusLabel: {
    fontSize: 12,
    color: "#64748B",
  },
  statusValue: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0F172A",
  },
  onlineBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  onlineText: {
    fontSize: 12,
    fontWeight: "600",
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
    paddingTop: 12,
    gap: 12,
  },
  metricItem: {
    width: "47%",
  },
  metricLabel: {
    fontSize: 11,
    color: "#64748B",
    marginBottom: 2,
  },
  metricValue: {
    fontSize: 15,
    fontWeight: "600",
    color: "#1E293B",
  },
  metricValueSm: {
    fontSize: 13,
    fontWeight: "600",
    color: "#1E293B",
  },
  controlsRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 16,
  },
  ctrlBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: 10,
  },
  startBtn: {
    backgroundColor: "#10B981",
  },
  stopBtn: {
    backgroundColor: "#EF4444",
  },
  simBtn: {
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  btnText: {
    color: "#FFFFFF",
    fontWeight: "600",
    fontSize: 14,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: "#0F172A",
  },
  cardDesc: {
    fontSize: 13,
    color: "#64748B",
    lineHeight: 18,
    marginBottom: 12,
  },
  qualityRows: {
    gap: 8,
  },
  qRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: "#F8FAFC",
  },
  qLabel: {
    fontSize: 13,
    color: "#475569",
  },
  qValue: {
    fontSize: 13,
    fontWeight: "700",
  },
  bufferProgressContainer: {
    height: 8,
    backgroundColor: "#F1F5F9",
    borderRadius: 4,
    overflow: "hidden",
    marginBottom: 6,
  },
  bufferProgressBar: {
    height: "100%",
    backgroundColor: "#3B82F6",
  },
  bufferCaption: {
    fontSize: 12,
    color: "#64748B",
  },
});
