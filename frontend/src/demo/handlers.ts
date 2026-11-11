import { http, HttpResponse } from "msw";
import { demoAlerts, demoPage, demoStats } from "./fixtures";

const demoSettings = { default_map_latitude: 47.6062, default_map_longitude: -122.3321, show_critical_toasts: true, play_alert_sound: true, updated_at: new Date().toISOString() };
const demoPreferences = [{ alert_category: "safety", email: true, sms: true, min_severity: "high" }];
const demoThresholds = [{ id: 1, scope: "global", scope_id: null, sound_type: "fall", threshold: 0.8 }];
let demoCurrentAlert = { ...demoAlerts[0] };
const demoDetail = () => ({ ...demoCurrentAlert, history: [{ history_id: 1, from_state: null, to_state: "new", actor_user_id: null, note: null, changed_at: demoCurrentAlert.created_at }, ...(demoCurrentAlert.state !== "new" ? [{ history_id: 2, from_state: "new", to_state: demoCurrentAlert.state, actor_user_id: 1, note: "Demo acceptance flow", changed_at: demoCurrentAlert.updated_at }] : [])], deliveries: [{ notification_id: 1, recipient_id: 2, recipient_label: "Demo Owner", channel: "email", status: "sent", attempts: 1, last_error: null, sent_at: demoCurrentAlert.created_at }] });
export const handlers = [
  http.post("*/api/auth/login", async ({ request }) => { const body = await request.json() as { email?: string }; const owner = body.email?.includes("owner"); return HttpResponse.json({ access_token: "demo-token", user: { id: owner ? 2 : 1, email: body.email, full_name: owner ? "Demo Owner" : "Demo Admin", role: owner ? "owner" : "admin", house_ids: [1] } }); }),
  http.post("*/api/auth/signup", () => HttpResponse.json({ id: 2, email: "owner@example.com", full_name: "Demo Owner", role: "owner", house_ids: [] }, { status: 201 })),
  http.post("*/api/auth/refresh", () => HttpResponse.json({ access_token: "demo-token" })),
  http.post("*/api/auth/logout", () => new HttpResponse(null, { status: 204 })),
  http.get("*/api/users/me", () => HttpResponse.json({ id: 1, email: "admin@example.com", full_name: "Demo Admin", role: "admin", house_ids: [1] })),
  http.get("*/api/alerts", () => HttpResponse.json({ ...demoPage, items: [demoCurrentAlert, ...demoPage.items.filter((item) => item.alert_id !== demoCurrentAlert.alert_id)] })),
  http.get("*/api/alerts/:id", () => HttpResponse.json(demoDetail())),
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
  http.get("*/api/admin/data/health", () => HttpResponse.json({ queue_depth: 0, dlq_depth: 0, event_counts: {}, inference_latency_ms: 0, last_backup_at: null })),
  http.get("*/api/admin/events", () => HttpResponse.json({ items: [], total: 0 })),
  http.post("*/api/admin/events/:id/retry", () => HttpResponse.json({ event_id: 1, processing_state: "queued" })),
  http.get("*/api/admin/inference-logs", () => HttpResponse.json({ items: [], total: 0 })),
  http.get("*/api/admin/retention", () => HttpResponse.json({ clip_expire_days: 30, clip_ia_transition_days: null, telemetry_ttl_days: 30 })),
  http.put("*/api/admin/retention", async ({ request }) => HttpResponse.json(await request.json())),
  http.get("*/api/users/me/dashboard-settings", () => HttpResponse.json(demoSettings)),
  http.put("*/api/users/me/dashboard-settings", async ({ request }) => Object.assign(demoSettings, await request.json(), { updated_at: new Date().toISOString() }) && HttpResponse.json(demoSettings)),
  http.get("*/api/users/me/saved-views", () => HttpResponse.json({ views: [] })),
  http.put("*/api/users/me/saved-views", () => HttpResponse.json({ views: [] })),
  http.get("*/api/notification-prefs", () => HttpResponse.json({ house_id: 1, items: demoPreferences })),
  http.put("*/api/notification-prefs", async ({ request }) => HttpResponse.json({ house_id: 1, items: await request.json() })),
  http.get("*/api/admin/thresholds", () => HttpResponse.json({ items: demoThresholds })),
  http.put("*/api/admin/thresholds", async ({ request }) => HttpResponse.json(await request.json())),
  http.patch("*/api/alerts/:id/state", async ({ request }) => { const body = await request.json() as { to_state?: string; note?: string }; demoCurrentAlert = { ...demoCurrentAlert, state: (body.to_state ?? demoCurrentAlert.state) as typeof demoCurrentAlert.state, version: demoCurrentAlert.version + 1, updated_at: new Date().toISOString() }; return HttpResponse.json(demoCurrentAlert); }),
];
