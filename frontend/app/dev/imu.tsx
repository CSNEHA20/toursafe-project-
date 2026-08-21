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
  Pause,
  Square,
  ArrowLeft,
  Share2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Compass,
  Zap,
} from "lucide-react-native";
import { useRouter } from "expo-router";
import Toast from "react-native-toast-message";
import { useIMUStore } from "@/store/imuStore";
import { imuController } from "@/lib/sensors/imuController";
import { realtimeClient } from "@/lib/realtimeClient";
import { IMU_CONFIG } from "@/lib/sensors/config";

export default function IMUDiagnosticsScreen() {
  const router = useRouter();
  const [realtimeState, setRealtimeState] = useState(realtimeClient.getConnectionState());
  const [exportJson, setExportJson] = useState<string | null>(null);

  const {
    imuStatus,
    accelerometerStatus,
    gyroscopeStatus,
    latestIMUSample,
    qualityMetrics,
    activeSession,
    imuError,
  } = useIMUStore();

  useEffect(() => {
    imuController.checkAvailability();
    const unsub = realtimeClient.onStateChange((s) => setRealtimeState(s));
    return () => unsub();
  }, []);

  const handleStartIMU = async () => {
    try {
      await imuController.start();
      Toast.show({ type: "success", text1: "50 Hz IMU Pipeline Started" });
    } catch (err: any) {
      Toast.show({ type: "error", text1: "Start Failed", text2: err?.message });
    }
  };

  const handlePauseIMU = () => {
    imuController.pause();
  };

  const handleResumeIMU = () => {
    imuController.resume();
  };

  const handleStopIMU = async () => {
    await imuController.stop();
    Toast.show({ type: "info", text1: "IMU Telemetry Stopped" });
  };

  const handleExportDiagnostics = () => {
    const snapshot = imuController.exportDiagnosticSnapshot(5);
    const jsonStr = JSON.stringify(snapshot, null, 2);
    setExportJson(jsonStr);

    Share.share({
      message: jsonStr,
      title: "TourSafe IMU Diagnostics Snapshot",
    }).catch(() => {});
  };

  const getQualityColor = () => {
    switch (qualityMetrics.qualityState) {
      case "excellent":
        return "#10b981";
      case "good":
        return "#0d9488";
      case "degraded":
        return "#f59e0b";
      case "poor":
        return "#ef4444";
      case "unavailable":
      default:
        return "#94a3b8";
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <ArrowLeft size={18} color="#fff" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>IMU Telemetry Diagnostics</Text>
          <Text style={styles.subtitle}>50 Hz physical Accelerometer & Gyroscope pipeline</Text>
        </View>
      </View>

      {/* Real Device Sensor Banner */}
      <View
        style={[
          styles.bannerCard,
          qualityMetrics.accelerometerAvailable && qualityMetrics.gyroscopeAvailable
            ? styles.bannerActive
            : styles.bannerWarning,
        ]}
      >
        {qualityMetrics.accelerometerAvailable && qualityMetrics.gyroscopeAvailable ? (
          <>
            <CheckCircle2 size={20} color="#10b981" />
            <View style={{ flex: 1 }}>
              <Text style={styles.bannerTitle}>REAL DEVICE SENSOR DATA</Text>
              <Text style={styles.bannerSubtitle}>
                Physical MEMS Accelerometer & Gyroscope hardware active.
              </Text>
            </View>
          </>
        ) : (
          <>
            <AlertTriangle size={20} color="#ef4444" />
            <View style={{ flex: 1 }}>
              <Text style={[styles.bannerTitle, { color: "#ef4444" }]}>
                PHYSICAL SENSORS UNAVAILABLE
              </Text>
              <Text style={styles.bannerSubtitle}>
                {imuError || "Device does not provide physical motion sensors (e.g. running in web browser)."}
              </Text>
            </View>
          </>
        )}
      </View>

      {/* Control Strip */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>IMU Pipeline Controls</Text>
        <View style={styles.btnRow}>
          {imuStatus === "idle" || imuStatus === "stopped" || imuStatus === "error" ? (
            <TouchableOpacity onPress={handleStartIMU} style={[styles.btn, styles.startBtn]}>
              <Play size={16} color="#fff" />
              <Text style={styles.btnText}>Start 50 Hz IMU</Text>
            </TouchableOpacity>
          ) : imuStatus === "active" ? (
            <>
              <TouchableOpacity onPress={handlePauseIMU} style={[styles.btn, styles.pauseBtn]}>
                <Pause size={16} color="#1a365d" />
                <Text style={[styles.btnText, { color: "#1a365d" }]}>Pause</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleStopIMU} style={[styles.btn, styles.stopBtn]}>
                <Square size={16} color="#fff" />
                <Text style={styles.btnText}>Stop IMU</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <TouchableOpacity onPress={handleResumeIMU} style={[styles.btn, styles.resumeBtn]}>
                <Play size={16} color="#fff" />
                <Text style={styles.btnText}>Resume</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleStopIMU} style={[styles.btn, styles.stopBtn]}>
                <Square size={16} color="#fff" />
                <Text style={styles.btnText}>Stop IMU</Text>
              </TouchableOpacity>
            </>
          )}

          <TouchableOpacity onPress={handleExportDiagnostics} style={[styles.btn, styles.secondaryBtn]}>
            <Share2 size={16} color="#1a365d" />
            <Text style={[styles.btnText, { color: "#1a365d" }]}>Export Snapshot</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* KPI Overview Grid */}
      <View style={styles.grid}>
        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>IMU Status</Text>
          <Text
            style={[
              styles.kpiValue,
              {
                color:
                  imuStatus === "active"
                    ? "#10b981"
                    : imuStatus === "paused"
                    ? "#f59e0b"
                    : "#64748b",
              },
            ]}
          >
            {imuStatus.toUpperCase()}
          </Text>
        </View>

        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Observed Rate</Text>
          <Text style={[styles.kpiValue, { color: getQualityColor() }]}>
            {qualityMetrics.observedFrequencyHz} Hz
          </Text>
          <Text style={styles.kpiSub}>Target: {IMU_CONFIG.TARGET_FREQUENCY_HZ} Hz</Text>
        </View>

        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Quality State</Text>
          <Text style={[styles.kpiValue, { color: getQualityColor() }]}>
            {qualityMetrics.qualityState.toUpperCase()}
          </Text>
          <Text style={styles.kpiSub}>Jitter: {qualityMetrics.jitterMs} ms</Text>
        </View>

        <View style={styles.kpi}>
          <Text style={styles.kpiLabel}>Sync Offset</Text>
          <Text style={[styles.kpiValue, { color: "#0d9488" }]}>
            {qualityMetrics.timestampDeltaMs} ms
          </Text>
          <Text style={styles.kpiSub}>Tol: ±{IMU_CONFIG.SYNC_TOLERANCE_MS} ms</Text>
        </View>
      </View>

      {/* Live Physical Accelerometer Channels */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Activity size={18} color="#1a365d" />
            <Text style={styles.cardTitle}>Physical Accelerometer (g)</Text>
          </View>
          <Text style={[styles.badge, { color: accelerometerStatus === "active" ? "#10b981" : "#64748b" }]}>
            {accelerometerStatus.toUpperCase()}
          </Text>
        </View>

        {latestIMUSample ? (
          <View style={styles.metaTable}>
            <Row label="X-Axis (Lateral)" value={`${latestIMUSample.accelerometer.x.toFixed(4)} g`} />
            <Row label="Y-Axis (Longitudinal)" value={`${latestIMUSample.accelerometer.y.toFixed(4)} g`} />
            <Row label="Z-Axis (Vertical)" value={`${latestIMUSample.accelerometer.z.toFixed(4)} g`} />
            <Row
              label="Derived Magnitude (A_mag)"
              value={`${latestIMUSample.derived.acceleration_magnitude.toFixed(4)} g`}
              highlight
            />
            <Row
              label="Magnitude (SI m/s²)"
              value={`${(latestIMUSample.derived.acceleration_magnitude * 9.80665).toFixed(3)} m/s²`}
            />
            <Row label="Callback Frequency" value={`${qualityMetrics.accelerometerFrequencyHz} Hz`} />
          </View>
        ) : (
          <View style={styles.emptyBox}>
            <Activity size={28} color="#94a3b8" />
            <Text style={styles.emptyText}>No accelerometer samples received yet.</Text>
          </View>
        )}
      </View>

      {/* Live Physical Gyroscope Channels */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Compass size={18} color="#1a365d" />
            <Text style={styles.cardTitle}>Physical Gyroscope (rad/s)</Text>
          </View>
          <Text style={[styles.badge, { color: gyroscopeStatus === "active" ? "#10b981" : "#64748b" }]}>
            {gyroscopeStatus.toUpperCase()}
          </Text>
        </View>

        {latestIMUSample ? (
          <View style={styles.metaTable}>
            <Row label="X-Axis (Pitch Rate)" value={`${latestIMUSample.gyroscope.x.toFixed(4)} rad/s`} />
            <Row label="Y-Axis (Roll Rate)" value={`${latestIMUSample.gyroscope.y.toFixed(4)} rad/s`} />
            <Row label="Z-Axis (Yaw Rate)" value={`${latestIMUSample.gyroscope.z.toFixed(4)} rad/s`} />
            <Row
              label="Derived Magnitude (G_mag)"
              value={`${latestIMUSample.derived.angular_velocity_magnitude.toFixed(4)} rad/s`}
              highlight
            />
            <Row label="Callback Frequency" value={`${qualityMetrics.gyroscopeFrequencyHz} Hz`} />
          </View>
        ) : (
          <View style={styles.emptyBox}>
            <Compass size={28} color="#94a3b8" />
            <Text style={styles.emptyText}>No gyroscope samples received yet.</Text>
          </View>
        )}
      </View>

      {/* Sampling Frequency & Interval Analysis */}
      <View style={styles.card}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <Clock size={18} color="#1a365d" />
          <Text style={styles.cardTitle}>Timing & Jitter Diagnostics</Text>
        </View>
        <View style={styles.metaTable}>
          <Row label="Total Synchronized Samples" value={String(qualityMetrics.sampleCount)} />
          <Row label="Target Sampling Interval" value={`${IMU_CONFIG.SAMPLE_INTERVAL_MS} ms (50 Hz)`} />
          <Row label="Average Measured Interval" value={`${qualityMetrics.averageIntervalMs} ms`} />
          <Row label="Min Observed Interval" value={`${qualityMetrics.minIntervalMs} ms`} />
          <Row label="Max Observed Interval" value={`${qualityMetrics.maxIntervalMs} ms`} />
          <Row label="Inter-sample Jitter (StdDev)" value={`${qualityMetrics.jitterMs} ms`} />
          <Row label="Detected Delivery Gaps (>50ms)" value={String(qualityMetrics.sampleGapCount)} />
          <Row label="Largest Delivery Gap" value={`${qualityMetrics.largestGapMs} ms`} />
          <Row label="Total Gap Duration" value={`${qualityMetrics.totalGapDurationMs} ms`} />
        </View>
      </View>

      {/* Active Session & Realtime Transport */}
      <View style={styles.card}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <Zap size={18} color="#1a365d" />
          <Text style={styles.cardTitle}>Session & Realtime Status</Text>
        </View>
        <View style={styles.metaTable}>
          <Row label="Active Session ID" value={activeSession?.session_id || "None"} />
          <Row label="Tourist ID" value={activeSession?.tourist_id || "tourist_me"} />
          <Row label="Last Sequence #" value={`#${latestIMUSample?.sequence_number || 0}`} />
          <Row label="Wall-Clock Timestamp" value={latestIMUSample?.timestamp || "N/A"} />
          <Row label="Realtime Transport (WS)" value={realtimeState.toUpperCase()} />
        </View>
      </View>

      {/* Snapshot Preview if Exported */}
      {exportJson && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Exported Diagnostic Snapshot (JSON)</Text>
          <ScrollView horizontal style={styles.jsonBox}>
            <Text style={styles.jsonText}>{exportJson.slice(0, 1500)}...</Text>
          </ScrollView>
        </View>
      )}
    </ScrollView>
  );
}

