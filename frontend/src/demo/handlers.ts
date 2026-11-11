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
  http.get("*/api/users/me/saved-views", () => HttpResponse.json({ views: [] })),
  http.put("*/api/users/me/saved-views", () => HttpResponse.json({ views: [] })),
  http.patch("*/api/alerts/:id/state", () => HttpResponse.json(demoAlerts[0])),
];
