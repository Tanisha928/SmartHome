import { http, HttpResponse } from "msw";
import { demoAlerts } from "./fixtures";
import { readDemoState, writeDemoState, nextId, defaultDashboardSettings } from "./state";
import { retentionError } from "../lib/retention";
import { alertsPdf } from "./exports";
import { toCsv } from "../lib/exportService";
import type { Alert, AlertFilters, NotificationPreference, Threshold } from "../features/alerts/types";
import type { HouseCreate, Room, Device, DevicePatch } from "../features/devices/types";
import type { RetentionPolicy } from "../features/dataops/types";
import type { User, DashboardSettingsInput } from "../api/apiClient";

let user: User = { id: 1, email: "admin@example.com", full_name: "Demo Admin", role: "admin", house_ids: [1] };
const account = () => String(user.id);
const fail = (message: string, status = 400, error = "validation_error") => HttpResponse.json({ error, message }, { status });
const missing = () => fail("Record not found", 404, "not_found");
const paramsOf = (request: Request) => new URL(request.url).searchParams;
function page<T>(items: T[], request: Request) {
  const q = paramsOf(request); const page = Math.max(1, Number(q.get("page")) || 1); const size = Math.min(100, Math.max(1, Number(q.get("page_size")) || 100));
  return { items: items.slice((page - 1) * size, page * size), total: items.length, page, page_size: size };
}
function audit(action: string, resource: string, house_id: number | null = null) {
  const state = readDemoState();
  state.audit.unshift({ audit_id: nextId(state.audit.map(a => a.audit_id)), actor_user_id: user.id, house_id, action, resource, ts: new Date().toISOString() });
  writeDemoState(state);
}
function allAlerts(): Alert[] {
  let simulated: Alert[] = [];
  try { simulated = JSON.parse(localStorage.getItem("smarthome:demo-alerts") ?? "[]"); } catch { /* malformed legacy data */ }
  const alerts = new Map(demoAlerts.map(a => [a.alert_id, a]));
  [...simulated, ...readDemoState().alerts].forEach(a => { const old = alerts.get(a.alert_id); if (!old || a.version >= old.version) alerts.set(a.alert_id, a); });
  return [...alerts.values()];
}
function filteredAlerts(request: Request): Alert[] {
  const q = paramsOf(request);
  const filtered = allAlerts().filter(a => {
    const text = `${a.alert_id} ${a.sound_type} ${a.alert_category} ${a.house_id} ${a.room_id}`.toLowerCase();
    return ["house_id", "severity", "state", "sound_type"].every(key => !q.get(key) || String(a[key as keyof Alert]) === q.get(key))
      && (!q.get("category") || a.alert_category === q.get("category"))
      && (!q.get("q") || text.includes(q.get("q")!.trim().toLowerCase()))
      && (!q.get("from") || (a.created_at ?? "") >= q.get("from")!)
      && (!q.get("to") || (a.created_at ?? "").slice(0, 10) <= q.get("to")!)
      && (!q.get("min_confidence") || (a.confidence ?? 0) >= Number(q.get("min_confidence")))
      && (!q.get("max_confidence") || (a.confidence ?? 0) <= Number(q.get("max_confidence")))
      && (!q.get("updated_since") || (a.updated_at ?? "") >= q.get("updated_since")!);
  });
  return filtered.sort((a, b) => (q.get("sort") === "oldest" ? 1 : -1) * (a.created_at ?? "").localeCompare(b.created_at ?? ""));
}
function safeAlert(alert: Alert) { if (user.role === "admin") return alert; const { confidence: _confidence, ...safe } = alert; return safe; }

