/**
 * TourSafe React Hook for WebSocket Integration
 * Integrates with the centralized singleton RealtimeClient.
 */

import { useEffect, useCallback } from "react";
import { realtimeClient } from "./realtimeClient";
import type { WSMessage } from "@/types";

type MessageHandler = (msg: WSMessage) => void;

export function useWebSocket(onMessage: MessageHandler, token?: string) {
  useEffect(() => {
    if (token) {
      realtimeClient.connect(token);
    }

    const unsubscribeWildcard = realtimeClient.onEvent("*", (payload, envelope) => {
      const legacyMsg: WSMessage = {
        type: envelope.event_type as any,
        payload,
        timestamp: envelope.timestamp,
      };
      onMessage(legacyMsg);
    });

    return () => {
      unsubscribeWildcard();
    };
  }, [token, onMessage]);

  const send = useCallback((data: unknown) => {
    if (typeof data === "object" && data !== null) {
      const d = data as any;
      realtimeClient.send(d.action || d.type || "message", d.payload || d, d.channel);
    }
  }, []);

  return { send };
}
