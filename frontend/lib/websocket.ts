import { useEffect, useRef, useCallback } from "react";
import type { WSMessage } from "@/types";

// React Native ships a global WebSocket implementation, so this hook is
// unchanged from the web version — no browser-only APIs were used here.
const WS_URL = process.env.EXPO_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

type MessageHandler = (msg: WSMessage) => void;

export function useWebSocket(onMessage: MessageHandler, token?: string) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!token) return;
    const url = `${WS_URL}?token=${token}`;
    const socket = new WebSocket(url);

    socket.onopen = () => {
      console.log("[WS] Connected");
    };

    socket.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data as string);
        onMessage(msg);
      } catch {
        // ignore parse errors
      }
    };

    socket.onclose = () => {
      if (mountedRef.current) {
        reconnectTimeout.current = setTimeout(connect, 3000);
      }
    };

    socket.onerror = () => {
      socket.close();
    };

    ws.current = socket;
  }, [token, onMessage]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimeout.current !== null) clearTimeout(reconnectTimeout.current);
      ws.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}
