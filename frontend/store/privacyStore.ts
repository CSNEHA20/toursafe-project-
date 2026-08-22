import { create } from 'zustand';
import { ConsentPurpose, ConsentRecord, PrivacyRequest, PrivacyRequestType } from '../types/privacy';

interface PrivacyState {
  consents: ConsentRecord[];
  requests: PrivacyRequest[];
  isLoading: boolean;
  error: string | null;

  fetchConsents: () => Promise<void>;
  grantConsent: (purpose: ConsentPurpose) => Promise<boolean>;
  withdrawConsent: (purpose: ConsentPurpose, reason?: string) => Promise<boolean>;

  fetchRequests: () => Promise<void>;
  submitRequest: (type: PrivacyRequestType, scope?: any[], notes?: string, correction?: any) => Promise<PrivacyRequest | null>;
  verifyRequest: (requestId: string) => Promise<boolean>;
  reviewRequest: (requestId: string, decision: string, reason?: string) => Promise<boolean>;
}

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export const usePrivacyStore = create<PrivacyState>((set, get) => ({
  consents: [],
  requests: [],
  isLoading: false,
  error: null,

  fetchConsents: async () => {
    try {
      set({ isLoading: true, error: null });
      const res = await fetch(`${API_BASE}/api/v1/privacy/consents`);
      if (res.ok) {
        const data = await res.json();
        set({ consents: data });
      }
    } catch (e: any) {
      set({ error: e.message });
    } finally {
      set({ isLoading: false });
    }
  },

  grantConsent: async (purpose: ConsentPurpose) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/privacy/consents/grant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ purpose }),
      });
      if (res.ok) {
        await get().fetchConsents();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  withdrawConsent: async (purpose: ConsentPurpose, reason?: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/privacy/consents/withdraw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ purpose, reason }),
      });
      if (res.ok) {
        await get().fetchConsents();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchRequests: async () => {
    try {
      set({ isLoading: true, error: null });
      const res = await fetch(`${API_BASE}/api/v1/privacy/requests`);
      if (res.ok) {
        const data = await res.json();
        set({ requests: data });
      }
    } catch (e: any) {
      set({ error: e.message });
    } finally {
      set({ isLoading: false });
    }
  },

  submitRequest: async (type, scope, notes, correction) => {
    try {
      set({ isLoading: true, error: null });
      const res = await fetch(`${API_BASE}/api/v1/privacy/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_type: type,
          scope,
          notes,
          correction_payload: correction,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        set((state) => ({ requests: [data, ...state.requests] }));
        return data;
      }
      return null;
    } catch (e: any) {
      set({ error: e.message });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  verifyRequest: async (requestId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/privacy/requests/${requestId}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: 'SESSION_AUTH' }),
      });
      if (res.ok) {
        await get().fetchRequests();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  reviewRequest: async (requestId: string, decision: string, reason?: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/privacy/requests/${requestId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, rejection_reason: reason }),
      });
      if (res.ok) {
        await get().fetchRequests();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },
}));
