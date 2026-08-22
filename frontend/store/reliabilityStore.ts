import { create } from 'zustand';
import {
  SystemMode,
  GoldenSignalsData,
  SubsystemMetricsData,
  SLOItem,
  DeadLetterItem,
  BackupItem,
} from '../types/reliability';

interface ReliabilityState {
  systemMode: SystemMode;
  modeReason: string;
  uptimeSeconds: number;
  goldenSignals: GoldenSignalsData | null;
  subsystems: SubsystemMetricsData | null;
  slos: SLOItem[];
  deadLetters: DeadLetterItem[];
  backups: BackupItem[];
  isLoading: boolean;
  error: string | null;

  fetchMetrics: () => Promise<void>;
  fetchSLOs: () => Promise<void>;
  fetchDegradation: () => Promise<void>;
  setDegradationMode: (mode: SystemMode, reason: string) => Promise<boolean>;
  fetchDeadLetters: () => Promise<void>;
  replayDeadLetter: (jobId: string) => Promise<boolean>;
  fetchBackups: () => Promise<void>;
  createBackup: (collections?: string[]) => Promise<boolean>;
  restoreBackup: (backupId: string, dryRun: boolean) => Promise<boolean>;
  runChaosDrills: () => Promise<{ all_passed: boolean; total_drills: number; drills: any[] } | null>;
}

export const useReliabilityStore = create<ReliabilityState>((set, get) => ({
  systemMode: 'FULL',
  modeReason: 'System operating normally',
  uptimeSeconds: 0,
  goldenSignals: null,
  subsystems: null,
  slos: [],
  deadLetters: [],
  backups: [],
  isLoading: false,
  error: null,

  fetchMetrics: async () => {
    try {
      const res = await fetch('/api/v1/reliability/metrics');
      if (res.ok) {
        const data = await res.json();
        set({
          uptimeSeconds: data.uptime_seconds,
          goldenSignals: data.golden_signals,
          subsystems: data.subsystems,
        });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  fetchSLOs: async () => {
    try {
      const res = await fetch('/api/v1/reliability/slo');
      if (res.ok) {
        const data = await res.json();
        set({ slos: data.slos || [] });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  fetchDegradation: async () => {
    try {
      const res = await fetch('/api/v1/reliability/degradation');
      if (res.ok) {
        const data = await res.json();
        set({ systemMode: data.mode, modeReason: data.reason });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  setDegradationMode: async (mode: SystemMode, reason: string) => {
    try {
      const res = await fetch('/api/v1/reliability/degradation/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, reason }),
      });
      if (res.ok) {
        await get().fetchDegradation();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchDeadLetters: async () => {
    try {
      const res = await fetch('/api/v1/reliability/queues/dead-letter');
      if (res.ok) {
        const data = await res.json();
        set({ deadLetters: data.dead_letters || [] });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  replayDeadLetter: async (jobId: string) => {
    try {
      const res = await fetch('/api/v1/reliability/queues/dead-letter/replay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId }),
      });
      if (res.ok) {
        await get().fetchDeadLetters();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchBackups: async () => {
    try {
      const res = await fetch('/api/v1/reliability/backups');
      if (res.ok) {
        const data = await res.json();
        set({ backups: data.backups || [] });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  createBackup: async (collections?: string[]) => {
    try {
      const res = await fetch('/api/v1/reliability/backups/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collections }),
      });
      if (res.ok) {
        await get().fetchBackups();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  restoreBackup: async (backupId: string, dryRun: boolean) => {
    try {
      const res = await fetch('/api/v1/reliability/backups/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backup_id: backupId, dry_run: dryRun }),
      });
      return res.ok;
    } catch {
      return false;
    }
  },

  runChaosDrills: async () => {
    try {
      const res = await fetch('/api/v1/reliability/chaos/run', { method: 'POST' });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  },
}));
