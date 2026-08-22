/**
 * TourSafe Authority Administration & Governance Store
 */

import { create } from 'zustand';
import {
  AdminOverviewMetrics,
  ConfigurationDiffResult,
  GovernanceConfigurationRecord,
  ImmutableAuditRecord,
  JurisdictionModel,
  OrganizationModel,
  PolicySimulationResult,
  SafetyRuleSimulationResult,
  SystemHealthOverview,
} from '../types/governance';

interface GovernanceState {
  metrics: AdminOverviewMetrics | null;
  organizations: OrganizationModel[];
  jurisdictions: JurisdictionModel[];
  configurations: GovernanceConfigurationRecord[];
  activeConfig: GovernanceConfigurationRecord | null;
  diffResult: ConfigurationDiffResult | null;
  auditLogs: ImmutableAuditRecord[];
  auditTotal: number;
  auditPage: number;
  systemHealth: SystemHealthOverview | null;
  policySimulation: PolicySimulationResult | null;
  safetySimulation: SafetyRuleSimulationResult | null;
  loading: boolean;
  error: string | null;

  // Actions
  fetchOverview: (token: string, jurisdictionId?: string) => Promise<void>;
  fetchOrganizations: (token: string) => Promise<void>;
  fetchJurisdictions: (token: string) => Promise<void>;
  fetchConfigurations: (token: string, type?: string) => Promise<void>;
  fetchAuditLogs: (token: string, page?: number, search?: string) => Promise<void>;
  fetchSystemHealth: (token: string) => Promise<void>;
  createDraftConfig: (token: string, payload: any) => Promise<GovernanceConfigurationRecord | null>;
  validateConfig: (token: string, configId: string) => Promise<any>;
  approveConfig: (token: string, configId: string, reason: string) => Promise<boolean>;
  rejectConfig: (token: string, configId: string, reason: string) => Promise<boolean>;
  activateConfig: (token: string, configId: string, reason: string) => Promise<boolean>;
  rollbackConfig: (token: string, targetVersionId: string, reason: string) => Promise<boolean>;
  computeDiff: (token: string, srcId: string, tgtId: string) => Promise<void>;
  runPolicySimulation: (token: string, policyId: string, context: any) => Promise<void>;
  runSafetySimulation: (token: string, candidateConfigId?: string, customParams?: any) => Promise<void>;
}

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export const useGovernanceStore = create<GovernanceState>((set, get) => ({
  metrics: null,
  organizations: [],
  jurisdictions: [],
  configurations: [],
  activeConfig: null,
  diffResult: null,
  auditLogs: [],
  auditTotal: 0,
  auditPage: 1,
  systemHealth: null,
  policySimulation: null,
  safetySimulation: null,
  loading: false,
  error: null,

  fetchOverview: async (token: string, jurisdictionId?: string) => {
    set({ loading: true, error: null });
    try {
      const url = new URL(`${API_BASE}/api/v1/admin/overview`);
      if (jurisdictionId) url.searchParams.append('jurisdiction_id', jurisdictionId);

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ metrics: data, loading: false });
      } else {
        set({ error: 'Failed to load overview metrics', loading: false });
      }
    } catch (err: any) {
      set({ error: err.message || 'Error fetching overview', loading: false });
    }
  },

  fetchOrganizations: async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/organizations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ organizations: data });
      }
    } catch (err) {
      console.error('Error loading organizations:', err);
    }
  },

  fetchJurisdictions: async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/jurisdictions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ jurisdictions: data });
      }
    } catch (err) {
      console.error('Error loading jurisdictions:', err);
    }
  },

  fetchConfigurations: async (token: string, type?: string) => {
    set({ loading: true });
    try {
      const url = new URL(`${API_BASE}/api/v1/admin/configurations`);
      if (type) url.searchParams.append('type', type);

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ configurations: data, loading: false });
      } else {
        set({ loading: false });
      }
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchAuditLogs: async (token: string, page = 1, search?: string) => {
    try {
      const url = new URL(`${API_BASE}/api/v1/admin/audit`);
      url.searchParams.append('page', page.toString());
      url.searchParams.append('limit', '25');
      if (search) url.searchParams.append('search', search);

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ auditLogs: data.items, auditTotal: data.total, auditPage: page });
      }
    } catch (err) {
      console.error('Error loading audit logs:', err);
    }
  },

  fetchSystemHealth: async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/system/health`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ systemHealth: data });
      }
    } catch (err) {
      console.error('Error loading system health:', err);
    }
  },

  createDraftConfig: async (token: string, payload: any) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/configurations`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const created = await res.json();
        set((state) => ({ configurations: [created, ...state.configurations] }));
        return created;
      }
    } catch (err) {
      console.error('Error creating draft config:', err);
    }
    return null;
  },

  validateConfig: async (token: string, configId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/configurations/${configId}/validate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.error('Error validating config:', err);
    }
    return null;
  },

  approveConfig: async (token: string, configId: string, reason: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/configurations/${configId}/approve`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason }),
      });
      if (res.ok) {
        await get().fetchConfigurations(token);
        return true;
      }
    } catch (err) {
      console.error('Error approving config:', err);
    }
    return false;
  },

  rejectConfig: async (token: string, configId: string, reason: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/configurations/${configId}/reject`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ rejection_reason: reason }),
      });
      if (res.ok) {
        await get().fetchConfigurations(token);
        return true;
      }
    } catch (err) {
      console.error('Error rejecting config:', err);
    }
    return false;
  },

  activateConfig: async (token: string, configId: string, reason: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/configurations/${configId}/activate`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason }),
      });
      if (res.ok) {
        await get().fetchConfigurations(token);
        await get().fetchOverview(token);
        return true;
      }
    } catch (err) {
      console.error('Error activating config:', err);
    }
    return false;
  },

  rollbackConfig: async (token: string, targetVersionId: string, reason: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/configurations/rollback`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ target_version_id: targetVersionId, reason }),
      });
      if (res.ok) {
        await get().fetchConfigurations(token);
        await get().fetchOverview(token);
        return true;
      }
    } catch (err) {
      console.error('Error rolling back config:', err);
    }
    return false;
  },

  computeDiff: async (token: string, srcId: string, tgtId: string) => {
    try {
      const url = new URL(`${API_BASE}/api/v1/admin/configurations/diff`);
      url.searchParams.append('source_config_id', srcId);
      url.searchParams.append('target_config_id', tgtId);

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ diffResult: data });
      }
    } catch (err) {
      console.error('Error computing diff:', err);
    }
  },

  runPolicySimulation: async (token: string, policyId: string, context: any) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/policies/simulate?policy_id=${policyId}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(context),
      });
      if (res.ok) {
        const data = await res.json();
        set({ policySimulation: data });
      }
    } catch (err) {
      console.error('Error running policy simulation:', err);
    }
  },

  runSafetySimulation: async (token: string, candidateConfigId?: string, customParams?: any) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/safety-config/simulate`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          candidate_config_id: candidateConfigId,
          custom_parameters: customParams,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        set({ safetySimulation: data });
      }
    } catch (err) {
      console.error('Error running safety simulation:', err);
    }
  },
}));
