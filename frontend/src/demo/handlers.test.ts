// @vitest-environment jsdom
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { setupServer } from "msw/node";
import { handlers } from "./handlers";
import { alertsPdf } from "./exports";
import { demoAlerts } from "./fixtures";

const server = setupServer(...handlers);
const storage = vi.hoisted(() => {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) } });
  return values;
});
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterAll(() => { server.close(); vi.unstubAllGlobals(); });
const send = (path: string, method = "GET", body?: unknown) => fetch(`http://localhost${path}`, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
const json = async (path: string, method = "GET", body?: unknown) => { const response = await send(path, method, body); expect(response.ok).toBe(true); return response.json(); };
beforeEach(async () => { storage.clear(); await json("/api/auth/login", "POST", { email: "admin@example.com" }); });

describe("presentation API regressions", () => {
  it("registers houses and rooms, preserves submitted values, rejects duplicates", async () => {
    const body = { address_line: "48 Acceptance Lane", postal_code: "98101", timezone: "UTC" };
    const house = await json("/api/houses", "POST", body);
    const room = await json("/api/rooms", "POST", { house_id: house.house_id, room_type: "living", label: "Reading room" });
    expect((await json("/api/houses")).items).toContainEqual(expect.objectContaining(body));
    expect((await json(`/api/rooms?house_id=${house.house_id}`)).items).toEqual([room]);
    expect((await send("/api/houses", "POST", body)).status).toBe(409);
  });

  it("retains device registration, updates, capture state and removal without exposing raw keys", async () => {
    const device = await json("/api/devices", "POST", { room_id: 1, serial_no: "test-device", device_type: "audio", label: "New sensor" });
    expect(device.api_key).toMatch(/^dk_demo_/);
    expect(device.conn_state).toBe("offline");
    await json(`/api/devices/${device.device_id}`, "PATCH", { label: "Renamed sensor", status: "disabled" });
    const saved = (await json("/api/devices")).items.find((d: { device_id: number }) => d.device_id === device.device_id);
    expect(saved).toMatchObject({ serial_no: "test-device", label: "Renamed sensor", status: "disabled" });
    expect(saved).not.toHaveProperty("api_key");
    expect((await send(`/api/devices/${device.device_id}`, "DELETE")).status).toBe(204);
    expect((await json("/api/devices")).total).toBe(1);
  });

  it("reflects house enable/disable and heartbeat transitions in later reads", async () => {
    await json("/api/houses/1/disable", "POST");
    expect((await json("/api/houses")).items[0].status).toBe("disabled");
    expect((await json("/api/devices")).items[0].status).toBe("disabled");
    await json("/api/houses/1/enable", "POST");
    const d = await json("/api/devices", "POST", { room_id: 1, serial_no: "heartbeat-test", device_type: "audio" });
    await json(`/api/devices/${d.device_id}/heartbeat`, "POST");
    expect((await json(`/api/devices?connectivity=online`)).items).toContainEqual(expect.objectContaining({ device_id: d.device_id, conn_state: "online" }));
  });

  it("persists profile changes across later reads and a new sign-in", async () => {
    await json("/api/auth/login", "POST", { email: "owner@example.com" });
    await json("/api/users/me", "PUT", { full_name: "Updated Owner", phone: "+15551234567", email: "renamed@example.com" });
    expect(await json("/api/users/me")).toMatchObject({ full_name: "Updated Owner", phone: "+15551234567" });
    const result = await json("/api/auth/login", "POST", { email: "renamed@example.com" });
    expect(result.user.full_name).toBe("Updated Owner");
  });

  it("persists notification preferences, scoped by user and house", async () => {
    const items = [{ alert_category: "emergency", email: true, sms: false, min_severity: "critical" }];
    await json("/api/auth/login", "POST", { email: "owner@example.com" });
    await json("/api/notification-prefs?house_id=1", "PUT", items);
    expect((await json("/api/notification-prefs?house_id=1")).items).toEqual(items);
    expect((await json("/api/notification-prefs?house_id=2")).items).not.toEqual(items);
  });

  it("persists threshold overrides and retains their IDs when updated", async () => {
    const body = { scope: "global", scope_id: null, sound_type: "glass_break", threshold: .86 };
    const first = await json("/api/admin/thresholds", "PUT", body);
    const next = await json("/api/admin/thresholds", "PUT", { ...body, threshold: .9 });
    expect(next.id).toBe(first.id);
    expect((await json("/api/admin/thresholds")).items).toContainEqual(next);
  });

  it("rejects invalid retention and persists valid settings", async () => {
    const body = { clip_expire_days: 40, clip_ia_transition_days: 30, telemetry_ttl_days: 14 };
    expect((await send("/api/admin/retention", "PUT", { ...body, clip_expire_days: 10 })).status).toBe(400);
    expect((await send("/api/admin/retention", "PUT", { ...body, telemetry_ttl_days: -1 })).status).toBe(400);
    await json("/api/admin/retention", "PUT", body);
    expect(await json("/api/admin/retention")).toEqual(body);
  });

  it("filters event states, moves retried events into queued and records audit entries", async () => {
    expect((await json("/api/admin/events?state=scored")).items).toEqual([]);
    expect((await json("/api/admin/events?state=failed")).items).toHaveLength(1);
    await json("/api/admin/events/1/retry", "POST");
    expect((await json("/api/admin/events?state=failed")).items).toEqual([]);
    expect((await json("/api/admin/events?state=queued")).items[0].retry_count).toBe(2);
    expect((await json("/api/admin/audit")).items[0].action).toBe("event.retried");
  });

  it("routes PDF exports before alert IDs and returns a structurally complete PDF", async () => {
    const response = await send("/api/alerts/export?format=pdf");
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("application/pdf");
    const text = await response.text();
    expect(text.startsWith("%PDF-1.4")).toBe(true);
    expect(text).toContain("#101 fall");
  });

  it("generates a valid cross-reference offset and includes all report objects", () => {
    const pdf = alertsPdf(demoAlerts);
    const offset = Number(pdf.match(/startxref\n(\d+)/)?.[1]);
    expect(pdf.slice(offset, offset + 4)).toBe("xref");
    expect(pdf.endsWith("%%EOF\n")).toBe(true);
    expect(pdf).toContain("/BaseFont /Helvetica");
    const multiplePages = alertsPdf(Array.from({ length: 81 }, (_, index) => ({ ...demoAlerts[0], alert_id: 1000 + index })));
    expect(multiplePages).toContain("/Count 3");
    expect(multiplePages).toContain("#1080 fall");
  });

  it("retains alert transitions and strips owner confidence from list/detail responses", async () => {
    await json("/api/alerts/101/state", "PATCH", { to_state: "acknowledged", expected_state: "new" });
    expect((await json("/api/alerts/101")).state).toBe("acknowledged");
    expect((await send("/api/alerts/101/state", "PATCH", { to_state: "resolved", expected_state: "new" })).status).toBe(409);
    await json("/api/auth/login", "POST", { email: "owner@example.com" });
    expect(await json("/api/alerts/101")).not.toHaveProperty("confidence");
    expect((await json("/api/alerts")).items[0]).not.toHaveProperty("confidence");
  });
});
