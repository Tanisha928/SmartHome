import type { User, DashboardSettingsInput } from "../api/apiClient";
import type { Alert, AlertFilters, NotificationPreference, Threshold } from "../features/alerts/types";
import type { House, Room, Device } from "../features/devices/types";
import type { PipelineEvent, RetentionPolicy, AuditRow } from "../features/dataops/types";

// Presentation data lives only in this browser. Read on each request so tabs agree.
const KEY = "smarthome:workspace:v1";
export type DemoState = {
  houses: House[]; rooms: Room[]; devices: Device[];
  profiles: Record<string, User>; settings: Record<string, DashboardSettingsInput>;
  preferences: Record<string, NotificationPreference[]>;
  savedViews: Record<string, AlertFilters[]>; thresholds: Threshold[];
  retention: RetentionPolicy; events: PipelineEvent[]; audit: AuditRow[];
  alerts: Alert[];
};
export function initialDemoState(): DemoState {
  return {
    houses: [{ house_id: 1, address_line: "1 Demo Way", city: "Seattle", state: "WA", postal_code: "98101", latitude: 47.6062, longitude: -122.3321, timezone: "UTC", status: "active" }],
    rooms: [{ room_id: 1, house_id: 1, room_type: "kitchen", label: "Kitchen" }],
    devices: [{ device_id: 7, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo", label: "Kitchen monitor", status: "enabled", conn_state: "online", wifi_rssi: -55, last_heartbeat: new Date().toISOString(), config_version: 1 }],
    profiles: {}, settings: {}, preferences: {}, savedViews: {}, alerts: [],
    thresholds: [{ id: 1, scope: "global", scope_id: null, sound_type: "fall", threshold: 0.8 }],
    retention: { clip_expire_days: 30, clip_ia_transition_days: null, telemetry_ttl_days: 30 },
    events: [{ event_id: 1, house_id: 1, device_id: 7, processing_state: "failed", retry_count: 1, captured_at: new Date().toISOString(), correlation_id: "demo-event-1" }], audit: [],
  };
}
export function readDemoState(): DemoState {
  try { const stored = localStorage.getItem(KEY); if (stored) return JSON.parse(stored) as DemoState; } catch { /* recover an invalid presentation cache */ }
  return initialDemoState();
}
export function writeDemoState(state: DemoState) { localStorage.setItem(KEY, JSON.stringify(state)); }
export function nextId(items: number[]) { return Math.max(0, ...items) + 1; }
export const defaultDashboardSettings: DashboardSettingsInput = { default_map_latitude: 47.6062, default_map_longitude: -122.3321, show_critical_toasts: true, play_alert_sound: true };

