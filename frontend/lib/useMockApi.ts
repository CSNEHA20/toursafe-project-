// Drop-in replacement for all API calls
// Set EXPO_PUBLIC_USE_MOCK=true in .env for full mock mode
// (was NEXT_PUBLIC_USE_MOCK on web)

import {
  MOCK_LOGGED_IN_TOURIST,
  MOCK_TOURISTS,
  MOCK_ALERTS,
  MOCK_ZONES,
  MOCK_KPI,
  MOCK_HEATMAP_POINTS,
  MOCK_RESPONSE_TIMES,
  MOCK_TOURIST_FLOW,
  MOCK_INCIDENT_TRENDS,
  MOCK_ZONE_SUMMARY,
  MOCK_INCIDENTS,
  MOCK_EFIRS,
  MOCK_CONSENTS,
  MOCK_LOCATION_HISTORY,
  MOCK_EMERGENCY_CONTACTS,
  MOCK_NEARBY_PLACES,
  MOCK_ACTIVITY_FEED,
  MOCK_AUTHORITY,
  MOCK_VERIFICATION_LOG,
  MOCK_CONSENT_LOG,
  MOCK_ANALYTICS_SNAPSHOTS,
} from "./mockData";

const delay = (ms = 400) => new Promise<void>((r) => setTimeout(r, ms));

