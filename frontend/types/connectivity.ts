/**
 * TourSafe Connectivity Types
 * Canonical network state and transmission policies for mobile edge telemetry.
 */

export type ConnectionType = "wifi" | "cellular" | "none" | "unknown" | "bluetooth" | "ethernet" | "wimax" | "vpn" | "other";

export interface NetworkState {
  type: ConnectionType;
  isConnected: boolean;
  isWifi: boolean;
  isCellular: boolean;
  isMetered: boolean;
  effectiveType?: "2g" | "3g" | "4g" | "5g" | "none" | "unknown";
}

export interface ConnectionInfo {
  type: ConnectionType;
  isConnected: boolean;
  isInternetReachable?: boolean | null;
  details?: any;
}

export interface ConnectivityPolicy {
  allowTelemetryUpload: boolean;
  allowHighFrequencyUpload: boolean;
  allowBatchCompression: boolean;
  maxBatchSize: number;
  retryIntervalMs: number;
}

export const CONNECTIVITY_POLICIES: Record<string, ConnectivityPolicy> = {
  wifi: {
    allowTelemetryUpload: true,
    allowHighFrequencyUpload: true,
    allowBatchCompression: true,
    maxBatchSize: 50,
    retryIntervalMs: 3000,
  },
  cellular: {
    allowTelemetryUpload: true,
    allowHighFrequencyUpload: false,
    allowBatchCompression: true,
    maxBatchSize: 25,
    retryIntervalMs: 5000,
  },
  none: {
    allowTelemetryUpload: false,
    allowHighFrequencyUpload: false,
    allowBatchCompression: false,
    maxBatchSize: 0,
    retryIntervalMs: 15000,
  },
  unknown: {
    allowTelemetryUpload: false,
    allowHighFrequencyUpload: false,
    allowBatchCompression: false,
    maxBatchSize: 0,
    retryIntervalMs: 10000,
  },
};

export function deriveConnectivityPolicy(state: NetworkState): ConnectivityPolicy {
  if (!state.isConnected) {
    return CONNECTIVITY_POLICIES.none;
  }
  if (state.isWifi) {
    return CONNECTIVITY_POLICIES.wifi;
  }
  if (state.isCellular) {
    return CONNECTIVITY_POLICIES.cellular;
  }
  return CONNECTIVITY_POLICIES.unknown;
}
