/**
 * TourSafe Connectivity Store (Zustand)
 * Central store for network state, connectivity policies, and upload decisions.
 * Persists connectivity state across app restarts via AsyncStorage.
 */

import { create } from "zustand";
import {
  NetworkState,
  ConnectionType,
  ConnectionInfo,
  CONNECTIVITY_POLICIES,
  deriveConnectivityPolicy,
} from "@/types/connectivity";
import AsyncStorage from "@react-native-async-storage/async-storage";

interface ConnectivityStoreState {
  networkState: NetworkState;
  lastUpdated: number; // epoch ms
  policy: ConnectionInfo;

  setNetworkState: (state: NetworkState) => void;
  setPolicy: (policy: ConnectionInfo) => void;
  updatePolicyFromState: () => void;
  reset: () => void;
}

const CONNECTIVITY_STORAGE_KEY = "@toursafe_connectivity_state_v1";

const initialState: ConnectivityStoreState = {
  networkState: {
    type: "none",
    isConnected: false,
    isWifi: false,
    isCellular: false,
    isMetered: false,
    effectiveType: "none",
  },
  lastUpdated: Date.now(),
  policy: deriveConnectivityPolicy({
    type: "none",
    isConnected: false,
    isWifi: false,
    isCellular: false,
    isMetered: false,
    effectiveType: "none",
  }),
};

export const useConnectivityStore = create<ConnectivityStoreState>((set) => ({
  networkState: initialState.networkState,
  lastUpdated: initialState.lastUpdated,
  policy: initialState.policy,

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
      networkState: {
        type: "none",
        isConnected: false,
        isWifi: false,
        isCellular: false,
        isMetered: false,
        effectiveType: "none",
      },
      lastUpdated: Date.now(),
      policy: deriveConnectivityPolicy({
        type: "none",
        isConnected: false,
        isWifi: false,
        isCellular: false,
        isMetered: false,
        effectiveType: "none",
      }),
    }),
}));

// Persist connectivity state across restarts
useConnectivityStore.setState(
  {
    name: "@toursafe-connectivity-store",
    size: 1,
  },
  persist(
    (state) => ({
      networkState: state.networkState,
      lastUpdated: state.lastUpdated,
      policy: state.policy,
    }),
    {
      storage: AsyncStorage,
      getStorageKey: (name) => CONNECTIVITY_STORAGE_KEY,
      partialize: (state) => ({
        networkState: state.networkState,
        lastUpdated: state.lastUpdated,
      }),
    }
  )
);