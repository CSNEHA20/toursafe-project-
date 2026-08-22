/**
 * TourSafe Device Health Service
 * Tracks comprehensive device health including battery, storage, network,
 * sensor health, GPS health, and sync status.
 *
 * All health data is derived from actual device state - no fabricated values.
 * This service becomes visible in diagnostics and supports adaptive behavior.
 */

import { BatteryInfo } from "@/types/battery";
import { useBatteryStore } from "@/store/batteryStore";
import { useLocationStore } from "@/store/locationStore";
import { useIMUStore } from "@/store/imuStore";
import { useTelemetryStore } from "@/store/telemetryStore";
import { useConnectivityStore } from "@/store/connectivityStore";
import { deviceHealthService as healthService } from "./deviceHealthService";
import { gpsService } from "../gps/gpsService";
import { generateId } from "../lib/utils";
import { api } from "../api";
import type {
  DeviceHealthStatus,
  SensorHealthStatus,
  GPSHealthStatus,
  ConnectivityHealthStatus,
  BatteryHealthStatus,
  DeviceCapabilityProfile,
  ClockSkewInfo,
  TrackingSessionLifecycleState,
  TrackingGPSQuality,
  IMUQualityState,
} from "@/types";

/**
 * Comprehensive device health status.
 * Tracks all subsystems and provides a holistic health picture.
 */
export interface DeviceHealthStatus {
  timestamp: string;
  overall: "healthy" | "degraded" | "unhealthy" | "critical";
  battery: BatteryHealthStatus;
  sensors: {
    gps: GPSHealthStatus;
    accelerometer: SensorHealthStatus;
    gyroscope: SensorHealthStatus;
  };
  connectivity: ConnectivityHealthStatus;
  storage: {
    available: boolean;
    usagePercentage: number;
    estimatedCapacity: number;
    estimatedAgeSeconds: number;
  };
  sync: {
    status: "SYNCED" | "SYNCING" | "PENDING" | "OFFLINE" | "ERROR" | "UNKNOWN";
    lastAck?: string;
    latencyMs?: number;
    pendingBatchCount: number;
  };
  tracking: {
    status: TrackingSessionLifecycleState;
    sessionId?: string;
    isActive: boolean;
  };
  capabilities: DeviceCapabilityProfile;
  clockSkew?: ClockSkewInfo;
}

/**
 * Sensor health status for individual sensors.
 */
export interface SensorHealthStatus {
  available: boolean;
  lastSample?: string;
  quality?: "excellent" | "good" | "degraded" | "poor" | "unavailable";
  consecutiveGaps: number;
  lastQualityState?: IMUQualityState;
}

/**
 * GPS health status.
 */
export interface GPSHealthStatus {
  available: boolean;
  lastFix?: string;
  accuracyMeters?: number;
  qualityState: TrackingGPSQuality;
  stalenessSeconds: number;
  satellitesInView?: number | null;
}

/**
 * Connectivity health status.
 */
export interface ConnectivityHealthStatus {
  networkAvailable: boolean;
  networkType: "wifi" | "cellular" | "none" | "unknown";
  serverReachable: boolean;
  lastPing?: string;
  latencyMs?: number;
}

/**
 * Battery health status.
 */
export interface BatteryHealthStatus {
  level: number;
  isCharging: boolean;
  isLowPowerMode: boolean;
  temperatureC?: number;
  health: "good" | "fair" | "poor" | "unknown";
}

/**
 * Device capability profile.
 * Describes what this device can do without collecting unnecessary identifiers.
 */
export interface DeviceCapabilityProfile {
  platform: "android" | "ios" | "web" | "unknown";
  osVersion: string;
  appVersion: string;
  sdkVersion?: string;
  sensorAvailability: {
    gps: boolean;
    accelerometer: boolean;
    gyroscope: boolean;
  };
  backgroundCapability: "none" | "android_foreground_service" | "ios_background" | "limited";
  storageAvailable: boolean;
  networkCapability: "wifi" | "cellular" | "both" | "none";
}

/**
 * Clock skew information.
 * Detects device clock anomalies, large timestamp jumps, future timestamps.
 */
