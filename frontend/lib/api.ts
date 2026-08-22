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
  trigger: (data: { client_request_id?: string; latitude?: number; longitude?: number; accuracy?: number; reason?: string; description?: string }) =>
    api.post("/tourists/me/sos", {
      client_request_id: data.client_request_id || `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      latitude: data.latitude,
      longitude: data.longitude,
      accuracy: data.accuracy,
      reason: data.reason || data.description || "Manual SOS from app",
    }),
  cancel: (sos_id: string, reason: string) =>
    api.post(`/tourists/me/sos/${sos_id}/cancel`, { reason }),
  getActive: () => api.get("/tourists/me/sos/active"),
  getStatus: (incident_id: string) => api.get(`/sos/${incident_id}/status`),
  update: (incident_id: string, status: string) =>
    api.patch(`/sos/${incident_id}`, { status }),
};

export const incidentApi = {
  getAll: (params?: { status?: string; severity?: string; tourist_id?: string; page?: number; limit?: number }) =>
    api.get("/authority/incidents", { params }),
  getById: (id: string) => api.get(`/authority/incidents/${id}`),
  getTimeline: (id: string) => api.get(`/authority/incidents/${id}/timeline`),
  getMetrics: () => api.get("/authority/incidents/metrics"),
  acknowledge: (id: string, data?: { notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/acknowledge`, data || {}),
  assess: (id: string, data: { severity?: string; notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/assess`, data),
  assign: (id: string, data: { responder_id: string; unit_id?: string; notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/assign`, data),
  startResponse: (id: string, data?: { notes?: string; estimated_arrival_minutes?: number; version?: number }) =>
    api.post(`/authority/incidents/${id}/response-start`, data || {}),
  escalate: (id: string, data: { reason: string; target_severity?: string; notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/escalate`, data),
  addNote: (id: string, content: string) =>
    api.post(`/authority/incidents/${id}/notes`, { content }),
  resolve: (id: string, data: { resolution_reason: string; resolution_category?: string; notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/resolve`, data),
  cancel: (id: string, data: { cancellation_reason: string; is_false_alarm?: boolean; notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/cancel`, data),
  close: (id: string, data?: { notes?: string; version?: number }) =>
    api.post(`/authority/incidents/${id}/close`, data || {}),
};

export const responderApi = {
  getAll: (params?: { status?: string; type?: string; active_only?: boolean; limit?: number; skip?: number }) =>
    api.get("/authority/responders", { params }),
  getById: (id: string) => api.get(`/authority/responders/${id}`),
  create: (data: any) => api.post("/authority/responders", data),
  update: (id: string, data: any) => api.patch(`/authority/responders/${id}`, data),
  // Prompt 13 endpoints
  getMe: () => api.get<import("@/types").ResponderSelfProfile>("/responders/me"),
  updateStatus: (status: string, reason?: string) =>
    api.post("/responders/me/status", { status, reason }),
  updateLocation: (data: { latitude: number; longitude: number; altitude?: number; accuracy?: number; heading?: number; speed?: number; tracking_session_id?: string; timestamp?: string }) =>
    api.post("/responders/me/location", data),
  startTracking: (device_battery_pct?: number) =>
    api.post("/responders/me/tracking/start", null, { params: { device_battery_pct } }),
  stopTracking: (device_battery_pct?: number) =>
    api.post("/responders/me/tracking/stop", null, { params: { device_battery_pct } }),
  getRecommendations: (params: { incident_id: string; required_type?: string; max_distance_km?: number; limit?: number }) =>
    api.get<import("@/types").ResponderRecommendationItem[]>("/responders/recommendations", { params }),
  getLiveMap: (active_only = true) =>
    api.get("/responders/map/live", { params: { active_only } }),
  listUnits: (params?: { unit_type?: string; status?: string; limit?: number; skip?: number }) =>
    api.get<import("@/types").ResponderUnitRecord[]>("/responders/units", { params }),
  createUnit: (data: any) => api.post<import("@/types").ResponderUnitRecord>("/responders/units", data),
  updateUnit: (unit_id: string, data: any) => api.patch<import("@/types").ResponderUnitRecord>(`/responders/units/${unit_id}`, data),
};

export const incidentAssignmentApi = {
  getAssignments: (incident_id: string) =>
    api.get<import("@/types").AssignmentRecord[]>(`/authority/incidents/${incident_id}/assignments`),
  createAssignment: (incident_id: string, data: { responder_id: string; unit_id?: string; notes?: string }) =>
    api.post<import("@/types").AssignmentRecord>(`/authority/incidents/${incident_id}/assignments`, data),
  acceptAssignment: (incident_id: string, assignment_id: string, notes?: string) =>
    api.post<import("@/types").AssignmentRecord>(`/authority/incidents/${incident_id}/assignments/${assignment_id}/accept`, { notes }),
  rejectAssignment: (incident_id: string, assignment_id: string, data: { reason: string; details?: string }) =>
    api.post<import("@/types").AssignmentRecord>(`/authority/incidents/${incident_id}/assignments/${assignment_id}/reject`, data),
  startResponse: (incident_id: string, assignment_id: string, notes?: string) =>
    api.post<import("@/types").AssignmentRecord>(`/authority/incidents/${incident_id}/assignments/${assignment_id}/start`, { notes }),
  markArrived: (incident_id: string, assignment_id: string, data: { latitude?: number; longitude?: number; accuracy?: number; force_override?: boolean; notes?: string }) =>
    api.post<import("@/types").AssignmentRecord>(`/authority/incidents/${incident_id}/assignments/${assignment_id}/arrived`, data),
  completeResponse: (incident_id: string, assignment_id: string, data: { completion_reason: string; resolution_notes?: string }) =>
    api.post<import("@/types").AssignmentRecord>(`/authority/incidents/${incident_id}/assignments/${assignment_id}/complete`, data),
  getMessages: (incident_id: string, limit = 50, skip = 0) =>
    api.get<import("@/types").OperationalMessageRecord[]>(`/authority/incidents/${incident_id}/messages`, { params: { limit, skip } }),
  sendMessage: (incident_id: string, data: { content: string; assignment_id?: string }) =>
    api.post<import("@/types").OperationalMessageRecord>(`/authority/incidents/${incident_id}/messages`, data),
  markMessagesRead: (incident_id: string) =>
    api.post(`/authority/incidents/${incident_id}/messages/read`),
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

export const geofenceApi = {
  // Tourist endpoints
  getMyCurrentZones: () =>
    api.get<import("@/types").TouristGeofenceSnapshotResponse>("/tourists/me/zones/current"),
  getMyZoneHistory: (params?: { start_time?: string; end_time?: string; zone_id?: string; limit?: number; skip?: number }) =>
    api.get<{ tourist_id: string; items: import("@/types").ZoneTransitionHistoryRecord[]; total: number; limit: number; skip: number }>("/tourists/me/zones/history", { params }),

  // Authority endpoints
  getTouristCurrentZones: (touristId: string) =>
    api.get<import("@/types").TouristGeofenceSnapshotResponse>(`/authority/tourists/${touristId}/zones/current`),
  getTouristZoneHistory: (touristId: string, params?: { start_time?: string; end_time?: string; zone_id?: string; limit?: number; skip?: number }) =>
    api.get<{ tourist_id: string; items: import("@/types").ZoneTransitionHistoryRecord[]; total: number; limit: number; skip: number }>(`/authority/tourists/${touristId}/zones/history`, { params }),
  getLiveOccupancy: () =>
    api.get<{ total_active_zones: number; zones: Array<{ zone_id: string; name: string; zone_type: string; risk_level: string; active_tourists_count: number; center?: any; boundary?: any }> }>("/authority/zones/live-occupancy"),

  // Dev diagnostics
  getDiagnostics: (touristId: string) =>
    api.get<import("@/types").GeofenceDiagnosticsData>(`/dev/geofence/diagnostics/${touristId}`),
};

export const analyticsApi = {
  getOverview: (params?: { start_time?: string; end_time?: string; granularity?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/overview", { params }),
  getIncidents: (params?: { start_time?: string; end_time?: string; granularity?: string; severity?: string; incident_source?: string; zone_id?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/incidents", { params }),
  getZones: (params?: { start_time?: string; end_time?: string; risk_level?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/zones", { params }),
  getZoneDetail: (zoneId: string, params?: { start_time?: string; end_time?: string; granularity?: string; bypass_cache?: boolean }) =>
    api.get(`/analytics/zones/${zoneId}`, { params }),
  getHeatmaps: (params?: { layer?: string; start_time?: string; end_time?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/heatmaps", { params }),
  getAnomalies: (params?: { start_time?: string; end_time?: string; granularity?: string; model_version?: string; zone_id?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/anomalies", { params }),
  getSafety: (params?: { start_time?: string; end_time?: string; granularity?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/safety", { params }),
  getResponders: (params?: { start_time?: string; end_time?: string; responder_id?: string; unit_id?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/responders", { params }),
  getNotifications: (params?: { start_time?: string; end_time?: string; bypass_cache?: boolean }) =>
    api.get("/analytics/notifications", { params }),
  getDataQuality: () => api.get("/analytics/data-quality"),
  getTouristStats: (touristId: string) => api.get(`/analytics/tourists/${touristId}`),
  getMyStats: () => api.get("/analytics/tourist/my-stats"),
  createExport: (data: { export_type: string; format?: string; filters?: any }) =>
    api.post("/analytics/export", data),
  getExportStatus: (jobId: string) => api.get(`/analytics/export/${jobId}`),
  getDownloadUrl: (jobId: string) => `${API_BASE}/api/v1/analytics/export/${jobId}/download`,
  // Backward compatibility aliases
  getKPIs: () => api.get("/analytics/overview"),
  getResponseTimes: (days = 30) => api.get("/analytics/incidents", { params: { days } }),
  getIncidentTrends: (days = 30) => api.get("/analytics/overview", { params: { days } }),
  getZoneStats: () => api.get("/analytics/zones"),
  getHeatmapData: () => api.get("/analytics/heatmaps"),
  getAlertDistribution: () => api.get("/analytics/safety"),
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

export const commandCenterApi = {
  getSnapshot: () => api.get<any>("/authority/command-center/snapshot"),
  getSystemStatus: () => api.get<any>("/authority/command-center/system-status"),
  search: (q: string, type?: string) => api.get<any>("/authority/command-center/search", { params: { q, type } }),
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
  analyticsApi.getOverview = () =>
    okd({
      active_tourists: MOCK_KPI.total_active,
      active_tracking_sessions: MOCK_KPI.total_active,
      tourists_in_elevated_safety: 2,
      tourists_in_zones: 15,
      open_incidents: MOCK_KPI.alerts_today,
      responding_incidents: 1,
      sos_events_today: MOCK_KPI.status_breakdown.sos,
      total_incidents_in_period: 12,
      total_anomalies_in_period: 8,
      median_response_time_seconds: 420.0,
      p90_response_time_seconds: 780.0,
      tracking_coverage_percentage: 95.4,
      gps_availability_percentage: 99.1,
      freshness: { is_cached: false, data_status: "REAL_DATA" },
      incident_trend: [
        { timestamp: "2026-08-16T00:00:00Z", count: 2, value: 2 },
        { timestamp: "2026-08-17T00:00:00Z", count: 1, value: 1 },
        { timestamp: "2026-08-18T00:00:00Z", count: 4, value: 4 },
        { timestamp: "2026-08-19T00:00:00Z", count: 2, value: 2 },
        { timestamp: "2026-08-20T00:00:00Z", count: 3, value: 3 },
      ],
      safety_state_distribution: { NORMAL: 42, WATCH: 3, ELEVATED: 1, INCIDENT: 1 },
    });

  analyticsApi.getIncidents = () =>
    okd({
      total_incidents: 12,
      open_incidents: 2,
      resolved_incidents: 9,
      closed_incidents: 8,
      cancelled_incidents: 1,
      escalated_incidents: 2,
      false_alarms: 1,
      false_alarm_rate: 0.083,
      by_source: { MANUAL_SOS: 5, SAFETY_ENGINE: 6, AUTHORITY_CREATED: 1 },
      by_severity: { LOW: 3, MEDIUM: 5, HIGH: 3, CRITICAL: 1 },
      by_zone: { "zone-1": 4, "zone-2": 3 },
      time_to_acknowledge: { count: 12, p50_seconds: 180.0, p90_seconds: 360.0, mean_seconds: 210.0 },
      time_to_assign: { count: 12, p50_seconds: 240.0, p90_seconds: 480.0, mean_seconds: 270.0 },
      time_to_response: { count: 12, p50_seconds: 420.0, p90_seconds: 780.0, mean_seconds: 450.0 },
      time_to_arrival: { count: 10, p50_seconds: 600.0, p90_seconds: 960.0, mean_seconds: 640.0 },
      time_to_resolution: { count: 9, p50_seconds: 900.0, p90_seconds: 1400.0, mean_seconds: 950.0 },
      sla_threshold_seconds: 900.0,
      within_sla_count: 8,
      outside_sla_count: 1,
      sla_compliance_rate: 88.9,
      time_series: [],
      freshness: { is_cached: false },
    });

  analyticsApi.getZones = () =>
    okd({
      zones: MOCK_ZONE_SUMMARY.map((z: any) => ({
        zone_id: z.id,
        name: z.name,
        risk_level: z.risk_level || "medium",
        zone_type: z.zone_type || "safe",
        unique_tourists: z.tourist_count,
        total_entries: z.tourist_count * 2,
        total_exits: z.tourist_count * 2 - 1,
        total_dwell_events: z.tourist_count,
        avg_dwell_seconds: 1200.0,
        max_dwell_seconds: 3600.0,
        incident_count: z.active_alerts,
        anomaly_count: 1,
        sos_count: 0,
        active_tourists_now: z.tourist_count,
      })),
      total_zones: MOCK_ZONE_SUMMARY.length,
      freshness: { is_cached: false },
    });

  analyticsApi.getZoneDetail = (zoneId: string) =>
    okd({
      zone_id: zoneId,
      name: "Zone Detail",
      risk_level: "low",
      zone_type: "safe",
      unique_tourists: 15,
      entries_count: 30,
      exits_count: 28,
      dwell_count: 15,
      average_dwell_seconds: 1200.0,
      maximum_dwell_seconds: 3600.0,
      incidents_count: 1,
      sos_count: 0,
      anomalies_count: 1,
      hourly_entry_distribution: {},
      time_series: [],
      freshness: { is_cached: false },
    });

  analyticsApi.getHeatmaps = () =>
    okd({
      layer_type: "tourist_density",
      cells: MOCK_HEATMAP_POINTS.map((pt: any, idx: number) => ({
        geohash: `gh_${idx}`,
        latitude: pt.latitude,
        longitude: pt.longitude,
        weight: pt.weight,
        sample_count: pt.weight,
        is_suppressed: false,
      })),
      total_cells: MOCK_HEATMAP_POINTS.length,
      suppressed_cells_count: 0,
      privacy_threshold_k: 3,
      freshness: { is_cached: false },
    });

  analyticsApi.getAnomalies = () =>
    okd({
      total_anomalies: 8,
      active_anomalies: 1,
      cleared_anomalies: 7,
      by_model_version: { "v1.0.0": 8 },
      by_zone: { "zone-1": 3 },
      score_distribution: { "0.0-0.5": 1, "0.5-0.7": 3, "0.7-0.9": 3, "0.9-1.0": 1, ">1.0": 0 },
      mean_duration_seconds: 42.0,
      median_duration_seconds: 38.0,
      incident_conversion_count: 2,
      cleared_without_incident_count: 6,
      operational_conversion_rate: 0.25,
      inference_latency_avg_ms: 18.4,
      time_series: [],
      freshness: { is_cached: false },
    });

  analyticsApi.getSafety = () =>
    okd({
      total_decisions: 150,
      state_counts: { NORMAL: 135, WATCH: 10, ELEVATED: 3, INCIDENT: 2 },
      transition_frequencies: { "NORMAL->WATCH": 10, "WATCH->ELEVATED": 3 },
      unknown_state_causes: { "GPS unavailable": 2 },
      time_series: [],
      freshness: { is_cached: false },
    });

  analyticsApi.getResponders = () =>
    okd({
      total_responders: 8,
      active_responders: 6,
      available_responders: 4,
      assigned_responders: 2,
      offline_responders: 2,
      total_assignments: 14,
      completed_assignments: 12,
      rejected_assignments: 1,
      rejection_rate: 0.071,
      acceptance_rate: 0.929,
      p50_response_time_seconds: 120.0,
      p90_response_time_seconds: 240.0,
      p50_arrival_time_seconds: 480.0,
      p90_arrival_time_seconds: 720.0,
      assignments_by_responder_type: { POLICE: 8, MEDICAL: 4, FIRE: 2 },
      unit_performance: [{ unit_id: "u-1", unit_name: "Central Police Unit", total_assignments: 8, completed: 7, active_responders: 4 }],
      freshness: { is_cached: false },
    });

  analyticsApi.getNotifications = () =>
    okd({
      total_created: 45,
      total_sent: 43,
      total_delivered: 41,
      total_failed: 2,
      delivery_success_rate: 95.3,
      channel_distribution: { PUSH: 30, SMS: 10, EMAIL: 5 },
      category_distribution: { EMERGENCY: 15, SYSTEM: 30 },
      provider_health: { FIREBASE: { sent: 30, delivered: 29, failed: 1 }, TWILIO: { sent: 10, delivered: 9, failed: 1 } },
      dead_letter_count: 0,
      mean_delivery_latency_ms: 320.0,
      freshness: { is_cached: false },
    });

  analyticsApi.getDataQuality = () =>
    okd({
      overall_health: "GOOD",
      gps_quality: { domain: "GPS Telemetry", status: "GOOD", score: 98.5, details: { evaluated_samples: 450 } },
      telemetry_quality: { domain: "IMU Telemetry Pipeline", status: "GOOD", score: 99.1, details: { samples_last_24h: 1200 } },
      ml_inference_quality: { domain: "LSTM Anomaly Inference", status: "GOOD", score: 99.4, details: { inference_latency_avg_ms: 18.4 } },
      zone_geometry_validity: { domain: "Zone Geometry Validity", status: "GOOD", score: 100.0, details: { active_zones: 4 } },
      incident_completeness: { domain: "Incident Audit Trail", status: "GOOD", score: 100.0, details: { incidents_last_24h: 3 } },
      notification_delivery_health: { domain: "Notification Delivery", status: "GOOD", score: 95.3, details: { providers_online: 3 } },
      freshness: { is_cached: false },
    });

  analyticsApi.getTouristStats = (touristId: string) =>
    okd({
      tourist_id: touristId,
      total_trips: 3,
      completed_trips: 2,
      total_distance_km: 18.4,
      total_duration_hours: 6.2,
      unique_zones_visited: 4,
      trips: [],
      freshness: { is_cached: false },
    });

  analyticsApi.getMyStats = () =>
    okd({
      tourist_id: MOCK_LOGGED_IN_TOURIST.id,
      total_trips: 3,
      completed_trips: 2,
      total_distance_km: 18.4,
      total_duration_hours: 6.2,
      unique_zones_visited: 4,
      trips: [
        {
          trip_id: "trip-01",
          title: "Taj Mahal Heritage Walk",
          status: "completed",
          started_at: "2026-08-20T09:00:00Z",
          ended_at: "2026-08-20T12:30:00Z",
          distance_km: 7.8,
          zones_visited_count: 2,
          zones_visited_names: ["Taj East Gate Zone", "Heritage Corridor"],
          total_dwell_seconds: 4200.0,
          gps_accuracy_avg_meters: 8.2,
          safety_events_count: 0,
          incidents_count: 0,
          sos_count: 0,
          tracking_gaps_count: 0,
        },
        {
          trip_id: "trip-02",
          title: "Fatehpur Sikri Excursion",
          status: "completed",
          started_at: "2026-08-21T10:00:00Z",
          ended_at: "2026-08-21T15:00:00Z",
          distance_km: 10.6,
          zones_visited_count: 1,
          zones_visited_names: ["Monument Safety Perimeter"],
          total_dwell_seconds: 5400.0,
          gps_accuracy_avg_meters: 10.5,
          safety_events_count: 0,
          incidents_count: 0,
          sos_count: 0,
          tracking_gaps_count: 0,
        },
      ],
      freshness: { is_cached: false },
    });

  analyticsApi.createExport = (data: any) =>
    okd({
      job_id: `exp_${Date.now()}`,
      requested_by: "authority_admin",
      export_type: data.export_type || "incidents",
      format: data.format || "csv",
      status: "completed",
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      file_reference: `export_${data.export_type || "incidents"}.${data.format || "csv"}`,
      record_count: 12,
      file_size_bytes: 4096,
      download_url: `/api/v1/analytics/export/exp_mock/download`,
    }, 600);

  analyticsApi.getExportStatus = (jobId: string) =>
    okd({
      job_id: jobId,
      requested_by: "authority_admin",
      export_type: "incidents",
      format: "csv",
      status: "completed",
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      file_reference: `export_${jobId}.csv`,
      record_count: 12,
      file_size_bytes: 4096,
      download_url: `/api/v1/analytics/export/${jobId}/download`,
    });

  // Backward compatibility mock handlers
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

  // ── commandCenterApi ────────────────────────────────────────────────────────
  commandCenterApi.getSnapshot = () => {
    const liveTourists = MOCK_TOURISTS.map((t: any) => ({
      tourist_id: t.id,
      user_id: t.user_id,
      full_name: t.full_name,
      phone: t.phone_e164,
      nationality: t.nationality,
      safety_state: t.status === "sos" ? "INCIDENT" : t.status === "warning" ? "ELEVATED" : "NORMAL",
      tracking_status: "active",
      latitude: t.current_lat,
      longitude: t.current_lng,
      altitude: 12.5,
      accuracy_m: 4.8,
      speed_mps: 1.2,
      heading_deg: 180,
      battery_pct: t.battery_pct || 85,
      current_zone_id: t.current_zone_id,
      current_zone_name: "Zone",
      last_updated_at: new Date().toISOString(),
      staleness: "LIVE",
      verification_status: "verified",
      credential_status: "active",
    }));

    const liveIncidents = MOCK_INCIDENTS.map((inc: any) => ({
      incident_id: inc.incident_id || inc.id,
      tourist_id: inc.tourist_id || "tourist_1",
      tourist_name: inc.tourist_name || "Tourist",
      source: inc.source || "SAFETY_ENGINE",
      severity: inc.severity || "HIGH",
      status: inc.status || "OPEN",
      started_at: inc.created_at || new Date().toISOString(),
      created_at: inc.created_at || new Date().toISOString(),
      updated_at: inc.updated_at || new Date().toISOString(),
      age_seconds: 180,
      assigned_responder_id: inc.assigned_responder_id,
      latitude: inc.latitude || 15.4989,
      longitude: inc.longitude || 73.8278,
      reasons: inc.reasons || ["Safety alert triggered"],
      signal_summary: inc.signals || {},
      timeline_summary: inc.timeline || [],
      version: 1,
      is_sos: inc.is_sos || inc.severity === "CRITICAL",
    }));

    const liveResponders = [
      {
        responder_id: "resp_01",
        full_name: "Patrol Unit North 1",
        unit_id: "unit_north_1",
        unit_name: "North Beach Patrol",
        unit_type: "POLICE",
        status: "AVAILABLE",
        latitude: 15.5500,
        longitude: 73.7600,
        battery_pct: 94,
        capabilities: ["FIRST_AID", "WATER_RESCUE", "PATROL"],
        last_location_time: new Date().toISOString(),
        staleness: "LIVE",
      },
      {
        responder_id: "resp_02",
        full_name: "Medical Unit 2",
        unit_id: "unit_med_2",
        unit_name: "Emergency Medical Unit",
        unit_type: "PARAMEDIC",
        status: "ASSIGNED",
        latitude: 15.5200,
        longitude: 73.8200,
        battery_pct: 88,
        capabilities: ["PARAMEDIC", "AMBULANCE"],
        last_location_time: new Date().toISOString(),
        staleness: "LIVE",
      },
    ];

    const liveZones = MOCK_ZONES.map((z: any) => ({
      zone_id: z.id,
      name: z.name,
      description: z.description,
      zone_type: z.zone_type,
      risk_level: z.risk_level || "critical",
      status: "active",
      is_active: true,
      center_lat: z.center_lat,
      center_lng: z.center_lng,
      boundary: z.boundary,
      center: { type: "Point", coordinates: [z.center_lng, z.center_lat] },
      active_tourists_count: z.tourist_count || 3,
      active_incidents_count: z.active_alerts || 0,
      recent_events_count: z.active_alerts || 0,
    }));

    return okd({
      snapshot_id: `snap_${Date.now()}`,
      server_time: new Date().toISOString(),
      authority_scope: {
        authority_id: "auth_goa_01",
        user_id: "user_auth_1",
        full_name: "Operations Chief",
        organization_name: "Goa Police Tourism Dept",
        designation: "Commanding Officer",
        role: "authority",
        jurisdiction_code: "IN-GOA-NORTH",
        permissions: ["view_snapshot", "acknowledge_incident", "assess_incident", "assign_responder", "escalate_incident", "resolve_incident", "close_incident"],
      },
      kpis: {
        active_tourists: liveTourists.length,
        open_incidents: liveIncidents.length,
        sos_incidents: liveIncidents.filter((i: any) => i.is_sos).length,
        active_responders: liveResponders.length,
        unassigned_incidents: liveIncidents.filter((i: any) => !i.assigned_responder_id).length,
        elevated_safety_states: liveTourists.filter((t: any) => t.safety_state !== "NORMAL").length,
        stale_tracking_tourists: 0,
      },
      system_health: {
        realtime: "HEALTHY",
        telemetry: "HEALTHY",
        ml: "HEALTHY",
        notifications: "HEALTHY",
        map: "HEALTHY",
        backend: "HEALTHY",
        details: { mode: "MOCK_OPERATIONAL_MODE" },
        checked_at: new Date().toISOString(),
      },
      active_incidents: liveIncidents,
      sos_queue: liveIncidents.filter((i: any) => i.is_sos),
      tourists: liveTourists,
      responders: liveResponders,
      zones: liveZones,
      freshness: { is_cached: false, generated_at: new Date().toISOString() },
    });
  };

  commandCenterApi.getSystemStatus = () =>
    okd({
      realtime: "HEALTHY",
      telemetry: "HEALTHY",
      ml: "HEALTHY",
      notifications: "HEALTHY",
      map: "HEALTHY",
      backend: "HEALTHY",
      details: { mode: "MOCK_OPERATIONAL_MODE" },
      checked_at: new Date().toISOString(),
    });

  commandCenterApi.search = (q: string) =>
    okd({
      query: q,
      results: [
        {
          id: "tourist_1",
          entity_type: "tourist",
          title: "Alice Smith",
          subtitle: "UK • Safety: NORMAL",
          badge: "NORMAL",
          status: "active",
          latitude: 15.4989,
          longitude: 73.8278,
          metadata: {},
        },
      ],
      total_count: 1,
    });
}