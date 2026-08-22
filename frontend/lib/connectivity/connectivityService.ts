/**
 * TourSafe Connectivity Service
 * Tracks network state (Wi-Fi, cellular, offline, unknown) and provides
 * connectivity-aware decisions for the telemetry pipeline.
 *
 * Principle: Distinguish "device has network" from "server reachable."
 * NETWORK_CONNECTED but SERVER_UNREACHABLE is a critical distinction.
 */

import { NetworkState, ConnectionType, ConnectionInfo, CONNECTION_TYPES, CONNECTIVITY_POLICIES, deriveConnectivityPolicy } from "../../types/connectivity";
import { useConnectivityStore } from "../../store/connectivityStore";
import type { TelemetryPacketEnvelope } from "../../types/telemetry";

/**
 * ConnectivityService observes the device's network state and provides
 * connectivity-aware decisions to the telemetry pipeline.
 * It monitors network changes and surfaces policy recommendations.
 */
class ConnectivityService {
  private networkState: NetworkState = {
    type: "none",
    isConnected: false,
    isWifi: false,
    isCellular: false,
    isMetered: false,
    effectiveType: "none",
  };
  private listenerCount = 0;
  private subscription: (() => void) | null = null;

  constructor() {
    this.scheduleCheck();
  }

  /**
   * Read the current network state from the device.
   * Uses react-native-netinfo or falls back to estimation.
   */
  public async readCurrentState(): Promise<NetworkState> {
    try {
      // Try react-native-netinfo
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const netinfo = require("react-native-netinfo");

      if (netinfo && typeof netinfo.isConnectedFetch !== "function") {
        const state = await netinfo.isConnectedFetch();
        this.networkState = this.normalizeNetinfoState(state);
      } else {
        // Fallback
        this.networkState = {
          type: "none",
          isConnected: false,
          isWifi: false,
          isCellular: false,
          isMetered: false,
          effectiveType: "none",
        };
      }
    } catch (err) {
      console.warn("[ConnectivityService] Could not read network state:", err);
    }

    return { ...this.networkState };
  }

  private normalizeNetinfoState(state: any): NetworkState {
    if (!state) {
      return {
        type: "none",
        isConnected: false,
        isWifi: false,
        isCellular: false,
        isMetered: false,
        effectiveType: "none",
      };
    }

    const isConnected = state.isConnected ?? false;
    const type = state.type ?? "none";
    const isWifi = state.isWifi ?? false;
    const isCellular = state.isCellular ?? false;
    const isMetered = state.isMetered ?? false;

    let effectiveType = "unknown";
    if (isWifi) effectiveType = "wifi";
    else if (isCellular) effectiveType = "cell";
    else effectiveType = "none";

    return {
      type: CONNECTION_TYPES.includes(type as any) ? type : "unknown",
      isConnected,
      isWifi,
      isCellular,
      isMetered,
      effectiveType,
    };
  }

  public subscribe(callback: (state: NetworkState) => void): () => void {
    this.listenerCount += 1;

    if (this.listenerCount === 1) {
      this.startMonitoring(callback);
    }

    return () => {
      this.listenerCount -= 1;
      if (this.listenerCount <= 0 && this.subscription) {
        this.subscription();
        this.subscription = null;
      }
    };
  }

  private startMonitoring(callback: (state: NetworkState) => void): void {
    try {
      // Try react-native-netinfo monitoring
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const netinfo = require("react-native-netinfo");

      if (netinfo && typeof netinfo.addEventListener !== "undefined") {
        console.debug("[ConnectivityService] Netinfo monitoring started");
      }
    } catch (err) {
      console.warn("[ConnectivityService] Netinfo monitoring not available:", err);
    }

    // Fallback: periodic network check every 5 seconds
    this.schedulePeriodicCheck(callback);
  }

  private schedulePeriodicCheck(callback: (state: NetworkState) => void): void {
    const check = async () => {
      const state = await this.readCurrentState();
      callback(state);
      setTimeout(() => this.schedulePeriodicCheck(callback), 5_000);
    };
    check();
  }

  public getCurrentState(): NetworkState {
    return { ...this.networkState };
  }

  public getCurrentPolicy(): ConnectionInfo {
    return deriveConnectivityPolicy(this.networkState);
  }

  public allowsUpload(): boolean {
    const policy = this.getCurrentPolicy();
    return policy.mode !== "buffer" && (policy.allowWifi || policy.allowCellular);
  }

  public requiresWifi(): boolean {
    const policy = this.getCurrentPolicy();
    return policy.mode === "wifiOnly" || (policy.type === "cell_metered" && !policy.allowCellular);
  }

  public isOffline(): boolean {
    return this.networkState.isConnected === false;
  }
}

export const connectivityService = new ConnectivityService();

export type { NetworkState, ConnectionType, ConnectionInfo };

export {
  CONNECTION_TYPES,
  CONNECTIVITY_POLICIES,
  deriveConnectivityPolicy,
};