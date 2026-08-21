/**
 * TourSafe Centralized Realtime WebSocket Client
 * Managed full-duplex authenticated real-time communication layer.
 */

import { Platform } from "react-native";
import type {
  RealtimeConnectionState,
  RealtimeDiagnostics,
  RealtimeEnvelope,
  RealtimeEventHandler,
  RealtimeStateListener,
  RealtimeSystemConnectedPayload,
} from "@/types/realtime";

const DEFAULT_WS_URL =
  process.env.EXPO_PUBLIC_WS_URL ||
  (Platform.OS === "web" ? "ws://localhost:8000/ws" : "ws://10.0.2.2:8000/ws");

class RealtimeClient {
  private ws: WebSocket | null = null;
  private state: RealtimeConnectionState = "disconnected";
  private token: string | null = null;
  private url: string = DEFAULT_WS_URL;

  private eventListeners: Map<string, Set<RealtimeEventHandler>> = new Map();
  private wildcardListeners: Set<RealtimeEventHandler> = new Set();
  private stateListeners: Set<RealtimeStateListener> = new Set();

  private activeSubscriptions: Set<string> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectDelay = 10000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private isIntentionallyClosed = false;

  // Diagnostics telemetry
  private diagnostics: RealtimeDiagnostics = {
    state: "disconnected",
    connectionId: null,
    userId: null,
    role: null,
    connectedAt: null,
    reconnectCount: 0,
    lastEventTimestamp: null,
    lastEventType: null,
    eventsReceived: 0,
    eventsSent: 0,
    lastError: null,
    subscribedChannels: [],
  };

  constructor() {
    this.setState("disconnected");
  }

  public setToken(token: string | null) {
    this.token = token;
    if (!token && this.state === "connected") {
      this.disconnect();
    }
  }

  public getConnectionState(): RealtimeConnectionState {
    return this.state;
  }

  public getDiagnostics(): RealtimeDiagnostics {
    return {
      ...this.diagnostics,
      state: this.state,
      subscribedChannels: Array.from(this.activeSubscriptions),
    };
  }