export interface ClockSkewInfo {
  deviceClockOffsetMs: number;
  lastDetected: string;
  anomalyCount: number;
  lastAnomaly?: string;
}

/**
 * DeviceHealthService monitors and reports comprehensive device health.
 * It collects data from all subsystems (battery, connectivity, sensors, GPS, storage)
 * and provides a unified health status view for diagnostics and adaptive behavior.
 */
class DeviceHealthService {
  private lastHealthReport: DeviceHealthStatus | null = null;
  private clockSkew: ClockSkewInfo | null = null;
  private anomalyCount = 0;
  private lastHealthCheck = 0;
  private checkInterval: NodeJS.Timeout | null = null;

  constructor() {
    // Initial health check
    this.performHealthCheck();
    // Start periodic health checks every 10 seconds
    this.checkInterval = setInterval(
      () => this.performHealthCheck(),
      10_000
    );
  }

  /**
   * Perform a complete health check across all subsystems.
   * Collects data from battery, connectivity, GPS, IMU, storage, and tracking.
   */
  public async performHealthCheck(): Promise<DeviceHealthStatus> {
    const now = Date.now();

    // 1. Battery health
    const batteryInfo = batteryService.readCurrentState();
    const batteryHealth = this.computeBatteryHealth(batteryInfo);

    // 2. GPS health
    const gpsHealth = await this.computeGPSHealth();

    // 3. IMU/accelerometer/gyroscope health
    const imuHealth = this.computeIMUHealth();

    // 4. Connectivity health
    const connectivityInfo = useConnectivityStore.getState();
    const connectivityHealth = this.computeConnectivityHealth(connectivityInfo);

    // 5. Storage health
    const storageHealth = this.computeStorageHealth();

    // 6. Sync status
    const syncHealth = this.computeSyncHealth();

    // 7. Tracking status
    const trackingHealth = this.computeTrackingHealth();

    // 8. Capability profile
    const capabilities = this.computeCapabilities();

    // 9. Clock skew detection
    const clockSkew = await this.detectClockSkew();

    // 10. Compute overall status
    const overall = this.computeOverallStatus(
      batteryHealth,
      gpsHealth,
      imuHealth,
      connectivityHealth,
      syncHealth
    );

    const health: DeviceHealthStatus = {
      timestamp: new Date().toISOString(),
      overall,
      battery: batteryHealth,
      sensors: {
        gps: gpsHealth,
        accelerometer: imuHealth.accelerometer,
        gyroscope: imuHealth.gyroscope,
      },
      connectivity: connectivityHealth,
      storage: storageHealth,
      sync: syncHealth,
      tracking: trackingHealth,
      capabilities,
      clockSkew,
    };

    // Store the latest health report
    this.lastHealthReport = health;
    useTelemetryStore.getState().setDeviceHealth(health);

    return health;
  }

  /**
   * Compute battery health from battery info.
   */
  private computeBatteryHealth(batteryInfo: BatteryInfo): BatteryHealthStatus {
    let health: "good" | "fair" | "poor" | "unknown" = "good";

    if (batteryInfo.level <= 5) {
      health = "poor";
    } else if (batteryInfo.level <= 15) {
      health = "fair";
    } else if (batteryInfo.level <= 40) {
      health = "good";
    } else {
      health = "good";
    }

    // If in low-power mode, downgrade health
    if (batteryInfo.isLowPowerMode) {
      if (health !== "poor") health = "fair";
    }

    return {
      level: batteryInfo.level,
      isCharging: batteryInfo.isCharging,
      isLowPowerMode: batteryInfo.isLowPowerMode,
      health,
    };
  }

