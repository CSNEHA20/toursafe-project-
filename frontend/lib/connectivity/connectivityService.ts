/**
 * TourSafe Connectivity Service
 * Tracks network state (Wi-Fi, cellular, offline, unknown) and provides
 * connectivity-aware decisions for the telemetry pipeline.
 */

import {
  NetworkState,
  ConnectionType,
  ConnectionInfo,
  ConnectivityPolicy,
  CONNECTIVITY_POLICIES,
  deriveConnectivityPolicy,
} from "@/types/connectivity";
import { useConnectivityStore } from "@/store/connectivityStore";

class ConnectivityService {
  private networkState: NetworkState = {
    type: "wifi",
    isConnected: true,
    isWifi: true,
    isCellular: false,
    isMetered: false,
    effectiveType: "4g",
  };
  private listenerCount = 0;
  private subscription: (() => void) | null = null;

  constructor() {
    this.scheduleCheck();
  }

  private scheduleCheck() {
    this.readCurrentState().then((st) => {
      useConnectivityStore.getState().setNetworkState(st);
    });
  }

  public async readCurrentState(): Promise<NetworkState> {
    try {
      if (typeof navigator !== "undefined" && "onLine" in navigator) {
        const isOnline = navigator.onLine;
        this.networkState = {
          type: isOnline ? "wifi" : "none",
          isConnected: isOnline,
          isWifi: isOnline,
          isCellular: false,
          isMetered: false,
          effectiveType: isOnline ? "4g" : "none",
        };
      }
    } catch (err) {
      console.warn("[ConnectivityService] Could not read network state:", err);
    }
    return { ...this.networkState };
  }

  public subscribe(callback: (state: NetworkState) => void): () => void {
    this.listenerCount += 1;
    callback(this.networkState);

    const interval = setInterval(async () => {
      const state = await this.readCurrentState();
      callback(state);
    }, 5000);

    return () => {
      this.listenerCount -= 1;
      clearInterval(interval);
    };
  }

  public getCurrentState(): NetworkState {
    return { ...this.networkState };
  }

  public getCurrentPolicy(): ConnectivityPolicy {
    return deriveConnectivityPolicy(this.networkState);
  }

  public allowsUpload(): boolean {
    const policy = this.getCurrentPolicy();
    return policy.allowTelemetryUpload;
  }

  public isOffline(): boolean {
    return !this.networkState.isConnected;
  }

  public isOnline(): boolean {
    return this.networkState.isConnected;
  }
}

export const connectivityService = new ConnectivityService();
export type { NetworkState, ConnectionType, ConnectionInfo, ConnectivityPolicy };
export { CONNECTIVITY_POLICIES, deriveConnectivityPolicy };