export const mockApi = {
  // ── TOURIST ──────────────────────────────────────────────────────────────────
  getTouristProfile: async () => {
    await delay();
    return MOCK_LOGGED_IN_TOURIST;
  },
  getTouristConsents: async () => {
    await delay();
    return MOCK_CONSENTS;
  },
  getLocationHistory: async () => {
    await delay();
    return MOCK_LOCATION_HISTORY;
  },
  getNearbyZones: async () => {
    await delay();
    return MOCK_NEARBY_PLACES;
  },
  getEmergencyContacts: async () => {
    await delay();
    return MOCK_EMERGENCY_CONTACTS;
  },
  getConsentLog: async () => {
    await delay();
    return MOCK_CONSENT_LOG;
  },
  getMyAlerts: async () => {
    await delay();
    return MOCK_ALERTS.slice(0, 4);
  },
  getMyIncidents: async () => {
    await delay();
    return MOCK_INCIDENTS.filter((i) => i.tourist_id === "tourist-logged-in");
  },
  getDIDData: async () => {
    await delay();
    return {
      issued: true,
      did_uri: MOCK_LOGGED_IN_TOURIST.did_uri,
      display_id: MOCK_LOGGED_IN_TOURIST.did_mock_id,
      mock_tx_hash: MOCK_LOGGED_IN_TOURIST.did_mock_tx,
      mock_block_number: MOCK_LOGGED_IN_TOURIST.did_block_number,
      ipfs_mock_cid: MOCK_LOGGED_IN_TOURIST.did_ipfs_cid,
      issued_at: "2026-04-12T14:30:00Z",
    };
  },
  getQRData: async () => {
    await delay();
    return {
      qr_payload: JSON.stringify({
        did: MOCK_LOGGED_IN_TOURIST.did_uri,
        name: MOCK_LOGGED_IN_TOURIST.full_name,
        blood: MOCK_LOGGED_IN_TOURIST.blood_type,
        id: MOCK_LOGGED_IN_TOURIST.did_mock_id,
        ts: Math.floor(Date.now() / 1000),
      }),
      display_id: MOCK_LOGGED_IN_TOURIST.did_mock_id,
    };
  },
  triggerSOS: async (_data: unknown) => {
    await delay(1200);
    return { sos_id: "incident-mock-001", alert_id: "alert-mock-001", status: "dispatched" };
  },
  postConsent: async (_type: string, _granted: boolean) => {
    await delay(300);
    return { success: true };
  },
  postLocationPing: async (_data: unknown) => {
    await delay(200);
    return { status: "ok", recorded: true };
  },

  // ── AUTHORITY ─────────────────────────────────────────────────────────────────
  getKPIDashboard: async () => {
    await delay();
    return MOCK_KPI;
  },
  getAllTourists: async (_filters?: unknown) => {
    await delay();
    return MOCK_TOURISTS;
  },
  getTouristById: async (id: string) => {
    await delay();
    return {
      tourist: MOCK_TOURISTS.find((t) => t.id === id) ?? MOCK_TOURISTS[0],
      recent_alerts: MOCK_ALERTS.filter((a) => a.tourist_id === id).slice(0, 5),
      recent_locations: MOCK_LOCATION_HISTORY,
    };
  },
  getAlerts: async (_filters?: unknown) => {
    await delay();
    return MOCK_ALERTS;
  },
  getAlertById: async (id: string) => {
    await delay();
    return {
      alert: MOCK_ALERTS.find((a) => a.id === id) ?? MOCK_ALERTS[0],
      location_trail: MOCK_LOCATION_HISTORY,
    };
  },
  getUnreadAlertCount: async () => {
    await delay(100);
    return { count: MOCK_ALERTS.filter((a) => a.status === "new").length };
  },
  updateAlert: async (id: string, updates: unknown) => {
    await delay(300);
    return { id, ...(updates as object) };
  },
  getActiveSOS: async () => {
    await delay();
    return MOCK_INCIDENTS.filter((i) => i.priority === "critical" && i.status === "open");
  },
  acknowledgeAlert: async (_id: string) => {
    await delay(300);
    return { acknowledged: true };
  },
  resolveAlert: async (_id: string, _notes: string) => {
    await delay(300);
    return { resolved: true };
  },
  getHeatmap: async () => {
    await delay();
    return MOCK_HEATMAP_POINTS;
  },
  getResponseTimes: async () => {
    await delay();
    return MOCK_RESPONSE_TIMES;
  },
  getTouristFlow: async () => {
    await delay();
    return MOCK_TOURIST_FLOW;
  },
  getIncidentTrends: async () => {
    await delay();
    return MOCK_INCIDENT_TRENDS;
  },
  getZoneSummary: async () => {
    await delay();
    return MOCK_ZONE_SUMMARY;
  },
  getZones: async () => {
    await delay();
    return MOCK_ZONES;
  },
  createZone: async (data: unknown) => {
    await delay(800);
    return { id: `zone-new-${Date.now()}`, ...(data as object), is_active: true };
  },
  toggleZone: async (_id: string) => {
    await delay(300);
    return { is_active: true };
  },
  getIncidents: async () => {
    await delay();
    return MOCK_INCIDENTS;
  },
  createIncident: async (data: unknown) => {
    await delay(500);
    return { id: `incident-new-${Date.now()}`, ...(data as object), created_at: new Date().toISOString() };
  },
  getEFIRs: async () => {
    await delay();
    return MOCK_EFIRS;
  },
  getEFIRById: async (id: string) => {
    await delay();
    return MOCK_EFIRS.find((e) => e.id === id) ?? MOCK_EFIRS[0];
  },
  generateEFIR: async (data: unknown) => {
    await delay(1000);
    return {
      id: `efir-new-${Date.now()}`,
      case_number: `TSX-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-MOCK01`,
      status: "draft",
      ...(data as object),
    };
  },
  updateEFIR: async (id: string, updates: unknown) => {
    await delay(300);
    return { id, ...(updates as object) };
  },
  verifyDID: async (did_uri: string) => {
    await delay(800);
    return {
      verified: true,
      did_uri,
      tourist: {
        full_name: "Arun Kumar",
        blood_type: "O+",
        medical_conditions: [],
        allergies: [],
        emergency_contact_name: "Vijay Kumar",
        emergency_contact_phone: "+919988776656",
        nationality: "Indian",
      },
      tx_hash: "0x7f4a2b8c9d3e1f56789012345678abcdef012345abcdef",
      block_number: 44211982,
      issued_at: "2026-04-09T10:15:00Z",
    };
  },
  getVerificationLog: async () => {
    await delay();
    return MOCK_VERIFICATION_LOG;
  },
  getActivityFeed: async () => {
    await delay();
    return MOCK_ACTIVITY_FEED;
  },
  getAnalyticsSnapshots: async () => {
    await delay();
    return MOCK_ANALYTICS_SNAPSHOTS;
  },
  getAuthorityProfile: async () => {
    await delay();
    return MOCK_AUTHORITY;
  },
};

export { MOCK_ANALYTICS_SNAPSHOTS };
