import { create } from "zustand";
import type { Incident, SOSEvent, IncidentStatus } from "@/types";

interface SOSState {
  activeEvents: SOSEvent[];
  currentIncident: Incident | null;
  activeIncidentId: string | null;
  activeSosId: string | null;
  sosStatus: "idle" | "countdown" | "pending_transmission" | "triggered" | "acknowledged" | "responding" | "resolved" | "cancelled";
  countdownActive: boolean;
  countdownSeconds: number;
  isTriggering: boolean;
  offlinePendingPayload: any | null;
  lastErrorMessage: string | null;
  
  addSOSEvent: (event: SOSEvent) => void;
  updateSOSEvent: (incident_id: string, status: IncidentStatus) => void;
  setCurrentIncident: (incident: Incident | null) => void;
  setActiveIncidentId: (id: string | null) => void;
  setActiveSosId: (id: string | null) => void;
  setSosStatus: (status: SOSState["sosStatus"]) => void;
  startCountdown: () => void;
  cancelCountdown: () => void;
  decrementCountdown: () => void;
  setTriggering: (v: boolean) => void;
  setOfflinePendingPayload: (payload: any | null) => void;
  setLastErrorMessage: (msg: string | null) => void;
  resetSOS: () => void;
}

export const useSOSStore = create<SOSState>((set, get) => ({
  activeEvents: [],
  currentIncident: null,
  activeIncidentId: null,
  activeSosId: null,
  sosStatus: "idle",
  countdownActive: false,
  countdownSeconds: 5,
  isTriggering: false,
  offlinePendingPayload: null,
  lastErrorMessage: null,

  addSOSEvent: (event) =>
    set({ activeEvents: [event, ...get().activeEvents] }),

  updateSOSEvent: (incident_id, status) =>
    set({
      activeEvents: get().activeEvents.map((e) =>
        e.incident_id === incident_id ? { ...e, status } : e
      ),
    }),

  setCurrentIncident: (currentIncident) => set({ currentIncident }),
  setActiveIncidentId: (activeIncidentId) => set({ activeIncidentId }),
  setActiveSosId: (activeSosId) => set({ activeSosId }),
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
  setOfflinePendingPayload: (offlinePendingPayload) => set({ offlinePendingPayload }),
  setLastErrorMessage: (lastErrorMessage) => set({ lastErrorMessage }),
  resetSOS: () => set({
    sosStatus: "idle",
    countdownActive: false,
    countdownSeconds: 5,
    isTriggering: false,
    activeIncidentId: null,
    activeSosId: null,
    offlinePendingPayload: null,
    lastErrorMessage: null,
  }),
}));

// Alias for backwards compat with tourist pages
export const useSosStore = useSOSStore;