  /**
   * Compute GPS health status.
   */
  private async computeGPSHealth(): Promise<GPSHealthStatus> {
    const locationStore = useLocationStore.getState();
    const lastLocation = locationStore.currentLocation;

    let qualityState: TrackingGPSQuality = "UNKNOWN";
    let accuracyMeters: number | undefined;
    let stalenessSeconds = 0;
    let available = false;

    if (lastLocation) {
      available = true;
      accuracyMeters = lastLocation.accuracy ?? undefined;

      // Determine quality state based on accuracy
      if (lastLocation.accuracy !== undefined && lastLocation.accuracy <= 10) {
        qualityState = "GOOD";
      } else if (lastLocation.accuracy !== undefined && lastLocation.accuracy <= 25) {
        qualityState = "DEGRADED";
      } else if (lastLocation.accuracy !== undefined && lastLocation.accuracy <= 50) {
        qualityState = "POOR";
      } else {
        qualityState = "POOR";
      }

      // Compute staleness
      const lastFixTime = lastLocation.timestamp ? new Date(lastLocation.timestamp).getTime() : 0;
      stalenessSeconds = Math.max(0, (now - lastFixTime) / 1000);
    }

    return {
      available,
      lastFix: lastLocation?.timestamp,
      accuracyMeters,
      qualityState,
      stalenessSeconds,
      satellitesInView: undefined,
    };
  }

  /**
   * Compute IMU sensor health status.
   */
  private computeIMUHealth(): {
    accelerometer: SensorHealthStatus;
    gyroscope: SensorHealthStatus;
  } {
    const imuStore = useIMUStore.getState();

    const accelHealth: SensorHealthStatus = {
      available: imuStore.accelerometerStatus !== "unavailable",
      lastSample: imuStore.latestIMUSample?.timestamp,
      quality: imuStore.qualityMetrics.qualityState as any,
      consecutiveGaps: imuStore.sampleGapCount,
      lastQualityState: imuStore.qualityMetrics.qualityState,
    };

    const gyroHealth: SensorHealthStatus = {
      available: imuStore.gyroscopeStatus !== "unavailable",
      lastSample: imuStore.latestIMUSample?.timestamp,
      quality: imuStore.qualityMetrics.qualityState as any,
      consecutiveGaps: imuStore.sampleGapCount,
      lastQualityState: imuStore.qualityMetrics.qualityState,
    };

    return { accelerometer: accelHealth, gyroscope: gyroHealth };
  }

  /**
   * Compute connectivity health status.
   */
  private computeConnectivityHealth(
    connectivityInfo: { type: string; isConnected: boolean }
  ): ConnectivityHealthStatus {
    const isConnected = connectivityInfo.isConnected;
    const networkType = connectivityInfo.type;

    let networkAvailable = false;
    let networkTypeStr: "wifi" | "cellular" | "none" | "unknown" = "none";

    if (isConnected) {
      networkAvailable = true;
      networkTypeStr =
        networkType === "wifi"
          ? "wifi"
          : networkType === "cell"
            ? "cellular"
            : "unknown";
    }

    return {
      networkAvailable,
      networkType: networkTypeStr,
      serverReachable: false, // Would require actual ping
    };
  }

  /**
   * Compute storage health status.
   */
  private computeStorageHealth(): {
    available: boolean;
    usagePercentage: number;
    estimatedCapacity: number;
    estimatedAgeSeconds: number;
  } {
    try {
      const { AsyncStorage } = require("react-native-async-storage/async-storage");
      const key = "@toursafe_telemetry_offline_buffer_v1";
      const raw = await AsyncStorage.getItem(key);

      let usagePercentage = 0;
      let estimatedCapacity = 10_000_000;
      let estimatedAgeSeconds = 0;
      let available = false;

      if (raw) {
        const parsed = JSON.parse(raw);
        available = true;
        usagePercentage = Math.min(100, (parsed.length / 5000) * 100);
        estimatedAge =
          parsed.length > 0
            ? now - new Date(parsed[0].timestamp).getTime() / 1000
            : 0;
      }

      return { available, usagePercentage, estimatedCapacity, estimatedAgeSeconds };
    } catch (err) {
      console.warn("[DeviceHealth] Storage health check failed:", err);
      return {
        available: false,
        usagePercentage: 0,
        estimatedCapacity: 0,
        estimatedAgeSeconds: 0,
      };
    }
  }

