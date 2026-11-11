import { http, HttpResponse } from "msw";
import { demoAlerts, demoPage, demoStats } from "./fixtures";
export const handlers = [
  http.post("*/api/auth/login", async ({ request }) => { const body = await request.json() as { email?: string }; const owner = body.email?.includes("owner"); return HttpResponse.json({ access_token: "demo-token", user: { id: owner ? 2 : 1, email: body.email, full_name: owner ? "Demo Owner" : "Demo Admin", role: owner ? "owner" : "admin", house_ids: [1] } }); }),
  http.post("*/api/auth/signup", () => HttpResponse.json({ id: 2, email: "owner@example.com", full_name: "Demo Owner", role: "owner", house_ids: [] }, { status: 201 })),
  http.get("*/api/users/me", () => HttpResponse.json({ id: 1, email: "admin@example.com", full_name: "Demo Admin", role: "admin", house_ids: [1] })),
  http.get("*/api/alerts", () => HttpResponse.json(demoPage)),
  http.get("*/api/stats/alerts", () => HttpResponse.json(demoStats)),
  http.get("*/api/stats/false-alerts", () => HttpResponse.json({ items: [] })),
  http.get("*/api/devices", () => HttpResponse.json({ items: [{ device_id: 7, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo", label: "Kitchen monitor", status: "enabled", conn_state: "online", wifi_rssi: -55, last_heartbeat: new Date().toISOString(), config_version: 1 }], total: 1, page: 1, page_size: 100 })),
  http.get("*/api/houses", () => HttpResponse.json({ items: [{ house_id: 1, address_line: "1 Demo Way", city: "Seattle", state: "WA", postal_code: "98101", latitude: 47.6062, longitude: -122.3321, timezone: "UTC", status: "active" }], total: 1, page: 1, page_size: 100 })),
  http.get("*/api/rooms", () => HttpResponse.json({ items: [{ room_id: 1, house_id: 1, room_type: "kitchen", label: "Kitchen" }], total: 1 })),
  http.patch("*/api/devices/:id", () => HttpResponse.json({ device_id: 7, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo", label: "Kitchen monitor", status: "disabled", conn_state: "online", wifi_rssi: -55, last_heartbeat: new Date().toISOString(), config_version: 1 })),
  http.post("*/api/devices", () => HttpResponse.json({ device_id: 8, house_id: 1, room_id: 1, device_type: "audio", serial_no: "demo-new", label: "Demo sensor", status: "enabled", conn_state: "offline", wifi_rssi: null, last_heartbeat: null, config_version: 1, api_key: "dk_demo_once" }, { status: 201 })),
  http.post("*/api/auth/device-token", () => HttpResponse.json({ access_token: "device-token", expires_in: 900 })),
  http.post("*/api/devices/7/heartbeat", () => HttpResponse.json({ device_id: 7, conn_state: "online", commands: [], config: {} })),
  http.get("*/api/admin/audit", () => HttpResponse.json({ items: [] })),
  http.get("*/api/users/me/saved-views", () => HttpResponse.json({ views: [] })),
  http.put("*/api/users/me/saved-views", () => HttpResponse.json({ views: [] })),
  http.patch("*/api/alerts/:id/state", () => HttpResponse.json(demoAlerts[0])),
];
