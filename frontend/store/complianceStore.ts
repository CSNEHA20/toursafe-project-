import { create } from 'zustand';
import {
  AccessReview,
  BreakGlassSession,
  ComplianceControl,
  FrameworkReadinessReport,
  FrameworkType,
  LegalHold,
  RetentionPolicy,
  VendorIntegration,
} from '../types/compliance';

interface ComplianceState {
  policies: RetentionPolicy[];
  legalHolds: LegalHold[];
  vendors: VendorIntegration[];
  accessReviews: AccessReview[];
  breakGlassSessions: BreakGlassSession[];
  controls: ComplianceControl[];
  readinessReports: Record<string, FrameworkReadinessReport>;
  isLoading: boolean;
  error: string | null;

  fetchPolicies: () => Promise<void>;
  createPolicy: (data: Partial<RetentionPolicy>) => Promise<RetentionPolicy | null>;
  approvePolicy: (policyId: string) => Promise<boolean>;
  rollbackPolicy: (policyId: string, targetVersion: number) => Promise<boolean>;
  triggerRetentionRun: (dryRun?: boolean) => Promise<any>;

  fetchLegalHolds: () => Promise<void>;
  createLegalHold: (data: any) => Promise<LegalHold | null>;
  releaseLegalHold: (holdId: string, reason: string) => Promise<boolean>;

  fetchVendors: () => Promise<void>;
  updateVendorReview: (vendorId: string, reviewStatus: string, contractStatus?: string) => Promise<boolean>;

  fetchAccessReviews: () => Promise<void>;
  createAccessReview: (title: string, scope: string, start: string, end: string) => Promise<boolean>;
  requestBreakGlass: (role: string, justification: string, scope: string, hours?: number) => Promise<BreakGlassSession | null>;
  fetchBreakGlassSessions: () => Promise<void>;
  revokeBreakGlass: (sessionId: string) => Promise<boolean>;

  fetchFrameworkReadiness: (framework: FrameworkType) => Promise<FrameworkReadinessReport | null>;
  fetchAuditorExport: () => Promise<any>;
}

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export const useComplianceStore = create<ComplianceState>((set, get) => ({
  policies: [],
  legalHolds: [],
  vendors: [],
  accessReviews: [],
  breakGlassSessions: [],
  controls: [],
  readinessReports: {},
  isLoading: false,
  error: null,

  fetchPolicies: async () => {
    try {
      set({ isLoading: true, error: null });
      const res = await fetch(`${API_BASE}/api/v1/compliance/policies`);
      if (res.ok) {
        const data = await res.json();
        set({ policies: data });
      }
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch retention policies' });
    } finally {
      set({ isLoading: false });
    }
  },

  createPolicy: async (payload) => {
    try {
      set({ isLoading: true, error: null });
      const res = await fetch(`${API_BASE}/api/v1/compliance/policies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        set((state) => ({ policies: [data, ...state.policies] }));
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

  approvePolicy: async (policyId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/policies/${policyId}/approve`, {
        method: 'POST',
      });
      if (res.ok) {
        await get().fetchPolicies();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  rollbackPolicy: async (policyId: string, targetVersion: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/policies/${policyId}/rollback?target_version=${targetVersion}`, {
        method: 'POST',
      });
      if (res.ok) {
        await get().fetchPolicies();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  triggerRetentionRun: async (dryRun = false) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/retention/run?dry_run=${dryRun}`, {
        method: 'POST',
      });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  },

  fetchLegalHolds: async () => {
    try {
      set({ isLoading: true });
      const res = await fetch(`${API_BASE}/api/v1/compliance/legal-holds`);
      if (res.ok) {
        const data = await res.json();
        set({ legalHolds: data });
      }
    } catch (e: any) {
      set({ error: e.message });
    } finally {
      set({ isLoading: false });
    }
  },

  createLegalHold: async (payload) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/legal-holds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        set((state) => ({ legalHolds: [data, ...state.legalHolds] }));
        return data;
      }
      return null;
    } catch {
      return null;
    }
  },

  releaseLegalHold: async (holdId: string, reason: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/legal-holds/${holdId}/release`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ release_reason: reason }),
      });
      if (res.ok) {
        await get().fetchLegalHolds();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchVendors: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/vendors`);
      if (res.ok) {
        const data = await res.json();
        set({ vendors: data });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  updateVendorReview: async (vendorId, reviewStatus, contractStatus) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/vendors/${vendorId}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          security_review_status: reviewStatus,
          contract_status: contractStatus,
        }),
      });
      if (res.ok) {
        await get().fetchVendors();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchAccessReviews: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/access-reviews`);
      if (res.ok) {
        const data = await res.json();
        set({ accessReviews: data });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  createAccessReview: async (title, scope, start, end) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/access-reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          scope,
          period_start: start,
          period_end: end,
        }),
      });
      if (res.ok) {
        await get().fetchAccessReviews();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  requestBreakGlass: async (role, justification, scope, hours = 2) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/break-glass`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requested_role: role,
          justification,
          target_scope: scope,
          duration_hours: hours,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        await get().fetchBreakGlassSessions();
        return data;
      }
      return null;
    } catch {
      return null;
    }
  },

  fetchBreakGlassSessions: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/break-glass`);
      if (res.ok) {
        const data = await res.json();
        set({ breakGlassSessions: data });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  revokeBreakGlass: async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/break-glass/${sessionId}/revoke`, {
        method: 'POST',
      });
      if (res.ok) {
        await get().fetchBreakGlassSessions();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchFrameworkReadiness: async (framework: FrameworkType) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/frameworks/${framework}/readiness`);
      if (res.ok) {
        const report = await res.json();
        set((state) => ({
          readinessReports: { ...state.readinessReports, [framework]: report },
        }));
        return report;
      }
      return null;
    } catch {
      return null;
    }
  },

  fetchAuditorExport: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/compliance/auditor/export`);
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  },
}));