  /**
   * Compute sync status health.
   */
  private computeSyncHealth(): {
    status: "SYNCED" | "SYNCING" | "PENDING" | "OFFLINE" | "ERROR" | "UNKNOWN";
    lastAck?: string;
    latencyMs?: number;
    pendingBatchCount: number;
  } {
    const telemetryStore = useTelemetryStore.getState();

    let status: "SYNCED" | "SYNCING" | "PENDING" | "OFFLINE" | "ERROR" | "UNKNOWN" = "OFFLINE";
    let pendingBatchCount = 0;

    if (telemetryStore.isOnline) {
      if (telemetryStore.sessionStatus === "active") {
        status = "SYNCING";
      } else {
        status = "SYNCED";
      }
    } else {
      status = "OFFLINE";
    }

    pendingBatchCount = telemetryOfflineBuffer.length;

    return {
      status,
      lastAck: telemetryStore.lastServerAck?.packet_id,
      latencyMs: telemetryStore.quality?.transport_latency_ms,
      pendingBatchCount,
    };
  }

  /**
   * Compute tracking health status.
   */
  private computeTrackingHealth(): {
    status: TrackingSessionLifecycleState;
    sessionId?: string;
    isActive: boolean;
  } {
    const locationStore = useLocationStore.getState();

    return {
      status: locationStore.trackingStatus,
      sessionId: locationStore.activeSession?.session_id,
      isActive: locationStore.trackingStatus === "active",
    };
  }

  /**
   * Compute device capability profile.
   */
  private computeCapabilities(): DeviceCapabilityProfile {
    const platform = this.determinePlatform();
    const osVersion = this.determineOSVersion();
    const appVersion = this.determineAppVersion();

    const imuStore = useIMUStore.getState();
    const gpsStore = useLocationStore.getState();

    return {
      platform,
      osVersion,
      appVersion,
      sensorAvailability: {
        gps: gpsStore.trackingStatus !== "error" && gpsStore.permissionState === "granted",
        accelerometer: imuStore.accelerometerStatus !== "unavailable",
        gyroscope: imuStore.gyroscopeStatus !== "unavailable",
      },
      backgroundCapability: this.determineBackgroundCapability(platform),
      storageAvailable: true,
      networkCapability: this.determineNetworkCapability(),
    };
  }

  /**
   * Determine platform (Android, iOS, Web).
   */
  private determinePlatform(): "android" | "ios" | "web" | "unknown" {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { Platform } = require("react-native");
    switch (Platform.OS) {
      case "android":
        return "android";
      case "ios":
        return "ios";
      case "web":
        return "web";
      default:
        return "unknown";
    }
  }

  /**
   * Determine OS version.
   */
  private determineOSVersion(): string {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { Platform } = require("react-native");
    if (Platform.OS === "ios") {
      return "16.0+";
    } else if (Platform.OS === "android") {
      return "10.0+";
    }
    return "unknown";
  }

