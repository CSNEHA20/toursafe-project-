/**
 * TourSafe Responder Store (Zustand)
 * Central field operations state store managing:
 * - Responder profile & availability state reconciliation
 * - Active incident assignment lifecycle & queue
 * - GPS tracking session telemetry
 * - Offline field notes queue & automatic background batch sync
 * - Mission history pagination
 * - Realtime diagnostics & network connectivity
 */

import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { responderApi, incidentAssignmentApi } from '@/lib/api';
import type {
  AssignmentHandoverRequest,
  AssignmentRecord,
  IncidentRecord,
  OfflineFieldNoteItem,
  ResponderHistoryItem,
  ResponderSelfProfile,
  ResponderStatus,
  SceneAssessmentRequest,
} from '@/types';

const OFFLINE_NOTES_STORAGE_KEY = '@toursafe_responder_offline_notes';

interface ResponderDiagnostics {
  wsConnected: boolean;
  lastGpsAgeSec: number;
  pendingNotesCount: number;
  batteryPct: number;
  activeSessionId: string | null;
  lastSyncTimestamp: string | null;
}

interface ResponderStoreState {
  // Core Profile & Assignment
  profile: ResponderSelfProfile | null;
  isLoading: boolean;
  isRefreshing: boolean;
  lastError: string | null;

  // Active Assignment Quick Access
  activeAssignment: AssignmentRecord | null;
  activeIncident: IncidentRecord | null;

  // GPS Telemetry
  currentGps: {
    latitude: number;
    longitude: number;
    accuracy?: number;
    speed?: number;
    heading?: number;
    timestamp: number;
  } | null;

  // Offline Field Notes
  offlineNotesQueue: OfflineFieldNoteItem[];
  isSyncingNotes: boolean;
  lastNotesSyncTime: string | null;

  // Mission History
  history: ResponderHistoryItem[];
  historyTotal: number;
  historyLoading: boolean;

  // Diagnostics
  diagnostics: ResponderDiagnostics;

  // Actions
  loadProfile: () => Promise<void>;
  updateAvailability: (status: ResponderStatus, reason?: string) => Promise<boolean>;
  toggleTrackingSession: (batteryPct?: number) => Promise<boolean>;
  sendGpsLocation: (coords: { latitude: number; longitude: number; accuracy?: number; speed?: number; heading?: number }) => Promise<void>;
  
  // Assignment Operations
  acceptAssignment: (incidentId: string, assignmentId: string, notes?: string) => Promise<boolean>;
  rejectAssignment: (incidentId: string, assignmentId: string, reason: string, details?: string) => Promise<boolean>;
  startResponse: (incidentId: string, assignmentId: string, notes?: string) => Promise<boolean>;
  markArrivedOnScene: (incidentId: string, assignmentId: string, override?: boolean, notes?: string) => Promise<boolean>;
  submitSceneAssessment: (incidentId: string, assignmentId: string, payload: SceneAssessmentRequest) => Promise<boolean>;
  requestHandover: (assignmentId: string, payload: AssignmentHandoverRequest) => Promise<boolean>;
  completeMission: (incidentId: string, assignmentId: string, completionReason: string, resolutionNotes?: string) => Promise<boolean>;

  // Offline Field Notes Queue
  addOfflineNote: (incidentId: string, content: string, latitude?: number, longitude?: number) => Promise<void>;
  syncPendingNotes: () => Promise<number>;
  loadSavedOfflineNotes: () => Promise<void>;

  // History
  loadHistory: (limit?: number, skip?: number) => Promise<void>;

  // Realtime & Diagnostics
  setWsConnected: (connected: boolean) => void;
  updateBattery: (pct: number) => void;
  reset: () => void;
}

