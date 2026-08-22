/**
 * TourSafe Connectivity Store (Zustand)
 * Central store for network state, connectivity policies, and upload decisions.
 */

import { create } from "zustand";
import {
  NetworkState,
  ConnectivityPolicy,
  deriveConnectivityPolicy,
} from "@/types/connectivity";

interface ConnectivityStoreState {
  networkState: NetworkState;
  lastUpdated: number; // epoch ms
  policy: ConnectivityPolicy;

  setNetworkState: (state: NetworkState) => void;
  setPolicy: (policy: ConnectivityPolicy) => void;
  updatePolicyFromState: () => void;
  reset: () => void;
}

const initialNetwork: NetworkState = {
  type: "none",
  isConnected: false,
  isWifi: false,
  isCellular: false,
  isMetered: false,
  effectiveType: "none",
};

export const useConnectivityStore = create<ConnectivityStoreState>((set, get) => ({
  networkState: initialNetwork,
  lastUpdated: Date.now(),
  policy: deriveConnectivityPolicy(initialNetwork),

  setNetworkState: (networkState) =>
    set({
      networkState,
      lastUpdated: Date.now(),
      policy: deriveConnectivityPolicy(networkState),
    }),

  setPolicy: (policy) => set({ policy }),

  updatePolicyFromState: () => {
    const { networkState } = get();
    set({
      policy: deriveConnectivityPolicy(networkState),
    });
  },

  reset: () =>
    set({
      networkState: initialNetwork,
      lastUpdated: Date.now(),
      policy: deriveConnectivityPolicy(initialNetwork),
    }),
}));