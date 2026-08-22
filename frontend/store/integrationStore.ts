/**
 * TourSafe External Integrations & Interoperability Store
 */

import { create } from 'zustand';
import {
  DeadLetterRecord,
  ExternalStateConflict,
  IntegrationAuditLog,
  IntegrationConfig,
  IntegrationRegistration,
} from '../types/integrations';

interface IntegrationState {
  integrations: IntegrationRegistration[];
  deadLetters: DeadLetterRecord[];
  auditLogs: IntegrationAuditLog[];
  conflicts: ExternalStateConflict[];
  selectedIntegration: IntegrationRegistration | null;
  loading: boolean;
  testingProvider: string | null;
  testResult: any | null;
  error: string | null;

  // Actions
  fetchIntegrations: (token: string) => Promise<void>;
  fetchDeadLetters: (token: string, resolved?: boolean) => Promise<void>;
  fetchAuditLogs: (token: string, limit?: number) => Promise<void>;
  fetchConflicts: (token: string, resolved?: boolean) => Promise<void>;
  testConnection: (token: string, providerName: string) => Promise<any>;
  updateConfig: (token: string, providerName: string, updates: Partial<IntegrationConfig>) => Promise<boolean>;
  retryDeadLetter: (token: string, recordId: string) => Promise<boolean>;
  resolveConflict: (token: string, conflictId: string, policy: string, chosenStatus: string) => Promise<boolean>;
  setSelectedIntegration: (integration: IntegrationRegistration | null) => void;
  clearTestResult: () => void;
}

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export const useIntegrationStore = create<IntegrationState>((set, get) => ({
  integrations: [],
  deadLetters: [],
  auditLogs: [],
  conflicts: [],
  selectedIntegration: null,
  loading: false,
  testingProvider: null,
  testResult: null,
  error: null,

  fetchIntegrations: async (token: string) => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations`, {
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`Failed to load integrations: ${res.statusText}`);
      const data = await res.json();
      set({ integrations: data, loading: false });
    } catch (e: any) {
      set({ error: e.message || 'Error fetching integrations', loading: false });
    }
  },

  fetchDeadLetters: async (token: string, resolved?: boolean) => {
    try {
      const url = new URL(`${API_BASE}/api/v1/integrations/queue/dead-letter`);
      if (resolved !== undefined) url.searchParams.append('resolved', String(resolved));
      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`Failed to load dead letters: ${res.statusText}`);
      const data = await res.json();
      set({ deadLetters: data });
    } catch (e: any) {
      console.warn('Error fetching dead letters:', e);
    }
  },

  fetchAuditLogs: async (token: string, limit: number = 50) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/logs/audit?limit=${limit}`, {
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`Failed to load integration logs: ${res.statusText}`);
      const data = await res.json();
      set({ auditLogs: data });
    } catch (e: any) {
      console.warn('Error fetching integration logs:', e);
    }
  },

  fetchConflicts: async (token: string, resolved?: boolean) => {
    try {
      const url = new URL(`${API_BASE}/api/v1/integrations/emergency-sync/conflicts`);
      if (resolved !== undefined) url.searchParams.append('resolved', String(resolved));
      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`Failed to load conflicts: ${res.statusText}`);
      const data = await res.json();
      set({ conflicts: data });
    } catch (e: any) {
      console.warn('Error fetching conflicts:', e);
    }
  },

  testConnection: async (token: string, providerName: string) => {
    set({ testingProvider: providerName, testResult: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/${providerName}/test`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      });
      const data = await res.json();
      set({ testResult: data, testingProvider: null });
      // Refresh list to update health status
      get().fetchIntegrations(token);
      return data;
    } catch (e: any) {
      const errRes = { success: false, detail: e.message || 'Connection test failed', latency_ms: 0 };
      set({ testResult: errRes, testingProvider: null });
      return errRes;
    }
  },

  updateConfig: async (token: string, providerName: string, updates: Partial<IntegrationConfig>) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/${providerName}/config`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error('Failed to update config');
      await get().fetchIntegrations(token);
      return true;
    } catch (e: any) {
      set({ error: e.message || 'Error updating config' });
      return false;
    }
  },

  retryDeadLetter: async (token: string, recordId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/queue/dead-letter/${recordId}/retry`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      });
      if (!res.ok) throw new Error('Failed to retry dead letter record');
      await get().fetchDeadLetters(token);
      await get().fetchAuditLogs(token);
      return true;
    } catch (e: any) {
      return false;
    }
  },

  resolveConflict: async (token: string, conflictId: string, policy: string, chosenStatus: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/integrations/emergency-sync/conflicts/${conflictId}/resolve`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ policy, chosen_status: chosenStatus }),
      });
      if (!res.ok) throw new Error('Failed to resolve state conflict');
      await get().fetchConflicts(token);
      return true;
    } catch (e: any) {
      return false;
    }
  },

  setSelectedIntegration: (integration: IntegrationRegistration | null) => set({ selectedIntegration: integration }),
  clearTestResult: () => set({ testResult: null, testingProvider: null }),
}));
