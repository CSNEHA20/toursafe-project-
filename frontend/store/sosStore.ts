import { create } from "zustand";
import type { Incident, SOSEvent, IncidentStatus } from "@/types";

interface SOSState {
  activeEvents: SOSEvent[];
  currentIncident: Incident | null;
  sosStatus: "idle" | "countdown" | "triggered" | "acknowledged" | "responding" | "resolved";
  countdownActive: boolean;
  countdownSeconds: number;
  isTriggering: boolean;
  addSOSEvent: (event: SOSEvent) => void;
  updateSOSEvent: (incident_id: string, status: IncidentStatus) => void;
  setCurrentIncident: (incident: Incident | null) => void;
  setSosStatus: (status: SOSState["sosStatus"]) => void;
  startCountdown: () => void;
  cancelCountdown: () => void;
  decrementCountdown: () => void;
  setTriggering: (v: boolean) => void;
}

export const useSOSStore = create<SOSState>((set, get) => ({
  activeEvents: [],
  currentIncident: null,
  sosStatus: "idle",
  countdownActive: false,
  countdownSeconds: 5,
  isTriggering: false,

  addSOSEvent: (event) =>
    set({ activeEvents: [event, ...get().activeEvents] }),

  updateSOSEvent: (incident_id, status) =>
    set({
      activeEvents: get().activeEvents.map((e) =>
        e.incident_id === incident_id ? { ...e, status } : e
      ),
    }),

  setCurrentIncident: (currentIncident) => set({ currentIncident }),
  setSosStatus: (sosStatus) => set({ sosStatus }),
  startCountdown: () => set({ countdownActive: true, countdownSeconds: 5, sosStatus: "countdown" }),
  cancelCountdown: () =>
    set({ countdownActive: false, countdownSeconds: 5, sosStatus: "idle" }),
  decrementCountdown: () => {
    const s = get().countdownSeconds - 1;
    if (s <= 0) {
      set({ countdownSeconds: 0, countdownActive: false });
    } else {
      set({ countdownSeconds: s });
    }
  },
  setTriggering: (isTriggering) => set({ isTriggering }),
}));

// Alias for backwards compat with tourist pages
export const useSosStore = useSOSStore;
