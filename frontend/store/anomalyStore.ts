/**
 * TourSafe - Anomaly State Store (Zustand)
 * Prompt 9: Real-Time LSTM Inference Service
 * Tracks active sensor anomaly episodes for authority dashboard & map views.
 */

import { create } from "zustand";
import type { AnomalyDetectedPayload, AnomalyEpisodeItem } from "@/types/anomaly";

interface AnomalyState {
  activeAnomalies: Record<string, AnomalyEpisodeItem>; // key: tourist_id
  history: AnomalyEpisodeItem[];
  isLoading: boolean;

  setAnomalies: (anomalies: AnomalyEpisodeItem[]) => void;
  addOrUpdateAnomaly: (payload: AnomalyDetectedPayload) => void;
  clearAnomaly: (tourist_id: string, duration?: number, peak_score?: number) => void;
  setLoading: (loading: boolean) => void;
}

export const useAnomalyStore = create<AnomalyState>((set, get) => ({
  activeAnomalies: {},
  history: [],
  isLoading: false,

  setAnomalies: (anomalies) => {
    const activeMap: Record<string, AnomalyEpisodeItem> = {};
    anomalies.forEach((a) => {
      if (a.status === "active") {
        activeMap[a.tourist_id] = a;
      }
    });
    set({ activeAnomalies: activeMap, history: anomalies });
  },

  addOrUpdateAnomaly: (payload) => {
    const existing = get().activeAnomalies[payload.tourist_id];
    const episode: AnomalyEpisodeItem = {
      anomaly_id: payload.anomaly_id,
      tourist_id: payload.tourist_id,
      session_id: payload.session_id,
      model_version: payload.model_version,
      started_at: existing ? existing.started_at : payload.timestamp,
      status: "active",
      current_score: payload.anomaly_score,
      peak_score: existing ? Math.max(existing.peak_score, payload.anomaly_score) : payload.anomaly_score,
      threshold: payload.threshold,
      window_count: existing ? existing.window_count + 1 : 1,
      duration_seconds: existing ? existing.duration_seconds + 1.0 : 0.0,
      quality: payload.quality,
      last_known_gps: payload.last_known_gps,
    };

    set({
      activeAnomalies: {
        ...get().activeAnomalies,
        [payload.tourist_id]: episode,
      },
    });
  },

  clearAnomaly: (tourist_id, duration, peak_score) => {
    const active = { ...get().activeAnomalies };
    const cleared = active[tourist_id];
    if (cleared) {
      delete active[tourist_id];
      const updatedHistory = [
        {
          ...cleared,
          status: "resolved" as const,
          cleared_at: new Date().toISOString(),
          duration_seconds: duration !== undefined ? duration : cleared.duration_seconds,
          peak_score: peak_score !== undefined ? peak_score : cleared.peak_score,
        },
        ...get().history,
      ].slice(0, 50);
      set({ activeAnomalies: active, history: updatedHistory });
    }
  },

  setLoading: (isLoading) => set({ isLoading }),
}));