export const handlers = [
  http.post("*/api/auth/login", async ({ request }) => {
    const body = await request.json() as { email: string }; const email = body.email.trim().toLowerCase();
    const state = readDemoState(); const admin = email.startsWith("admin@");
    user = state.profiles[email] ?? { id: admin ? 1 : 2, email, full_name: admin ? "Demo Admin" : "Demo Owner", role: admin ? "admin" : "owner", house_ids: [1] };
    return HttpResponse.json({ access_token: "demo-token", user });
  }),
  http.post("*/api/auth/signup", async ({ request }) => {
    const body = await request.json() as { email: string; full_name: string }; const state = readDemoState();
    const profile: User = { ...body, email: body.email.toLowerCase(), id: nextId([2, ...Object.values(state.profiles).map(p => p.id)]), role: "owner", house_ids: [] };
    state.profiles[profile.email] = profile; writeDemoState(state); return HttpResponse.json(profile, { status: 201 });
  }),
  http.post("*/api/auth/refresh", () => HttpResponse.json({ access_token: "demo-token" })),
  http.post("*/api/auth/logout", () => new HttpResponse(null, { status: 204 })),
  http.get("*/api/users/me", () => HttpResponse.json(user)),
  http.put("*/api/users/me", async ({ request }) => {
    const body = await request.json() as Pick<User, "email" | "full_name" | "phone">; const state = readDemoState(); const oldEmail = user.email;
    user = { ...user, ...body }; delete state.profiles[oldEmail]; state.profiles[user.email.toLowerCase()] = user; writeDemoState(state); audit("profile.updated", "Profile"); return HttpResponse.json(user);
  }),
  // Specific export route must precede the dynamic alert-id route.
  http.get("*/api/alerts/export", ({ request }) => {
    const alerts = filteredAlerts(request); const pdf = paramsOf(request).get("format") === "pdf";
    const content = pdf ? alertsPdf(alerts) : toCsv(alerts.map(a => ({ alert_id: a.alert_id, sound_type: a.sound_type ?? "", state: a.state })), ["alert_id", "sound_type", "state"]);
    return new HttpResponse(content, { headers: { "Content-Type": pdf ? "application/pdf" : "text/csv", "Content-Disposition": `attachment; filename="alerts.${pdf ? "pdf" : "csv"}"` } });
  }),
  http.get("*/api/alerts", ({ request }) => HttpResponse.json(page(filteredAlerts(request).map(safeAlert), request))),
  http.get("*/api/alerts/:id", ({ params }) => {
    const alert = allAlerts().find(a => a.alert_id === Number(params.id));
    return alert ? HttpResponse.json({ ...safeAlert(alert), history: [], deliveries: [] }) : missing();
  }),
  http.patch("*/api/alerts/:id/state", async ({ params, request }) => {
    const body = await request.json() as { to_state: Alert["state"]; expected_state?: string }; const old = allAlerts().find(a => a.alert_id === Number(params.id));
    if (!old) return missing();
    if (request.headers.get("x-demo-conflict") === "true" || body.expected_state && body.expected_state !== old.state) return HttpResponse.json({ error: "state_conflict", message: "State changed", details: { current_state: old.state, last_actor: "another-admin@example.com" } }, { status: 409 });
    const updated = { ...old, state: body.to_state, version: old.version + 1, updated_at: new Date().toISOString() }; const state = readDemoState();
    state.alerts = [...state.alerts.filter(a => a.alert_id !== old.alert_id), updated]; writeDemoState(state);
    localStorage.setItem("smarthome:demo-state", JSON.stringify({ alert_id: updated.alert_id, house_id: updated.house_id, state: updated.state }));
    audit("alert.updated", `Alert ${old.alert_id}`, old.house_id); return HttpResponse.json(safeAlert(updated));
  }),
  http.post("*/api/alerts/:id/resend", () => HttpResponse.json({ accepted: true })),
  http.get("*/api/stats/alerts", () => {
    const alerts = allAlerts(); const count = (key: "severity" | "alert_category" | "state") => alerts.reduce<Record<string, number>>((result, a) => { result[a[key]] = (result[a[key]] ?? 0) + 1; return result; }, {});
    return HttpResponse.json({ total: alerts.length, by_severity: count("severity"), by_category: count("alert_category"), by_state: count("state") });
  }),
  http.get("*/api/stats/false-alerts", () => HttpResponse.json({ items: [] })),
  http.get("*/api/houses", ({ request }) => HttpResponse.json(page(readDemoState().houses, request))),
  http.post("*/api/houses", async ({ request }) => {
    const body = await request.json() as HouseCreate; const state = readDemoState();
    if (!body.address_line?.trim() || !body.postal_code?.trim()) return fail("Address and postal code are required.");
    if (state.houses.some(h => h.address_line === body.address_line && h.postal_code === body.postal_code)) return fail("A house at that address is already registered.", 409, "duplicate_address");
    const house = { city: null, state: null, latitude: null, longitude: null, ...body, house_id: nextId(state.houses.map(h => h.house_id)), status: "active" as const };
    state.houses.push(house); writeDemoState(state); audit("house.created", body.address_line, house.house_id); return HttpResponse.json({ ...house, owner: null }, { status: 201 });
  }),
  http.get("*/api/rooms", ({ request }) => HttpResponse.json(page(readDemoState().rooms.filter(r => !paramsOf(request).get("house_id") || r.house_id === Number(paramsOf(request).get("house_id"))), request))),
  http.post("*/api/rooms", async ({ request }) => {
    const body = await request.json() as Omit<Room, "room_id">; const state = readDemoState();
    if (!state.houses.some(h => h.house_id === body.house_id)) return missing();
    if (state.rooms.some(r => r.house_id === body.house_id && r.label === body.label)) return fail("A room with that name already exists.", 409, "duplicate_label");
    const room = { ...body, room_id: nextId(state.rooms.map(r => r.room_id)) }; state.rooms.push(room); writeDemoState(state); return HttpResponse.json(room, { status: 201 });
  }),
  http.patch("*/api/rooms/:id", async ({ params, request }) => {
    const state = readDemoState(); const room = state.rooms.find(r => r.room_id === Number(params.id)); if (!room) return missing(); Object.assign(room, await request.json()); writeDemoState(state); return HttpResponse.json(room);
  }),
  http.get("*/api/devices", ({ request }) => {
    const q = paramsOf(request); const devices = readDemoState().devices.filter(d => (!q.get("house_id") || d.house_id === Number(q.get("house_id"))) && (!q.get("room_id") || d.room_id === Number(q.get("room_id"))) && (!q.get("status") || d.status === q.get("status")) && (!q.get("connectivity") || d.conn_state === q.get("connectivity")));
    return HttpResponse.json(page(devices, request));
  }),
  http.post("*/api/devices", async ({ request }) => {
    const body = await request.json() as Pick<Device, "room_id" | "serial_no" | "device_type" | "label">; const state = readDemoState(); const room = state.rooms.find(r => r.room_id === body.room_id);
    if (!room) return missing(); if (!body.serial_no?.trim()) return fail("Serial number is required.");
    if (state.devices.some(d => d.serial_no === body.serial_no)) return fail("That serial number is already registered.", 409, "duplicate_serial");
    const device: Device = { ...body, label: body.label ?? null, device_id: nextId(state.devices.map(d => d.device_id)), house_id: room.house_id, status: "enabled", conn_state: "offline", wifi_rssi: null, last_heartbeat: null, config_version: 1 };
    state.devices.push(device); writeDemoState(state); audit("device.created", body.serial_no, room.house_id); return HttpResponse.json({ ...device, api_key: `dk_demo_${crypto.randomUUID()}` }, { status: 201 });
  }),
  http.patch("*/api/devices/:id", async ({ params, request }) => {
    const body = await request.json() as DevicePatch; const state = readDemoState(); const device = state.devices.find(d => d.device_id === Number(params.id)); if (!device) return missing();
    if (user.role !== "admin" && Object.keys(body).some(k => k !== "status")) return fail("Owners may only change listening status.", 403, "scope_violation");
    if (body.threshold !== undefined && body.threshold !== null && (body.threshold < .5 || body.threshold > .99)) return fail("Threshold must be between 0.50 and 0.99.", 422, "invalid_threshold");
    Object.assign(device, body, { config_version: device.config_version + 1 }); writeDemoState(state); audit("device.updated", device.serial_no, device.house_id); return HttpResponse.json(device);
  }),
  http.delete("*/api/devices/:id", ({ params }) => { const state = readDemoState(); state.devices = state.devices.filter(d => d.device_id !== Number(params.id)); writeDemoState(state); return new HttpResponse(null, { status: 204 }); }),
  http.post("*/api/devices/:id/rotate-key", ({ params }) => { const device = readDemoState().devices.find(d => d.device_id === Number(params.id)); return device ? HttpResponse.json({ ...device, api_key: `dk_demo_${crypto.randomUUID()}` }) : missing(); }),
  http.post("*/api/auth/device-token", () => HttpResponse.json({ access_token: "device-token", expires_in: 900 })),
  http.post("*/api/devices/:id/heartbeat", ({ params }) => { const state = readDemoState(); const device = state.devices.find(d => d.device_id === Number(params.id)); if (!device) return missing(); device.conn_state = "online"; device.last_heartbeat = new Date().toISOString(); writeDemoState(state); return HttpResponse.json({ ...device, commands: [], config: {} }); }),
  http.post("*/api/devices/:id/command", async ({ request }) => HttpResponse.json({ command_id: Date.now(), ...await request.json() as object, status: "pending" }, { status: 202 })),
  ...(["disable", "enable"] as const).map(action => http.post(`*/api/houses/:id/${action}`, ({ params }) => {
    const state = readDemoState(); const house = state.houses.find(h => h.house_id === Number(params.id)); if (!house) return missing(); house.status = action === "disable" ? "disabled" : "active"; const devices = state.devices.filter(d => d.house_id === house.house_id); devices.forEach(d => { d.status = action === "disable" ? "disabled" : "enabled"; d.config_version++; }); writeDemoState(state); return HttpResponse.json({ ...house, devices_updated: devices.length, at: new Date().toISOString() });
  })),
  http.get("*/api/admin/audit", ({ request }) => {
    const items = readDemoState().audit;
    if (paramsOf(request).get("export") === "csv") return new HttpResponse(toCsv(items.map(a => ({ id: a.audit_id, action: a.action, resource: a.resource ?? "", time: a.ts ?? "" })), ["id", "action", "resource", "time"]), { headers: { "Content-Type": "text/csv" } });
    return HttpResponse.json(page(items, request));
  }),
  http.get("*/api/admin/data/health", () => { const events = readDemoState().events; return HttpResponse.json({ postgres: "ok", mongo: "ok", s3: "ok", sqs: { visible: events.filter(e => e.processing_state === "queued").length, in_flight: 0 }, dlq: { visible: events.filter(e => e.processing_state === "failed").length }, backups: { rds_snapshot_age_h: null, mongo_dump_age_d: null }, unprocessed_events: events.filter(e => e.processing_state !== "scored").length }); }),
  http.get("*/api/admin/events", ({ request }) => { const filter = paramsOf(request).get("state"); return HttpResponse.json(page(readDemoState().events.filter(e => !filter || e.processing_state === filter), request)); }),
  http.post("*/api/admin/events/:id/retry", ({ params }) => { const state = readDemoState(); const event = state.events.find(e => e.event_id === Number(params.id)); if (!event) return missing(); if (event.processing_state === "scored") return fail("Already scored", 409, "already_scored"); event.processing_state = "queued"; event.retry_count++; writeDemoState(state); audit("event.retried", `Event ${event.event_id}`, event.house_id); return HttpResponse.json(event); }),
  http.get("*/api/admin/inference-logs", () => HttpResponse.json({ items: [], total: 0 })),
  http.get("*/api/admin/retention", () => HttpResponse.json(readDemoState().retention)),
  http.put("*/api/admin/retention", async ({ request }) => { const body = await request.json() as RetentionPolicy; const error = retentionError(body); if (error) return fail(error); const state = readDemoState(); state.retention = body; writeDemoState(state); audit("retention.updated", "Retention policy"); return HttpResponse.json(body); }),
  http.get("*/api/users/me/dashboard-settings", () => HttpResponse.json({ ...(readDemoState().settings[account()] ?? defaultDashboardSettings), updated_at: null })),
  http.put("*/api/users/me/dashboard-settings", async ({ request }) => { const body = await request.json() as DashboardSettingsInput; const state = readDemoState(); state.settings[account()] = body; writeDemoState(state); return HttpResponse.json({ ...body, updated_at: new Date().toISOString() }); }),
  http.get("*/api/users/me/saved-views", () => HttpResponse.json({ views: readDemoState().savedViews[account()] ?? [] })),
  http.put("*/api/users/me/saved-views", async ({ request }) => { const body = await request.json() as { views: AlertFilters[] }; const state = readDemoState(); state.savedViews[account()] = body.views; writeDemoState(state); return HttpResponse.json(body); }),
  http.get("*/api/notification-prefs", ({ request }) => { const house_id = Number(paramsOf(request).get("house_id")); return HttpResponse.json({ house_id, items: readDemoState().preferences[`${account()}:${house_id}`] ?? [{ alert_category: "safety", email: true, sms: true, min_severity: "high" }] }); }),
  http.put("*/api/notification-prefs", async ({ request }) => { const items = await request.json() as NotificationPreference[]; const house_id = Number(paramsOf(request).get("house_id")); const state = readDemoState(); state.preferences[`${account()}:${house_id}`] = items; writeDemoState(state); return HttpResponse.json({ house_id, items }); }),
  http.get("*/api/admin/thresholds", () => HttpResponse.json({ items: readDemoState().thresholds })),
  http.put("*/api/admin/thresholds", async ({ request }) => { const body = await request.json() as Threshold; if (!Number.isFinite(body.threshold) || body.threshold < .5 || body.threshold > .99) return fail("Threshold must be between 0.50 and 0.99.", 422); const state = readDemoState(); const old = state.thresholds.find(t => t.scope === body.scope && t.scope_id === body.scope_id && t.sound_type === body.sound_type); const saved = { ...body, id: old?.id ?? nextId(state.thresholds.map(t => t.id)) }; state.thresholds = [...state.thresholds.filter(t => t.id !== saved.id), saved]; writeDemoState(state); return HttpResponse.json(saved); }),
];
