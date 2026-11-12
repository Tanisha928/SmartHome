/** Subscribe a screen to server-pushed events on /ws/alerts (alert.* and device.updated). */

import { useEffect, useRef } from "react";
import { getAccessToken, socketUrl } from "./apiClient";

export type LiveEvent = { type: string; house_id?: number; version?: number; alert?: unknown; device?: unknown };

/**
 * One house, or every house for admins (`houseId` undefined). Keep-alive pings are filtered out.
 * Reconnects with bounded backoff (1 s → 30 s); screens keep their own load/refresh as fallback.
 */
export function useLiveEvents(houseId: number | undefined, onEvent: (event: LiveEvent) => void) {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;

    const connect = () => {
      const token = getAccessToken();
      if (!token || stopped || typeof WebSocket === "undefined") return;
      socket = new WebSocket(socketUrl("/ws/alerts", { house_id: houseId }), ["bearer", token]);
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(String(message.data)) as LiveEvent;
          if (event.type && event.type !== "ping") handler.current(event);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        attempt += 1;
        timer = setTimeout(connect, Math.min(30_000, 1_000 * 2 ** (attempt - 1)));
      };
    };

    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [houseId]);
}