  public connect(token?: string) {
    if (token) {
      this.token = token;
    }

    if (!this.token) {
      console.warn("[RealtimeClient] Connect aborted: No authentication token available.");
      this.setState("disconnected");
      return;
    }

    if (this.ws && (this.state === "connected" || this.state === "connecting")) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.setState(this.reconnectAttempts > 0 ? "reconnecting" : "connecting");

    try {
      const endpoint = `${this.url}?token=${encodeURIComponent(this.token)}`;
      this.ws = new WebSocket(endpoint);

      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch (err: any) {
      this.diagnostics.lastError = err?.message || "Failed to initialize WebSocket";
      this.setState("error");
      this.scheduleReconnect();
    }
  }

  public disconnect() {
    this.isIntentionallyClosed = true;
    this.clearTimers();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore close error
      }
      this.ws = null;
    }
    this.reconnectAttempts = 0;
    this.setState("disconnected");
  }

  public subscribe(channel: string) {
    if (!channel) return;
    this.activeSubscriptions.add(channel);

    if (this.state === "connected" && this.ws?.readyState === WebSocket.OPEN) {
      this.sendRaw({
        action: "subscribe",
        channel,
      });
    }
  }

  public unsubscribe(channel: string) {
    if (!channel) return;
    this.activeSubscriptions.delete(channel);

    if (this.state === "connected" && this.ws?.readyState === WebSocket.OPEN) {
      this.sendRaw({
        action: "unsubscribe",
        channel,
      });
    }
  }

  public onEvent<T = any>(
    eventType: string,
    handler: RealtimeEventHandler<T>
  ): () => void {
    if (eventType === "*") {
      this.wildcardListeners.add(handler);
      return () => this.wildcardListeners.delete(handler);
    }

    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(handler);

    return () => {
      this.eventListeners.get(eventType)?.delete(handler);
    };
  }

  public offEvent(eventType: string, handler: RealtimeEventHandler) {
    if (eventType === "*") {
      this.wildcardListeners.delete(handler);
    } else {
      this.eventListeners.get(eventType)?.delete(handler);
    }
  }

  public onStateChange(listener: RealtimeStateListener): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  public send(action: string, payload?: any, channel?: string) {
    this.sendRaw({
      action,
      payload,
      channel,
    });
  }

  private sendRaw(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(data));
        this.diagnostics.eventsSent += 1;
      } catch (err: any) {
        console.warn("[RealtimeClient] Send error:", err);
      }
    }
  }

  private handleOpen() {
    this.reconnectAttempts = 0;
    this.diagnostics.lastError = null;
    this.startHeartbeat();
  }

  private handleMessage(event: WebSocketMessageEvent) {
    try {
      const dataStr = typeof event.data === "string" ? event.data : "";
      if (!dataStr) return;

      const envelope: RealtimeEnvelope = JSON.parse(dataStr);
      this.diagnostics.eventsReceived += 1;
      this.diagnostics.lastEventTimestamp = envelope.timestamp || new Date().toISOString();
      this.diagnostics.lastEventType = envelope.event_type;

      // Handle system handshake ack
      if (envelope.event_type === "system.connected") {
        const p = envelope.payload as RealtimeSystemConnectedPayload;
        this.diagnostics.connectionId = p.connection_id;
        this.diagnostics.userId = p.user_id;
        this.diagnostics.role = p.role;
        this.diagnostics.connectedAt = p.connected_at;
        if (Array.isArray(p.channels)) {
          p.channels.forEach((ch) => this.activeSubscriptions.add(ch));
        }

        this.setState("connected");

        // Resubscribe any pending channels
        this.activeSubscriptions.forEach((channel) => {
          this.sendRaw({ action: "subscribe", channel });
        });
      }

      // Dispatch to specific event listeners
      const handlers = this.eventListeners.get(envelope.event_type);
      if (handlers) {
        handlers.forEach((fn) => {
          try {
            fn(envelope.payload, envelope);
          } catch (e) {
            console.error(`[RealtimeClient] Handler error for ${envelope.event_type}:`, e);
          }
        });
      }

      // Dispatch to wildcard listeners
      this.wildcardListeners.forEach((fn) => {
        try {
          fn(envelope.payload, envelope);
        } catch (e) {
          console.error("[RealtimeClient] Wildcard handler error:", e);
        }
      });
    } catch (parseErr) {
      console.warn("[RealtimeClient] Failed to parse message:", parseErr);
    }
  }

  private handleError(event: any) {
    this.diagnostics.lastError = event?.message || "WebSocket encountered an error";
    if (this.state !== "connected") {
      this.setState("error");
    }
  }

  private handleClose(event: WebSocketCloseEvent) {
    this.clearTimers();
    this.ws = null;

    if (this.isIntentionallyClosed) {
      this.setState("disconnected");
      return;
    }

    if (event.code === 1008 || event.code === 4001) {
      // Authentication policy violation
      this.diagnostics.lastError = "Authentication rejected by server";
      this.setState("error");
      return;
    }

    this.setState("reconnecting");
    this.scheduleReconnect();
  }

  private scheduleReconnect() {
    if (this.isIntentionallyClosed || this.reconnectTimer) return;

    this.reconnectAttempts += 1;
    this.diagnostics.reconnectCount += 1;

    // Exponential backoff with jitter: 1s, 2s, 4s, 8s, up to 10s
    const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectDelay);
    const jitter = Math.random() * 500;
    const delay = baseDelay + jitter;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.isIntentionallyClosed) {
        this.connect();
      }
    }, delay);
  }

  private startHeartbeat() {
    this.clearTimers();
    this.pingTimer = setInterval(() => {
      if (this.state === "connected" && this.ws?.readyState === WebSocket.OPEN) {
        this.sendRaw({ action: "ping" });
      }
    }, 25000);
  }

  private clearTimers() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setState(newState: RealtimeConnectionState) {
    this.state = newState;
    this.diagnostics.state = newState;
    this.stateListeners.forEach((listener) => {
      try {
        listener(newState);
      } catch (err) {
        console.error("[RealtimeClient] State listener error:", err);
      }
    });
  }
}

// Global Singleton Realtime Client
export const realtimeClient = new RealtimeClient();

export function connectRealtime(token?: string) {
  realtimeClient.connect(token);
}

export function disconnectRealtime() {
  realtimeClient.disconnect();
}