function Row({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <View style={[styles.row, highlight ? styles.highlightRow : null]}>
      <Text style={[styles.rowLabel, highlight ? { color: "#1a365d", fontWeight: "700" } : null]}>
        {label}
      </Text>
      <Text style={[styles.rowValue, highlight ? { color: "#0d9488", fontWeight: "800" } : null]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f1f5f9" },
  content: { padding: 16, gap: 14 },
  header: {
    backgroundColor: "#1a365d",
    borderRadius: 16,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  backBtn: {
    padding: 8,
    backgroundColor: "rgba(255, 255, 255, 0.15)",
    borderRadius: 10,
  },
  title: { color: "#fff", fontSize: 20, fontWeight: "800" },
  subtitle: { color: "rgba(255, 255, 255, 0.7)", fontSize: 12, marginTop: 2 },
  bannerCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
  },
  bannerActive: {
    backgroundColor: "#ecfdf5",
    borderColor: "#a7f3d0",
  },
  bannerWarning: {
    backgroundColor: "#fef2f2",
    borderColor: "#fecaca",
  },
  bannerTitle: { fontSize: 13, fontWeight: "800", color: "#065f46", letterSpacing: 0.3 },
  bannerSubtitle: { fontSize: 11, color: "#475569", marginTop: 2 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: { fontSize: 15, fontWeight: "800", color: "#1a365d" },
  badge: { fontSize: 11, fontWeight: "700" },
  btnRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  btn: {
    flex: 1,
    minWidth: "45%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: 10,
  },
  startBtn: { backgroundColor: "#10b981" },
  pauseBtn: { backgroundColor: "#fef08a" },
  resumeBtn: { backgroundColor: "#3b82f6" },
  stopBtn: { backgroundColor: "#ef4444" },
  secondaryBtn: { backgroundColor: "#f1f5f9", borderWidth: 1, borderColor: "#cbd5e1" },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 13 },
  grid: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  kpi: {
    flex: 1,
    minWidth: "45%",
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  kpiLabel: { fontSize: 10, color: "#64748b", textTransform: "uppercase", fontWeight: "700" },
  kpiValue: { fontSize: 16, fontWeight: "800", marginTop: 4 },
  kpiSub: { fontSize: 10, color: "#94a3b8", marginTop: 2 },
  metaTable: { gap: 8 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 5,
    borderBottomWidth: 1,
    borderBottomColor: "#f1f5f9",
  },
  highlightRow: {
    backgroundColor: "#f0fdf4",
    paddingHorizontal: 6,
    borderRadius: 6,
  },
  rowLabel: { fontSize: 12, color: "#64748b", fontWeight: "600" },
  rowValue: { fontSize: 12, color: "#0f172a", fontWeight: "700" },
  emptyBox: { alignItems: "center", justifyContent: "center", padding: 20, gap: 8 },
  emptyText: { color: "#94a3b8", fontSize: 13 },
  jsonBox: {
    backgroundColor: "#0f172a",
    borderRadius: 10,
    padding: 12,
    maxHeight: 200,
    marginTop: 8,
  },
  jsonText: { color: "#38bdf8", fontSize: 10, fontFamily: "monospace" },
});
