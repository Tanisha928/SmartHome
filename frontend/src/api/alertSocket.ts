import { apiRequest } from "./apiClient";
import type { Alert, AlertPage } from "../features/alerts/types";

export type SocketState = "disconnected" | "connecting" | "catching_up" | "live" | "backoff_polling" | "refreshing_token";
type Options = { houseIds: number[]; token: string; refreshToken?: () => Promise<string | null>; onState: (state: SocketState) => void; onAlerts: (alerts: Alert[]) => void; onMessage: (event: { type: "alert.created" | "alert.updated"; alert: Alert }) => void };

export class AlertSocket {
  private socket: WebSocket | null = null;
  private timer: number | undefined;
  private pollTimer: number | undefined;
  private attempt = 0;
  private lastSeen: string | undefined;
  private token: string;
  constructor(private readonly options: Options) { this.token = options.token; }
  start() { this.connect(); this.pollTimer = window.setInterval(() => this.poll(), 30_000); }
  stop() { if (this.timer) window.clearTimeout(this.timer); if (this.pollTimer) window.clearInterval(this.pollTimer); this.socket?.close(); this.socket = null; this.options.onState("disconnected"); }
  private connect() {
    this.options.onState("connecting");
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    this.socket = new WebSocket(`${protocol}://${location.host}/ws/alerts`, ["bearer", this.token]);
    this.socket.onopen = () => { this.options.onState("catching_up"); void this.catchUp(); };
    this.socket.onmessage = (message) => { const event = JSON.parse(String(message.data)) as { type: "alert.created" | "alert.updated"; alert: Alert }; if (event.alert) this.lastSeen = event.alert.updated_at ?? event.alert.created_at ?? this.lastSeen; this.options.onMessage(event); this.options.onState("live"); };
    this.socket.onclose = () => { if (this.socket) void this.reconnectAfterClose(); };
    this.socket.onerror = () => this.socket?.close();
  }
  private async catchUp() { try { const page = await apiRequest<AlertPage>(`/api/alerts?updated_since=${encodeURIComponent(this.lastSeen ?? "")}`); this.options.onAlerts(page.items); this.options.onState("live"); this.attempt = 0; } catch { this.options.onState("backoff_polling"); this.poll(); this.scheduleRetry(); } }
  private poll() { this.options.onState("backoff_polling"); void apiRequest<AlertPage>(`/api/alerts?updated_since=${encodeURIComponent(this.lastSeen ?? "")}`).then((page) => { this.options.onAlerts(page.items); this.options.onState("live"); }).catch(() => undefined); }
  private async reconnectAfterClose() { if (this.options.refreshToken) { this.options.onState("refreshing_token"); const token = await this.options.refreshToken(); if (token) { this.token = token; this.attempt = 0; this.connect(); return; } } this.scheduleRetry(); }
  private scheduleRetry() { this.attempt += 1; const delay = Math.min(30_000, 1_000 * 2 ** (this.attempt - 1)); this.options.onState("backoff_polling"); this.timer = window.setTimeout(() => this.connect(), delay); }
}
