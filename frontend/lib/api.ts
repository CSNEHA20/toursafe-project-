import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { router } from "expo-router";
import Toast from "react-native-toast-message";
import { useAuthStore } from "@/store/authStore";
import type { Zone, ZoneMapItem, ZoneAudit } from "@/types";

const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// Auth token management
let isRefreshing = false;
let failedQueue: ((error: any) => void)[] = [];

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach((resolve) => resolve(token));
  failedQueue = [];
}

// Attach access token
let isMounted = true;

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!isMounted) return config;

    const store = useAuthStore.getState();
    if (store.accessToken) {
      config.headers.Authorization = `Bearer ${store.accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle token refresh on 401
let isHandling401 = false;

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const originalRequest = err.config as RetryConfig | undefined;

    if (err.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      if (isHandling401) {
        return new Promise((resolve) => {
          processQueue(null, null);
          resolve(originalRequest);
        });
      }

      isHandling401 = true;

      try {
        const store = useAuthStore.getState();
        if (!store.refreshToken) {
          router.replace("/auth/login");
          return Promise.reject(err);
        }

        const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: store.refreshToken }),
        });

        if (response.ok) {
          const data = await response.json();
          const { access_token: newAccessToken, refresh_token: newRefreshToken } = data;

          // Update auth store
          useAuthStore.setState({
            accessToken: newAccessToken,
            refreshToken: newRefreshToken,
          });

          // Retry the original request
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          }
          return api(originalRequest);
        } else {
          // Refresh failed - logout
          useAuthStore.getState().signOut();
          router.replace("/auth/login");
          return Promise.reject(err);
        }
      } catch (refreshError) {
        useAuthStore.getState().signOut();
        router.replace("/auth/login");
        return Promise.reject(err);
      } finally {
        isHandling401 = false;
      }
    }

    return Promise.reject(err);
  }
);

// ─── Typed API helpers ────────────────────────────────────────────────────────

export const touristApi = {
  getAll: (params?: Record<string, unknown>) => api.get("/tourists", { params }),
  getById: (id: string) => api.get(`/tourists/${id}`),
  getMe: () => api.get("/tourists/me"),
  create: (data: unknown) => api.post("/tourists", data),
  update: (id: string, data: unknown) => api.patch(`/tourists/${id}`, data),
  getLocation: (id: string) => api.get(`/tourists/${id}/location`),
  getTrail: (id: string, hours = 24) =>
    api.get(`/tourists/${id}/trail`, { params: { hours } }),
  bulkImport: (data: unknown[]) => api.post("/tourists/bulk-import", { tourists: data }),
  getMyProfile: () => api.get("/tourists/me"),
  updateMyProfile: (data: unknown) => api.patch("/tourists/me", data),
  getMyProfileStatus: () => api.get("/tourists/me/status"),
  submitKYC: (data: { document_type: string; document_reference: string }) =>
    api.post("/tourists/me/kyc", data),
  getMyKYCStatus: () => api.get("/tourists/me/kyc"),
  getMyMedical: () => api.get("/tourists/me/medical"),
  updateMyMedical: (data: unknown) => api.put("/tourists/me/medical", data),
  deleteMyMedical: () => api.delete("/tourists/me/medical"),
  createEmergencyContact: (data: {
    name: string;
    relationship: string;
    phone: string;
    alternate_phone?: string;
    email?: string;
    priority?: number;
  }) => api.post("/tourists/me/emergency-contacts", data),
  getMyEmergencyContacts: () => api.get("/tourists/me/emergency-contacts"),
  updateEmergencyContact: (contactId: string, data: {
    name?: string;
    relationship?: string;
    phone?: string;
    alternate_phone?: string;
    email?: string;
    priority?: number;
  }) => api.patch(`/tourists/me/emergency-contacts/${contactId}`, data),
  deleteEmergencyContact: (contactId: string) =>
    api.delete(`/tourists/me/emergency-contacts/${contactId}`),
  createItinerary: (data: {
    title: string;
    destination?: string;
    start_date?: string;
    end_date?: string;
    notes?: string;
    stops?: any[];
  }) => api.post("/tourists/me/itinerary", data),
  getMyItinerary: () => api.get("/tourists/me/itinerary"),
  updateItinerary: (itineraryId: string, data: {
    title?: string;
    destination?: string;
    start_date?: string;
    end_date?: string;
    notes?: string;
    status?: string;
  }) => api.patch(`/tourists/me/itinerary/${itineraryId}`, data),
  deleteItinerary: (itineraryId: string) =>
    api.delete(`/tourists/me/itinerary/${itineraryId}`),
};

export const locationApi = {
  updateLocation: (sample: any) => api.post("/location/update", sample),
  startSession: (data?: { device_id?: string; source?: string }) =>
    api.post("/location/session/start", data || {}),
  stopSession: (sessionId: string) =>
    api.post("/location/session/stop", { session_id: sessionId }),
  getMyLocation: () => api.get("/tourists/me/location"),
  getMyHistory: (params?: { start_time?: string; end_time?: string; limit?: number; skip?: number }) =>
    api.get("/tourists/me/location-history", { params }),
  getAuthorityTouristLocation: (touristId: string) =>
    api.get(`/authority/tourists/${touristId}/location`),
  getAuthorityTouristHistory: (touristId: string, params?: { start_time?: string; end_time?: string; limit?: number; skip?: number }) =>
    api.get(`/authority/tourists/${touristId}/location-history`, { params }),
  getAuthorityLiveLocations: () => api.get("/authority/live-locations"),
};

export const authorityApi = {
  getMe: () => api.get("/authority/me"),
  create: (data: unknown) => api.post("/authority", data),
  updateMe: (data: unknown) => api.patch("/authority/me", data),
  list: () => api.get("/authority"),
  getTouristDirectory: (params?: Record<string, unknown>) =>
    api.get("/authority/tourists", { params }),
  getTouristDetail: (touristId: string) => api.get(`/authority/tourists/${touristId}`),
};

export const alertApi = {
  getAll: (params?: Record<string, unknown>) => api.get("/alerts", { params }),
  getById: (id: string) => api.get(`/alerts/${id}`),
  acknowledge: (id: string) => api.post(`/alerts/${id}/acknowledge`),
  resolve: (id: string, notes?: string) =>
    api.post(`/alerts/${id}/resolve`, { notes }),
  escalate: (id: string) => api.post(`/alerts/${id}/escalate`),
};

export const sosApi = {
  trigger: (data: { tourist_id?: string; latitude: number; longitude: number; description?: string }) =>
    api.post("/sos/trigger", data),
  getStatus: (incident_id: string) => api.get(`/sos/${incident_id}/status`),
  update: (incident_id: string, status: string) =>
    api.patch(`/sos/${incident_id}`, { status }),
};

export const zoneApi = {
  // Tourist / Map endpoints
  getAll: (params?: { zone_type?: string; risk_level?: string; skip?: number; limit?: number }) =>
    api.get<{ zones: ZoneMapItem[]; total: number }>("/zones", { params }),
  getById: (id: string) => api.get<ZoneMapItem>(`/zones/${id}`),

  // Authority / Admin management endpoints
  getAuthorityZones: (params?: {
    q?: string;
    status?: string;
    zone_type?: string;
    risk_level?: string;
    skip?: number;
    limit?: number;
    sort_by?: string;
    sort_order?: string;
  }) => api.get<{ items: Zone[]; total: number; skip: number; limit: number }>("/authority/zones", { params }),
  getAuthorityZoneById: (id: string) => api.get<Zone>(`/authority/zones/${id}`),
  create: (data: Partial<Zone>) => api.post<Zone>("/authority/zones", data),
  update: (id: string, data: Partial<Zone>) => api.patch<Zone>(`/authority/zones/${id}`, data),
  delete: (id: string, hard_delete = false) =>
    api.delete<{ success: boolean; zone_id: string; message: string }>(`/authority/zones/${id}`, {
      params: { hard_delete },
    }),
  getAudits: (id: string) => api.get<ZoneAudit[]>(`/authority/zones/${id}/audits`),
};

export const analyticsApi = {
  getKPIs: () => api.get("/analytics/kpis"),
  getResponseTimes: (days = 30) =>
    api.get("/analytics/response-times", { params: { days } }),
  getIncidentTrends: (days = 30) =>
    api.get("/analytics/incident-trends", { params: { days } }),
  getZoneStats: () => api.get("/analytics/zone-stats"),
  getHeatmapData: () => api.get("/analytics/heatmap"),
  getAlertDistribution: () => api.get("/analytics/alert-distribution"),
};

export const efirApi = {
  getAll: (params?: Record<string, unknown>) => api.get("/efir", { params }),
  getMine: () => api.get("/efir/mine"),
  getById: (id: string) => api.get(`/efir/${id}`),
  create: (data: unknown) => api.post("/efir", data),
  submit: (id: string) => api.post(`/efir/${id}/submit`),
  archive: (id: string) => api.post(`/efir/${id}/archive`),
  getPDF: (id: string) => api.get(`/efir/${id}/pdf`, { responseType: "blob" }),
  downloadPDF: (id: string) => api.get(`/efir/${id}/pdf`, { responseType: "blob" }),
  download: (id: string) => api.get(`/efir/${id}/pdf`, { responseType: "blob" }),
};

export const blockchainApi = {
  getDID: (tourist_id: string) => api.get(`/blockchain/did/${tourist_id}`),
  verifyDID: (did_address: string) =>
    api.post("/blockchain/verify", { did_address }),
  verify: (did_address: string) =>
    api.post("/blockchain/verify", { did_address }),
};

export const itineraryApi = {
  getAll: () => api.get("/itinerary"),
  getById: (id: string) => api.get(`/itinerary/${id}`),
  create: (data: unknown) => api.post("/itinerary", data),
  update: (id: string, data: unknown) => api.patch(`/itinerary/${id}`, data),
  delete: (id: string) => api.delete(`/itinerary/${id}`),
  addStop: (id: string, data: unknown) => api.post(`/itinerary/${id}/stops`, data),
  deleteStop: (itineraryId: string, stopId: string) =>
    api.delete(`/itinerary/${itineraryId}/stops/${stopId}`),
};


export const safetyCheckApi = {
  getMine: () => api.get("/safety-check"),
  getPending: () => api.get("/safety-check/pending"),
  respond: (checkId: string, response: "safe" | "unsafe") =>
    api.post(`/safety-check/${checkId}/respond`, { response }),
  trigger: (touristId: string, reason?: string) =>
    api.post(`/safety-check/trigger/${touristId}`, null, { params: { reason } }),
  escalate: (checkId: string) => api.post(`/safety-check/${checkId}/escalate`),
};

// ─── Mock data override ──────────────────────────────────────────────────────
// When EXPO_PUBLIC_USE_MOCK=true all API objects return static mock data so the
// app works without a running backend or Supabase session.
// Set to false (or remove) to use the real FastAPI backend.

if (process.env.EXPO_PUBLIC_USE_MOCK === "true") {
  const {
    MOCK_KPI,
    MOCK_ALERTS,
    MOCK_ZONES,
    MOCK_ZONE_SUMMARY,
    MOCK_TOURISTS,
    MOCK_LOGGED_IN_TOURIST,
    MOCK_INCIDENTS,
    MOCK_EFIRS,
    MOCK_RESPONSE_TIMES,
    MOCK_INCIDENT_TRENDS,
    MOCK_HEATMAP_POINTS,
    MOCK_AUTHORITY,
  } = require("./mockData");

  // Helper: wrap data as an Axios-like response so components can use r.data
  const ok = (data: unknown) => Promise.resolve({ data, status: 200, statusText: "OK", headers: {}, config: {} as never });
  const delay = (ms = 350) => new Promise<void>((r) => setTimeout(r, ms));
  const okd = async (data: unknown, ms = 350) => { await delay(ms); return ok(data); };

  // ── analyticsApi ────────────────────────────────────────────────────────────
  analyticsApi.getKPIs = () =>
    okd({
      active_tourists: MOCK_KPI.total_active,
      active_tourists_delta: 5,
      active_alerts: MOCK_KPI.alerts_today,
      active_alerts_delta: 2,
      sos_today: MOCK_KPI.status_breakdown.sos,
      sos_today_delta: 0,
      avg_response_time_minutes: MOCK_KPI.avg_response_time_minutes,
      avg_response_time_delta: -1.2,
      zones_at_risk: 2,
      resolved_today: 3,
    });

  analyticsApi.getResponseTimes = () =>
    okd(MOCK_RESPONSE_TIMES.map((r: { date: string; avg_minutes: number }) => ({
      date: r.date,
      avg_minutes: r.avg_minutes,
      p95_minutes: r.avg_minutes * 1.4,
    })));

  analyticsApi.getIncidentTrends = () =>
    okd(MOCK_INCIDENT_TRENDS.map((t: { week: string; counts: Record<string, number> }) => ({
      date: t.week,
      sos: t.counts.accident ?? 0,
      inactivity: t.counts.medical ?? 0,
      zone_exit: t.counts.other ?? 0,
      other: t.counts.missing ?? 0,
    })));

  analyticsApi.getZoneStats = () =>
    okd(MOCK_ZONE_SUMMARY.map((z: { id: string; name: string; tourist_count: number; active_alerts: number }) => ({
      zone_id: z.id,
      zone_name: z.name,
      tourist_count: z.tourist_count,
      alert_count: z.active_alerts,
      risk_score: z.active_alerts > 0 ? 0.7 : 0.2,
    })));

  analyticsApi.getHeatmapData = () => okd(MOCK_HEATMAP_POINTS);
  analyticsApi.getAlertDistribution = () =>
    okd(MOCK_KPI.alert_type_breakdown);

  // ── alertApi ────────────────────────────────────────────────────────────────
  alertApi.getAll = (_params?: Record<string, unknown>) =>
    okd({
      items: MOCK_ALERTS.map((a: {
        id: string; alert_type: string; severity: string; status: string;
        description: string; zone_id: string; zone_name: string;
        latitude: number; longitude: number; created_at: string;
        tourist_id: string; anomaly_score: number | null;
      }) => ({
        ...a,
        type: a.alert_type,
        title: a.description.slice(0, 60),
        zone: { id: a.zone_id, name: a.zone_name },
      })),
      total: MOCK_ALERTS.length,
    });

  alertApi.getById = (id: string) => {
    const a = MOCK_ALERTS.find((x: { id: string }) => x.id === id) ?? MOCK_ALERTS[0];
    return okd({ ...a, type: a.alert_type, title: a.description.slice(0, 60), zone: { id: a.zone_id, name: a.zone_name } });
  };

  alertApi.acknowledge = (_id: string) => okd({ success: true }, 300);
  alertApi.resolve = (_id: string) => okd({ success: true }, 300);
  alertApi.escalate = (_id: string) => okd({ success: true }, 300);

  // ── zoneApi ─────────────────────────────────────────────────────────────────
  const mockZonesToZoneMapItems = (zones: any[]): ZoneMapItem[] =>
    zones.map((z) => ({
      zone_id: z.id,
      name: z.name,
      description: z.alert_message_en || "",
      type: z.zone_type as any,
      risk_level: z.zone_type === "danger" ? "critical" : z.zone_type === "warning" ? "medium" : "low",
      status: z.is_active ? "active" : "inactive",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [z.center_lng - 0.005, z.center_lat - 0.005],
            [z.center_lng + 0.005, z.center_lat - 0.005],
            [z.center_lng + 0.005, z.center_lat + 0.005],
            [z.center_lng - 0.005, z.center_lat + 0.005],
            [z.center_lng - 0.005, z.center_lat - 0.005],
          ],
        ],
      },
      center: {
        type: "Point",
        coordinates: [z.center_lng, z.center_lat],
      },
      properties: { dataset: "DEVELOPMENT GEOMETRY" },
    }));

  zoneApi.getAll = (params?: any) => {
    const items = mockZonesToZoneMapItems(MOCK_ZONES);
    return okd({ zones: items, total: items.length }) as any;
  };
  zoneApi.getById = (id: string) => {
    const z = MOCK_ZONES.find((x: { id: string }) => x.id === id) ?? MOCK_ZONES[0];
    return okd(mockZonesToZoneMapItems([z])[0]) as any;
  };
  zoneApi.getAuthorityZones = (params?: any) => {
    const items = mockZonesToZoneMapItems(MOCK_ZONES).map((z, idx) => ({
      id: z.zone_id,
      zone_id: z.zone_id,
      name: z.name,
      description: z.description,
      zone_type: z.type,
      risk_level: z.risk_level,
      status: z.status,
      boundary: z.geometry,
      center: z.center,
      properties: z.properties,
      is_active: z.status === "active",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }));
    return okd({ items, total: items.length, skip: 0, limit: items.length }) as any;
  };
  zoneApi.getAuthorityZoneById = (id: string) => {
    const z = MOCK_ZONES.find((x: { id: string }) => x.id === id) ?? MOCK_ZONES[0];
    const mapItem = mockZonesToZoneMapItems([z])[0];
    return okd({
      id: mapItem.zone_id,
      zone_id: mapItem.zone_id,
      name: mapItem.name,
      description: mapItem.description,
      zone_type: mapItem.type,
      risk_level: mapItem.risk_level,
      status: mapItem.status,
      boundary: mapItem.geometry,
      center: mapItem.center,
      properties: mapItem.properties,
      is_active: mapItem.status === "active",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }) as any;
  };
  zoneApi.create = (data: any) => okd({ id: `zone-${Date.now()}`, zone_id: `zone-${Date.now()}`, ...data }, 500) as any;
  zoneApi.update = (id: string, data: any) => okd({ id, zone_id: id, ...data }, 300) as any;
  zoneApi.delete = (id: string) => okd({ success: true, zone_id: id, message: "Zone deleted" }, 300) as any;
  zoneApi.getAudits = (_id: string) => okd([]) as any;

  // ── touristApi ──────────────────────────────────────────────────────────────
  const mockTouristToType = (t: {
    id: string; user_id: string; full_name: string; nationality: string;
    phone_e164: string; date_of_birth: string; status: string;
    current_lat: number; current_lng: number; current_zone_id: string;
    did_issued: boolean; did_mock_id: string | null; anomaly_score: number; battery_pct: number;
    blood_type?: string; medical_conditions?: string[]; allergies?: string[];
    emergency_contact_name?: string; emergency_contact_phone?: string; emergency_contact_relation?: string;
    age?: number; last_seen?: string;
  }) => {
    // Resolve zone name from MOCK_ZONES
    const zoneEntry = MOCK_ZONES.find((z: { id: string; name: string }) => z.id === t.current_zone_id);
    return {
      id: t.id,
      user_id: t.user_id,
      full_name: t.full_name,
      name: t.full_name,
      nationality: t.nationality,
      phone: t.phone_e164,
      passport_number: t.did_mock_id ?? "",
      email: "",
      date_of_birth: t.date_of_birth,
      gender: "other" as const,
      did_status: t.did_issued ? "active" : ("pending" as "active" | "pending" | "revoked"),
      status: (t.status === "sos" ? "sos" : t.status === "warning" ? "alert" : t.status === "inactive" ? "inactive" : "safe") as "safe" | "alert" | "sos" | "warning" | "inactive",
      current_location: { latitude: t.current_lat, longitude: t.current_lng },
      current_zone_id: t.current_zone_id,
      current_zone: zoneEntry?.name ?? "Unknown Zone",
      last_seen_at: t.last_seen ? new Date(Date.now() - 120000).toISOString() : new Date().toISOString(),
      last_seen: t.last_seen,
      is_active: true,
      created_at: new Date().toISOString(),
      // Extended fields
      battery_pct: t.battery_pct,
      anomaly_score: t.anomaly_score,
      blood_type: t.blood_type,
      medical_conditions: t.medical_conditions ?? [],
      allergies: t.allergies ?? [],
      emergency_contact_name: t.emergency_contact_name,
      emergency_contact_phone: t.emergency_contact_phone,
      emergency_contact_relation: t.emergency_contact_relation,
      age: t.age,
    };
  };

  touristApi.getAll = () => okd({ items: MOCK_TOURISTS.map(mockTouristToType), total: MOCK_TOURISTS.length });
  touristApi.getById = (id: string) => {
    const t = MOCK_TOURISTS.find((x: { id: string }) => x.id === id) ?? MOCK_TOURISTS[0];
    return okd(mockTouristToType(t));
  };
  touristApi.getMe = () => okd(mockTouristToType(MOCK_LOGGED_IN_TOURIST as never));
  touristApi.create = (data: unknown) => okd({ id: `tourist-new-${Date.now()}`, ...(data as object), did_status: "pending", is_active: true, created_at: new Date().toISOString() }, 700);
  touristApi.bulkImport = (data: unknown[]) => okd({ imported: data.length, failed: 0 }, 1200);
  touristApi.getTrail = (_id: string) => {
    const { MOCK_LOCATION_HISTORY } = require("./mockData");
    return okd(MOCK_LOCATION_HISTORY);
  };

  // ── sosApi ──────────────────────────────────────────────────────────────────
  sosApi.trigger = async () => { await delay(1200); return ok({ sos_id: "sos-mock-001", status: "dispatched" }); };

  // ── efirApi ─────────────────────────────────────────────────────────────────
  efirApi.getAll = () =>
    okd({
      items: MOCK_EFIRS.map((e: {
        id: string; incident_id: string; tourist_id: string;
        case_number: string; fir_type: string; status: string;
        incident_date: string; incident_location_text: string;
        incident_description: string; created_at: string; updated_at: string;
      }) => ({
        id: e.id,
        incident_id: e.incident_id,
        tourist_id: e.tourist_id,
        fir_number: e.case_number,
        efir_number: e.case_number,
        status: e.status === "approved" ? "accepted" : e.status === "closed" ? "archived" : e.status,
        incident_type: e.fir_type,
        incident_date: e.incident_date,
        incident_location: e.incident_location_text,
        description: e.incident_description,
        evidence_urls: [],
        created_at: e.created_at,
        updated_at: e.updated_at,
      })),
      total: MOCK_EFIRS.length,
    });
  efirApi.getById = (id: string) => {
    const e = MOCK_EFIRS.find((x: { id: string }) => x.id === id) ?? MOCK_EFIRS[0];
    return okd({ id: e.id, fir_number: e.case_number, efir_number: e.case_number, status: e.status, description: e.incident_description, incident_type: e.fir_type, incident_date: e.incident_date, incident_location: e.incident_location_text, evidence_urls: [], created_at: e.created_at, updated_at: e.updated_at });
  };
  efirApi.create = (data: unknown) => okd({ id: `efir-new-${Date.now()}`, fir_number: `TSX-MOCK-${Date.now()}`, status: "draft", ...(data as object) }, 800);
  efirApi.submit = (_id: string) => okd({ success: true }, 400);
  efirApi.archive = (_id: string) => okd({ success: true }, 300);

  // ── authorityApi ─────────────────────────────────────────────────────────────
  authorityApi.getMe = () => okd(MOCK_AUTHORITY);
  authorityApi.list = () => okd({ items: require("./mockData").MOCK_AUTHORITIES, total: 4 });
  authorityApi.create = (data: unknown) => okd({ id: `authority-new-${Date.now()}`, ...(data as object), status: "pending" }, 700);

  // ── blockchainApi ────────────────────────────────────────────────────────────
  blockchainApi.getDID = (_id: string) =>
    okd({ did_address: MOCK_LOGGED_IN_TOURIST.did_uri, verification_status: "verified", network: "polygon" });
  blockchainApi.verifyDID = (_addr: string) => okd({ verified: true, verification_status: "verified" }, 800);
  blockchainApi.verify = (_addr: string) => okd({ verified: true, verification_status: "verified" }, 800);

  // ── itineraryApi ─────────────────────────────────────────────────────────────
  itineraryApi.getAll = () => okd([]);

  // ── safetyCheckApi ───────────────────────────────────────────────────────────
  safetyCheckApi.getMine = () => okd({ items: [], total: 0 });
  safetyCheckApi.getPending = () => okd({ items: [], total: 0 });
}