export const useResponderStore = create<ResponderStoreState>((set, get) => ({
  profile: null,
  isLoading: false,
  isRefreshing: false,
  lastError: null,

  activeAssignment: null,
  activeIncident: null,

  currentGps: null,

  offlineNotesQueue: [],
  isSyncingNotes: false,
  lastNotesSyncTime: null,

  history: [],
  historyTotal: 0,
  historyLoading: false,

  diagnostics: {
    wsConnected: false,
    lastGpsAgeSec: 0,
    pendingNotesCount: 0,
    batteryPct: 100,
    activeSessionId: null,
    lastSyncTimestamp: null,
  },

  loadProfile: async () => {
    try {
      const res = await responderApi.getMe();
      if (res?.data) {
        const p = res.data;
        set({
          profile: p,
          activeAssignment: p.active_assignment || null,
          activeIncident: p.active_incident || null,
          lastError: null,
          diagnostics: {
            ...get().diagnostics,
            activeSessionId: p.tracking_session?.session_id || null,
          },
        });
      }
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to load responder profile' });
    }
  },

  updateAvailability: async (status: ResponderStatus, reason?: string) => {
    try {
      set({ isLoading: true, lastError: null });
      const res = await responderApi.updateStatus(status, reason);
      if (res?.data) {
        await get().loadProfile();
        return true;
      }
      return false;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to update availability' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  toggleTrackingSession: async (batteryPct?: number) => {
    const profile = get().profile;
    if (!profile?.responder) return false;
    const isCurrentlyTracking = profile.responder.tracking_active;
    try {
      if (isCurrentlyTracking) {
        await responderApi.stopTracking(batteryPct);
      } else {
        await responderApi.startTracking(batteryPct);
      }
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to toggle GPS tracking' });
      return false;
    }
  },

  sendGpsLocation: async (coords) => {
    const now = Date.now();
    set({
      currentGps: {
        ...coords,
        timestamp: now,
      },
      diagnostics: {
        ...get().diagnostics,
        lastGpsAgeSec: 0,
      },
    });

    try {
      const activeSessionId = get().profile?.tracking_session?.session_id;
      await responderApi.updateLocation({
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: coords.accuracy,
        speed: coords.speed,
        heading: coords.heading,
        tracking_session_id: activeSessionId || undefined,
        timestamp: new Date(now).toISOString(),
      });
    } catch (err) {
      // Background location transmission failed, will retry next interval
    }
  },

  acceptAssignment: async (incidentId: string, assignmentId: string, notes?: string) => {
    try {
      set({ isLoading: true, lastError: null });
      await incidentAssignmentApi.acceptAssignment(incidentId, assignmentId, notes);
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to accept assignment' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  rejectAssignment: async (incidentId: string, assignmentId: string, reason: string, details?: string) => {
    try {
      set({ isLoading: true, lastError: null });
      await incidentAssignmentApi.rejectAssignment(incidentId, assignmentId, { reason, details });
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to reject assignment' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  startResponse: async (incidentId: string, assignmentId: string, notes?: string) => {
    try {
      set({ isLoading: true, lastError: null });
      await incidentAssignmentApi.startResponse(incidentId, assignmentId, notes);
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to start response' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  markArrivedOnScene: async (incidentId: string, assignmentId: string, override = false, notes?: string) => {
    const currentGps = get().currentGps;
    try {
      set({ isLoading: true, lastError: null });
      await incidentAssignmentApi.markArrived(incidentId, assignmentId, {
        latitude: currentGps?.latitude,
        longitude: currentGps?.longitude,
        accuracy: currentGps?.accuracy,
        force_override: override,
        notes,
      });
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to confirm arrival on scene' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  submitSceneAssessment: async (incidentId: string, assignmentId: string, payload: SceneAssessmentRequest) => {
    try {
      set({ isLoading: true, lastError: null });
      await incidentAssignmentApi.submitSceneAssessment(incidentId, assignmentId, payload);
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to submit scene assessment' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  requestHandover: async (assignmentId: string, payload: AssignmentHandoverRequest) => {
    try {
      set({ isLoading: true, lastError: null });
      await responderApi.requestHandover(assignmentId, payload);
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to request handover' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  completeMission: async (incidentId: string, assignmentId: string, completionReason: string, resolutionNotes?: string) => {
    try {
      set({ isLoading: true, lastError: null });
      await incidentAssignmentApi.completeResponse(incidentId, assignmentId, {
        completion_reason: completionReason,
        resolution_notes: resolutionNotes,
      });
      await get().loadProfile();
      return true;
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to complete mission' });
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  addOfflineNote: async (incidentId: string, content: string, latitude?: number, longitude?: number) => {
    const noteId = `note_local_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const newNote: OfflineFieldNoteItem = {
      client_note_id: noteId,
      incident_id: incidentId,
      content,
      recorded_at: new Date().toISOString(),
      latitude,
      longitude,
    };

    const updatedQueue = [...get().offlineNotesQueue, newNote];
    set({
      offlineNotesQueue: updatedQueue,
      diagnostics: {
        ...get().diagnostics,
        pendingNotesCount: updatedQueue.length,
      },
    });

    try {
      await AsyncStorage.setItem(OFFLINE_NOTES_STORAGE_KEY, JSON.stringify(updatedQueue));
    } catch (e) {
      // storage write fail fallback
    }

    // Try immediate background sync
    await get().syncPendingNotes();
  },

  syncPendingNotes: async () => {
    const queue = get().offlineNotesQueue;
    if (!queue.length || get().isSyncingNotes) return 0;

    try {
      set({ isSyncingNotes: true });
      const res = await responderApi.syncFieldNotes({ notes: queue });
      if (res?.data) {
        const syncedIds = new Set(res.data.synced_ids || []);
        const remainingQueue = queue.filter((item) => !syncedIds.has(item.client_note_id));
        const nowIso = new Date().toISOString();

        set({
          offlineNotesQueue: remainingQueue,
          lastNotesSyncTime: nowIso,
          diagnostics: {
            ...get().diagnostics,
            pendingNotesCount: remainingQueue.length,
            lastSyncTimestamp: nowIso,
          },
        });

        await AsyncStorage.setItem(OFFLINE_NOTES_STORAGE_KEY, JSON.stringify(remainingQueue));
        return res.data.synced_count;
      }
    } catch (err) {
      // offline or network failure, will retry next cycle
    } finally {
      set({ isSyncingNotes: false });
    }
    return 0;
  },

  loadSavedOfflineNotes: async () => {
    try {
      const stored = await AsyncStorage.getItem(OFFLINE_NOTES_STORAGE_KEY);
      if (stored) {
        const queue = JSON.parse(stored);
        if (Array.isArray(queue)) {
          set({
            offlineNotesQueue: queue,
            diagnostics: {
              ...get().diagnostics,
              pendingNotesCount: queue.length,
            },
          });
        }
      }
    } catch (e) {
      // storage read fallback
    }
  },

  loadHistory: async (limit = 20, skip = 0) => {
    try {
      set({ historyLoading: true });
      const res = await responderApi.getHistory({ limit, skip });
      if (res?.data) {
        set({
          history: res.data.items || [],
          historyTotal: res.data.total || 0,
        });
      }
    } catch (err: any) {
      set({ lastError: err?.response?.data?.detail || err?.message || 'Failed to load mission history' });
    } finally {
      set({ historyLoading: false });
    }
  },

  setWsConnected: (wsConnected) =>
    set({
      diagnostics: {
        ...get().diagnostics,
        wsConnected,
      },
    }),

  updateBattery: (batteryPct) =>
    set({
      diagnostics: {
        ...get().diagnostics,
        batteryPct,
      },
    }),

  reset: () =>
    set({
      profile: null,
      activeAssignment: null,
      activeIncident: null,
      currentGps: null,
      lastError: null,
      history: [],
      historyTotal: 0,
    }),
}));
