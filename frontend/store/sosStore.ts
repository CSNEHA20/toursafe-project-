import { create } from "zustand";
import type { Incident, SOSEvent, IncidentStatus } from "@/types";
import { touristApi } from "@/lib/api";

interface ResponderInfo {
  id?: string;
  name?: string;
  role?: string;
  unit?: string;
  phone?: string;
  eta_minutes?: number;
}

interface SOSState {
  activeEvents: SOSEvent[];
  currentIncident: Incident | null;
  activeIncidentId: string | null;
  activeSosId: string | null;
  sosStatus: "idle" | "countdown" | "pending_transmission" | "triggered" | "acknowledged" | "responding" | "resolved" | "cancelled";
  incidentState: string | null;
  assignedResponder: ResponderInfo | null;
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
  setSOSStatus: (status: SOSState["sosStatus"]) => void;
  setIncidentState: (state: string | null) => void;
  setAssignedResponder: (responder: ResponderInfo | null) => void;
  startCountdown: () => void;
  cancelCountdown: () => void;
  decrementCountdown: () => void;
  setTriggering: (v: boolean) => void;
  setOfflinePendingPayload: (payload: any | null) => void;
  setLastErrorMessage: (msg: string | null) => void;
  triggerSOS: (latitude: number, longitude: number, accuracy?: number, description?: string) => Promise<any>;
  cancelSOS: (reason: string) => Promise<boolean>;
  resetSOS: () => void;
}

export const useSOSStore = create<SOSState>((set, get) => ({
  activeEvents: [],
  currentIncident: null,
  activeIncidentId: null,
  activeSosId: null,
  sosStatus: "idle",
  incidentState: null,
  assignedResponder: null,
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
  setSOSStatus: (sosStatus) => set({ sosStatus }),
  setIncidentState: (incidentState) => set({ incidentState }),
  setAssignedResponder: (assignedResponder) => set({ assignedResponder }),
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

  triggerSOS: async (latitude, longitude, accuracy, description) => {
    set({ isTriggering: true, sosStatus: "pending_transmission" });
    try {
      const clientRequestId = `sos_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      const res = await touristApi.triggerSOS({
        latitude,
        longitude,
        accuracy: accuracy || 10,
        description: description || "Emergency SOS from mobile companion",
        client_request_id: clientRequestId,
      });

      const incidentId = res.data?.incident_id || `inc_${Date.now()}`;
      set({
        sosStatus: "triggered",
        activeIncidentId: incidentId,
        incidentState: "DISPATCHED",
        isTriggering: false,
      });
      return res.data;
    } catch (err: any) {
      // Buffer offline
      set({
        sosStatus: "triggered",
        activeIncidentId: `offline_inc_${Date.now()}`,
        incidentState: "QUEUED_OFFLINE",
        isTriggering: false,
      });
      throw err;
    }
  },

  cancelSOS: async (reason) => {
    const incidentId = get().activeIncidentId;
    try {
      if (incidentId) {
        try {
          await touristApi.cancelSOS({ incident_id: incidentId, reason });
        } catch {
          // Local stand-down fallback
        }
      }
      get().resetSOS();
      return true;
    } catch (err) {
      get().resetSOS();
      return false;
    }
  },

  resetSOS: () => set({
    sosStatus: "idle",
    incidentState: null,
    assignedResponder: null,
    countdownActive: false,
    countdownSeconds: 5,
    isTriggering: false,
    activeIncidentId: null,
    activeSosId: null,
    offlinePendingPayload: null,
    lastErrorMessage: null,
  }),
}));

export const useSosStore = useSOSStore;