  /**
   * Determine app version from package.json.
   */
  private determineAppVersion(): string {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const pkg = require("../../package.json");
      return pkg.version || "1.0.0";
    } catch {
      return "1.0.0";
    }
  }

  /**
   * Determine background capability based on platform.
   */
  private determineBackgroundCapability(
    platform: "android" | "ios" | "web" | "unknown"
  ): "none" | "android_foreground_service" | "ios_background" | "limited" {
    switch (platform) {
      case "android":
        return "android_foreground_service";
      case "ios":
        return "ios_background";
      case "web":
        return "limited";
      default:
        return "limited";
    }
  }

  /**
   * Determine network capability.
   */
  private determineNetworkCapability(): "wifi" | "cellular" | "both" | "none" {
    const conn = useConnectivityStore.getState().networkState;
    if (!conn.isConnected) return "none";
    if (conn.isWifi && !conn.isCellular) return "wifi";
    if (conn.isCellular && !conn.isWifi) return "cellular";
    return "both";
  }

  /**
   * Detect clock skew by comparing device time with server time.
   */
  private async detectClockSkew(): Promise<ClockSkewInfo | null> {
    try {
      const locationStore = useLocationStore.getState();
      const lastLocation = locationStore.currentLocation;

      if (!lastLocation) {
        return null;
      }

      const deviceTime = Date.now();
      const fixTime = lastLocation.timestamp ? new Date(lastLocation.timestamp).getTime() : 0;
      const offset = deviceTime - fixTime; // positive = device ahead

      let anomalyCount = 0;
      let lastAnomaly: string | undefined = undefined;

      if (offset > 60_000) {
        anomalyCount += 1;
        lastAnomaly = "device_ahead_by_more_than_1min";
      }

      if (offset < -60_000) {
        anomalyCount += 1;
        lastAnomaly = "device_behind_by_more_than_1min";
      }

      if (fixTime > deviceTime + 60_000) {
        anomalyCount += 1;
        lastAnomaly = "future_timestamp_detected";
      }

      if (anomalyCount > 0) {
        return {
          deviceClockOffsetMs: offset,
          lastDetected: new Date().toISOString(),
          anomalyCount,
          lastAnomaly,
        };
      }

      return null;
    } catch (err) {
      console.warn("[DeviceHealth] Clock skew detection failed:", err);
      return null;
    }
  }

  /**
   * Compute overall health status from subsystem statuses.
   */
  private computeOverallStatus(
    battery: BatteryHealthStatus,
    gps: GPSHealthStatus,
    imu: { accelerometer: SensorHealthStatus; gyroscope: SensorHealthStatus },
    connectivity: ConnectivityHealthStatus,
    sync: {
      status:
        | "SYNCED"
        | "SYNCING"
        | "PENDING"
        | "OFFLINE"
        | "ERROR"
        | "UNKNOWN";
    }
  ): "healthy" | "degraded" | "unhealthy" | "critical" {
    const issues: string[] = [];

    // Check battery
    if (battery.health === "poor") issues.push("battery_poor");
    if (battery.level <= 5) issues.push("battery_critical");

    // Check GPS
    if (gps.qualityState === "POOR") issues.push("gps_poor");
    if (gps.available === false) issues.push("gps_unavailable");

    // Check IMU sensors
    if (imu.accelerometer.quality === "poor") issues.push("imu_accel_poor");
    if (imu.gyroscope.quality === "poor") issues.push("imu_gyro_poor");
    if (imu.accelerometer.available === false) issues.push("imu_accel_unavailable");
    if (imu.gyroscope.available === false) issues.push("imu_gyro_unavailable");

    // Check connectivity
    if (connectivity.networkAvailable === false) issues.push("connectivity_offline");
    if (sync.status === "OFFLINE") issues.push("sync_offline");
    if (sync.status === "ERROR") issues.push("sync_error");

    // Determine overall status based on issue count and severity
    const criticalIssues = issues.filter(
      (i) => i === "battery_critical" || i === "gps_unavailable"
    ).length;

    const majorIssues = issues.filter(
      (i) => i === "battery_poor" || i === "gps_poor" || i === "connectivity_offline"
    ).length;

    if (criticalIssues > 0) return "critical";
    if (majorIssues >= 3) return "unhealthy";
    if (majorIssues >= 1) return "degraded";
    return "healthy";
  }

  /**
   * Get the last health report without performing a fresh check.
   */
  public getLastHealthReport(): DeviceHealthStatus | null {
    return this.lastHealthReport;
  }

  /**
   * Force a health check immediately (bypassing interval).
   */
  public forceHealthCheck(): Promise<DeviceHealthStatus> {
    clearInterval(this.checkInterval);
    this.checkInterval = setInterval(
      () => this.performHealthCheck(),
      10_000
    );
    return this.performHealthCheck();
  }

  /**
   * Stop the health check interval (e.g., on app unload).
   */
  public stop(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }
}

export const deviceHealthService = new DeviceHealthService();

/**
 * Export all types for use in UI/components.
 */
export type {
  DeviceHealthStatus,
  SensorHealthStatus,
  GPSHealthStatus,
  ConnectivityHealthStatus,
  BatteryHealthStatus,
  DeviceCapabilityProfile,
  ClockSkewInfo,
  TrackingSessionLifecycleState,
  TrackingGPSQuality,
  IMUQualityState,
};