import { create } from "zustand";
import type { Alert } from "@/types";

interface AlertState {
  alerts: Alert[];
  unreadCount: number;
  selectedAlert: Alert | null;
  isLoading: boolean;
  filter: {
    severity: string | null;
    type: string | null;
    status: string | null;
    zone_id: string | null;
  };
  setAlerts: (alerts: Alert[]) => void;
  addAlert: (alert: Alert) => void;
  updateAlert: (alert: Alert) => void;
  selectAlert: (alert: Alert | null) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  setFilter: (filter: Partial<AlertState["filter"]>) => void;
  setLoading: (loading: boolean) => void;
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  selectedAlert: null,
  isLoading: false,
  filter: { severity: null, type: null, status: null, zone_id: null },

  setAlerts: (alerts) => {
    const unread = alerts.filter((a) => a.status === "active").length;
    set({ alerts, unreadCount: unread });
  },

  addAlert: (alert) => {
    const updated = [alert, ...get().alerts];
    const unread = updated.filter((a) => a.status === "active").length;
    set({ alerts: updated, unreadCount: unread });
  },

  updateAlert: (alert) => {
    const updated = get().alerts.map((a) => (a.id === alert.id ? alert : a));
    const unread = updated.filter((a) => a.status === "active").length;
    set({ alerts: updated, unreadCount: unread });
  },

  selectAlert: (selectedAlert) => set({ selectedAlert }),

  markRead: (id) => {
    const updated = get().alerts.map((a) =>
      a.id === id ? { ...a, status: "acknowledged" as const } : a
    );
    set({ alerts: updated, unreadCount: updated.filter((a) => a.status === "active").length });
  },

  markAllRead: () => {
    const updated = get().alerts.map((a) =>
      a.status === "active" ? { ...a, status: "acknowledged" as const } : a
    );
    set({ alerts: updated, unreadCount: 0 });
  },

  setFilter: (filter) => set({ filter: { ...get().filter, ...filter } }),
  setLoading: (isLoading) => set({ isLoading }),
}));
