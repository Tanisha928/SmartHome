import { http, HttpResponse } from "msw";
import { demoAlerts, demoStats } from "./fixtures";
import type { Alert } from "../features/alerts/types";

const demoSettings = { default_map_latitude: 47.6062, default_map_longitude: -122.3321, show_critical_toasts: true, play_alert_sound: true, updated_at: new Date().toISOString() };
const demoPreferences = [{ alert_category: "safety", email: true, sms: true, min_severity: "high" }];
const demoThresholds = [{ id: 1, scope: "global", scope_id: null, sound_type: "fall", threshold: 0.8 }];
let demoSavedViews: Array<Record<string, unknown>> = [];
let demoPipelineEvent = { event_id: 1, house_id: 1, device_id: 7, processing_state: "failed", retry_count: 1, captured_at: new Date().toISOString(), correlation_id: "demo-event-1" };
let demoCurrentAlert = { ...demoAlerts[0] };
let demoUser: { id: number; email: string; full_name: string; role: "admin" | "owner"; house_ids: number[] } = { id: 1, email: "admin@example.com", full_name: "Demo Admin", role: "admin", house_ids: [1] };
const simulatedAlerts = () => {
  try {
    const value = JSON.parse(localStorage.getItem("smarthome:demo-alerts") ?? "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
};
const saveSimulatedAlerts = (items: typeof demoAlerts) => localStorage.setItem("smarthome:demo-alerts", JSON.stringify(items));
const allDemoAlerts = () => {
  const simulated = simulatedAlerts();
  let current = demoCurrentAlert;
  try {
    const state = JSON.parse(localStorage.getItem("smarthome:demo-state") ?? "null") as { alert_id?: number; state?: Alert["state"] } | null;
    if (state?.alert_id === current.alert_id && state.state) current = { ...current, state: state.state };
  } catch { /* ignore malformed demo state */ }
  return [current, ...demoAlerts.filter((item) => item.alert_id !== current.alert_id && !simulated.some((alert) => alert.alert_id === item.alert_id)), ...simulated];
};
const filteredDemoAlerts = (request: Request) => {
  const params = new URL(request.url).searchParams;
  const q = params.get("q")?.trim().toLowerCase();
  const severity = params.get("severity");
  const state = params.get("state");
  const category = params.get("category");
  const soundType = params.get("sound_type");
  const from = params.get("from");
  const to = params.get("to");
  const minConfidenceValue = params.get("min_confidence");
  const maxConfidenceValue = params.get("max_confidence");
  const minConfidence = minConfidenceValue === null ? undefined : Number(minConfidenceValue);
  const maxConfidence = maxConfidenceValue === null ? undefined : Number(maxConfidenceValue);
  const filtered = allDemoAlerts().filter((alert) => {
    const text = `${alert.alert_id} ${alert.sound_type ?? ""} ${alert.alert_category} ${alert.house_id} ${alert.room_id}`.toLowerCase();
    const created = alert.created_at ?? "";
    return (!q || text.includes(q)) && (!severity || alert.severity === severity) && (!state || alert.state === state) && (!category || alert.alert_category === category) && (!soundType || alert.sound_type === soundType) && (!from || created >= from) && (!to || created.slice(0, 10) <= to) && (minConfidence === undefined || !Number.isNaN(minConfidence) && (alert.confidence ?? 0) >= minConfidence) && (maxConfidence === undefined || !Number.isNaN(maxConfidence) && (alert.confidence ?? 1) <= maxConfidence);
  });
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const pageSize = Math.min(100, Math.max(1, Number(params.get("page_size") ?? 100)));
  return { items: filtered.slice((page - 1) * pageSize, page * pageSize), total: filtered.length, page, page_size: pageSize };
};
export const handlers = [
  http.post("*/api/auth/login", async ({ request }) => {
    const body = await request.json() as { email?: string };
    const email = body.email?.trim().toLowerCase() ?? "";
    const admin = email === "admin@example.com" || email === "admin@smarthome.local" || email.startsWith("admin@");
    demoUser = { id: admin ? 1 : 2, email: body.email ?? "", full_name: admin ? "Demo Admin" : "Demo Owner", role: admin ? "admin" : "owner", house_ids: [1] };
    return HttpResponse.json({ access_token: "demo-token", user: demoUser });
  }),
  http.post("*/api/auth/signup", () => HttpResponse.json({ id: 2, email: "owner@example.com", full_name: "Demo Owner", role: "owner", house_ids: [] }, { status: 201 })),
  http.post("*/api/auth/refresh", () => HttpResponse.json({ access_token: "demo-token" })),
  http.post("*/api/auth/logout", () => new HttpResponse(null, { status: 204 })),
  http.get("*/api/users/me", () => HttpResponse.json(demoUser)),
  http.get("*/api/alerts", ({ request }) => HttpResponse.json(filteredDemoAlerts(request))),
  http.get("*/api/alerts/:id", ({ params }) => { const alert = allDemoAlerts().find((item) => item.alert_id === Number(params.id)); return HttpResponse.json(alert ? { ...alert, history: [], deliveries: [] } : { error: "not_found", message: "Alert not found" }, { status: alert ? 200 : 404 }); }),
  http.post("*/api/alerts/:id/resend", () => HttpResponse.json({ accepted: true })),
  http.get("*/api/alerts/export", ({ request }) => new HttpResponse(request.url.includes("format=pdf") ? new Uint8Array([37, 80, 68, 70]) : "alert_id,sound_type\n101,fall\n", { headers: { "Content-Type": request.url.includes("format=pdf") ? "application/pdf" : "text/csv" } })),
  http.get("*/api/stats/alerts", () => HttpResponse.json(demoStats)),
  http.get("*/api/stats/false-alerts", () => HttpResponse.json({ items: [] })),
  http.get("*/api/devices", () => HttpResponse.json({ items: [{ device_id: 7, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo", label: "Kitchen monitor", status: "enabled", conn_state: "online", wifi_rssi: -55, last_heartbeat: new Date().toISOString(), config_version: 1 }], total: 1, page: 1, page_size: 100 })),
  http.get("*/api/houses", () => HttpResponse.json({ items: [{ house_id: 1, address_line: "1 Demo Way", city: "Seattle", state: "WA", postal_code: "98101", latitude: 47.6062, longitude: -122.3321, timezone: "UTC", status: "active" }], total: 1, page: 1, page_size: 100 })),
  http.get("*/api/rooms", () => HttpResponse.json({ items: [{ room_id: 1, house_id: 1, room_type: "kitchen", label: "Kitchen" }], total: 1 })),
  http.post("*/api/rooms", async ({ request }) => HttpResponse.json({ room_id: 2, house_id: 1, room_type: "living", label: "Living room", ...(await request.json() as object) }, { status: 201 })),
  http.patch("*/api/rooms/:id", async ({ request }) => HttpResponse.json({ room_id: 1, house_id: 1, room_type: "kitchen", label: "Kitchen", ...(await request.json() as object) })),
  http.patch("*/api/devices/:id", () => HttpResponse.json({ device_id: 7, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo", label: "Kitchen monitor", status: "disabled", conn_state: "online", wifi_rssi: -55, last_heartbeat: new Date().toISOString(), config_version: 1 })),
  http.post("*/api/devices", () => HttpResponse.json({ device_id: 8, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo-new", label: "Demo sensor", status: "enabled", conn_state: "offline", wifi_rssi: null, last_heartbeat: null, config_version: 1, api_key: "dk_demo_once" }, { status: 201 })),
  http.post("*/api/auth/device-token", () => HttpResponse.json({ access_token: "device-token", expires_in: 900 })),
  http.post("*/api/devices/7/heartbeat", () => HttpResponse.json({ device_id: 7, conn_state: "online", commands: [], config: {} })),
  http.delete("*/api/devices/:id", () => new HttpResponse(null, { status: 204 })),
  http.post("*/api/devices/:id/rotate-key", () => HttpResponse.json({ device_id: 7, serial_no: "demo", label: "Kitchen monitor", api_key: "dk_demo_rotated" })),
  http.post("*/api/devices/:id/command", async ({ request }) => HttpResponse.json({ command_id: 1, ...(await request.json() as object), status: "pending" }, { status: 202 })),
  http.post("*/api/houses/:id/disable", () => HttpResponse.json({ house_id: 1, status: "disabled", devices_updated: 1 })),
  http.post("*/api/houses/:id/enable", () => HttpResponse.json({ house_id: 1, status: "active", devices_updated: 1 })),
  http.get("*/api/admin/audit", () => HttpResponse.json({ items: [] })),
  http.get("*/api/admin/data/health", () => HttpResponse.json({ postgres: "ok", mongo: "ok", s3: "ok", sqs: { visible: 0, in_flight: 0 }, dlq: { visible: 0 }, backups: { rds_snapshot_age_h: null, mongo_dump_age_d: null }, unprocessed_events: 0 })),
  http.get("*/api/admin/events", () => HttpResponse.json({ items: [demoPipelineEvent], total: 1 })),
  http.post("*/api/admin/events/:id/retry", () => { demoPipelineEvent = { ...demoPipelineEvent, processing_state: "queued", retry_count: demoPipelineEvent.retry_count + 1 }; return HttpResponse.json({ event_id: demoPipelineEvent.event_id, processing_state: demoPipelineEvent.processing_state }); }),
  http.get("*/api/admin/inference-logs", () => HttpResponse.json({ items: [], total: 0 })),
  http.get("*/api/admin/retention", () => HttpResponse.json({ clip_expire_days: 30, clip_ia_transition_days: null, telemetry_ttl_days: 30 })),
  http.put("*/api/admin/retention", async ({ request }) => HttpResponse.json(await request.json())),
  http.get("*/api/users/me/dashboard-settings", () => HttpResponse.json(demoSettings)),
  http.put("*/api/users/me/dashboard-settings", async ({ request }) => Object.assign(demoSettings, await request.json(), { updated_at: new Date().toISOString() }) && HttpResponse.json(demoSettings)),
  http.get("*/api/users/me/saved-views", () => HttpResponse.json({ views: demoSavedViews })),
  http.put("*/api/users/me/saved-views", async ({ request }) => { const body = await request.json() as { views?: Array<Record<string, unknown>> }; demoSavedViews = body.views ?? []; return HttpResponse.json({ views: demoSavedViews }); }),
  http.get("*/api/notification-prefs", () => HttpResponse.json({ house_id: 1, items: demoPreferences })),
  http.put("*/api/notification-prefs", async ({ request }) => HttpResponse.json({ house_id: 1, items: await request.json() })),
  http.get("*/api/admin/thresholds", () => HttpResponse.json({ items: demoThresholds })),
  http.put("*/api/admin/thresholds", async ({ request }) => HttpResponse.json(await request.json())),
  http.patch("*/api/alerts/:id/state", async ({ params, request }) => { if (request.headers.get("x-demo-conflict") === "true") return HttpResponse.json({ error: "state_conflict", message: "State changed", details: { current_state: "acknowledged", last_actor: "another-admin@example.com" } }, { status: 409 }); const body = await request.json() as { to_state?: string }; const id = Number(params.id); const existing = allDemoAlerts().find((item) => item.alert_id === id); if (!existing) return HttpResponse.json({ error: "not_found", message: "Alert not found" }, { status: 404 }); const updated = { ...existing, state: (body.to_state ?? existing.state) as typeof existing.state, version: existing.version + 1, updated_at: new Date().toISOString() }; if (id === demoCurrentAlert.alert_id) demoCurrentAlert = updated; else saveSimulatedAlerts(simulatedAlerts().map((item) => item.alert_id === id ? updated : item)); return HttpResponse.json(updated); }),
];
