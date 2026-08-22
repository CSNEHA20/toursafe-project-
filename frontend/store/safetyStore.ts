/**
 * TourSafe - Safety Store (Zustand)
 * Manages live multi-signal safety state, active incidents, decisions audit timeline, and alert notifications.
 */

import { create } from "zustand";
import type {
  ActiveSafetyState,
  IncidentRecord,
  SafetyDecisionRecord,
  SafetyState,
  TouristSafetyStatusResponse,
} from "@/types/safety";

interface SafetyStoreState {
  touristSafetyStatus: TouristSafetyStatusResponse | null;
  activeSafetyStates: Record<string, ActiveSafetyState>; // tourist_id -> ActiveSafetyState
  activeIncidents: Record<string, IncidentRecord>; // incident_id -> IncidentRecord
  recentDecisions: SafetyDecisionRecord[];
  selectedTouristSafety: ActiveSafetyState | null;
  isLoading: boolean;
  error: string | null;

  setTouristSafetyStatus: (status: TouristSafetyStatusResponse | null) => void;
  updateActiveSafetyState: (state: ActiveSafetyState) => void;
  upsertIncident: (incident: IncidentRecord) => void;
  removeIncident: (incidentId: string) => void;
  setRecentDecisions: (decisions: SafetyDecisionRecord[]) => void;
  appendDecision: (decision: SafetyDecisionRecord) => void;
  setSelectedTouristSafety: (state: ActiveSafetyState | null) => void;
  handleRealtimeSafetyEvent: (eventPayload: any) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useSafetyStore = create<SafetyStoreState>((set, get) => ({
  touristSafetyStatus: null,
  activeSafetyStates: {},
  activeIncidents: {},
  recentDecisions: [],
  selectedTouristSafety: null,
  isLoading: false,
  error: null,

  setTouristSafetyStatus: (touristSafetyStatus) => set({ touristSafetyStatus }),

  updateActiveSafetyState: (state) => {
    set((prev) => ({
      activeSafetyStates: {
        ...prev.activeSafetyStates,
        [state.tourist_id]: state,
      },
    }));
  },

  upsertIncident: (incident) => {
    set((prev) => ({
      activeIncidents: {
        ...prev.activeIncidents,
        [incident.incident_id]: incident,
      },
    }));
  },

  removeIncident: (incidentId) => {
    set((prev) => {
      const updated = { ...prev.activeIncidents };
      delete updated[incidentId];
      return { activeIncidents: updated };
    });
  },

  setRecentDecisions: (recentDecisions) => set({ recentDecisions }),

  appendDecision: (decision) => {
    set((prev) => ({
      recentDecisions: [decision, ...prev.recentDecisions.slice(0, 49)],
    }));
  },

  setSelectedTouristSafety: (selectedTouristSafety) => set({ selectedTouristSafety }),

  handleRealtimeSafetyEvent: (eventPayload) => {
    if (!eventPayload) return;
    const { event_type, data } = eventPayload;

    if (event_type === "safety.state_changed" && data) {
      const activeState: ActiveSafetyState = {
        tourist_id: data.tourist_id,
        current_state: data.current_state,
        previous_state: data.previous_state,
        decision_id: data.decision_id || "",
        started_at: data.started_at || data.timestamp || new Date().toISOString(),
        last_update: data.timestamp || new Date().toISOString(),
        last_evaluated_at: data.timestamp,
        active_incident_id: data.incident_id,
        last_decision_id: data.decision_id || "",
        rule_version: data.rule_version || "safety-rules-v1",
        reasons: data.reasons || [],
        active_reasons: data.reasons || [],
        active_signals_summary: data.signals || {},
        quality: data.quality || "GOOD",
        confidence_class: data.confidence_class || "HIGH",
        risk_score: data.risk_score,
        risk_assessment: data.risk_assessment,
      };
      get().updateActiveSafetyState(activeState);
    } else if (
      (event_type === "incident.created" || event_type === "incident.updated") &&
      data
    ) {
      const inc: IncidentRecord = {
        incident_id: data.incident_id,
        tourist_id: data.tourist_id,
        session_id: data.session_id,
        started_at: data.started_at,
        updated_at: data.updated_at,
        status: data.status,
        severity: data.severity,
        decision_id: data.decision_id,
        rule_version: data.rule_version,
        reasons: data.reasons || [],
        signal_summary: data.signal_summary || {},
      };
      get().upsertIncident(inc);
    } else if (event_type === "incident.resolved" && data) {
      if (data.incident_id) {
        get().removeIncident(data.incident_id);
      }
    }
  },

  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      touristSafetyStatus: null,
      activeSafetyStates: {},
      activeIncidents: {},
      recentDecisions: [],
      selectedTouristSafety: null,
      isLoading: false,
      error: null,
    }),
}));
