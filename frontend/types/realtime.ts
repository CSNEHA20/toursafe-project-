/**
 * TourSafe Realtime Type Definitions
 * Canonical Realtime Event Envelope, Channels, and Connection States
 */

export type RealtimeConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

export interface RealtimeEnvelope<T = any> {
  event_id: string;
  event_type: string;
  timestamp: string;
  source: string;
  version: number;
  payload: T;
}

export type RealtimeEventHandler<T = any> = (
  payload: T,
  envelope: RealtimeEnvelope<T>
) => void;

export type RealtimeStateListener = (state: RealtimeConnectionState) => void;

export interface RealtimeDiagnostics {
  state: RealtimeConnectionState;
  connectionId: string | null;
  userId: string | null;
  role: string | null;
  connectedAt: string | null;
  reconnectCount: number;
  lastEventTimestamp: string | null;
  lastEventType: string | null;
  eventsReceived: number;
  eventsSent: number;
  lastError: string | null;
  subscribedChannels: string[];
}

export interface RealtimeSystemConnectedPayload {
  connection_id: string;
  user_id: string;
  role: string;
  channels: string[];
  connected_at: string;
}

export interface RealtimeSystemErrorPayload {
  error: string;
  channel?: string;
  code?: number;
}

export interface RealtimeSystemHeartbeatPayload {
  type: string;
  timestamp: string;
}

export interface RealtimeSystemStatusPayload {
  subscribed?: string;
  unsubscribed?: string;
  status?: string;
}
