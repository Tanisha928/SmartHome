import { describe, expect, it } from "vitest";
import {
  buildHouseTree,
  deviceHealth,
  filterTree,
  fleetStats,
  heartbeatAge,
  signalLabel,
} from "./logic";
import type { Device, House, Room } from "./types";

const house = (id: number, address: string): House => ({
  house_id: id,
  address_line: address,
  city: "Seattle",
  state: "WA",
  postal_code: `9810${id}`,
  latitude: null,
  longitude: null,
  timezone: "UTC",
  status: "active",
});

const room = (id: number, houseId: number, label: string): Room => ({
  room_id: id,
  house_id: houseId,
  room_type: "living",
  label,
});

const device = (id: number, houseId: number, roomId: number, extra: Partial<Device> = {}): Device => ({
  device_id: id,
  house_id: houseId,
  room_id: roomId,
  device_type: "audio",
  serial_no: `SN-${id}`,
  label: null,
  status: "enabled",
  conn_state: "online",
  wifi_rssi: -50,
  last_heartbeat: null,
  config_version: 1,
  ...extra,
});

describe("fleetStats", () => {
  it("counts disabled before connectivity", () => {
    const stats = fleetStats([
      device(1, 1, 1),
      device(2, 1, 1, { conn_state: "offline" }),
      device(3, 1, 1, { status: "disabled", conn_state: "online" }),
      device(4, 1, 1, { status: "disabled", conn_state: "offline" }),
    ]);
    expect(stats).toEqual({ total: 4, online: 1, offline: 1, disabled: 2 });
  });

  it("maps health per device", () => {
    expect(deviceHealth(device(1, 1, 1, { status: "disabled" }))).toBe("disabled");
    expect(deviceHealth(device(1, 1, 1, { conn_state: "offline" }))).toBe("offline");
  });
});

describe("house tree", () => {
  const houses = [house(1, "1 Pine St"), house(12, "12 Oak Ave")];
  const rooms = [room(10, 1, "Living"), room(11, 1, "Kitchen"), room(20, 12, "Hall")];
  const devices = [
    device(100, 1, 10),
    device(101, 1, 11, { label: "Fridge mic" }),
    device(200, 12, 20),
  ];
  const tree = buildHouseTree(houses, rooms, devices);

  it("groups devices under rooms and counts them", () => {
    expect(tree[0].deviceCount).toBe(2);
    expect(tree[0].rooms.map((r) => r.devices.map((d) => d.device_id))).toEqual([[100], [101]]);
    expect(tree[1].deviceCount).toBe(1);
  });

  it("searches by house id and keeps the whole house", () => {
    const out = filterTree(tree, "12");
    expect(out.map((n) => n.house.house_id)).toEqual([12]);
    expect(out[0].rooms).toHaveLength(1);
  });

  it("searches by device id and keeps only that branch", () => {
    const out = filterTree(tree, "#101");
    expect(out).toHaveLength(1);
    expect(out[0].rooms.map((r) => r.room.label)).toEqual(["Kitchen"]);
  });

  it("searches serials, labels and addresses case-insensitively", () => {
    expect(filterTree(tree, "fridge")[0].rooms[0].devices[0].device_id).toBe(101);
    expect(filterTree(tree, "sn-200")[0].house.house_id).toBe(12);
    expect(filterTree(tree, "oak")[0].house.house_id).toBe(12);
    expect(filterTree(tree, "nothing-matches")).toEqual([]);
    expect(filterTree(tree, "  ")).toBe(tree);
  });
});

describe("formatting", () => {
  const now = Date.parse("2026-11-10T12:00:00Z");
  it("heartbeatAge", () => {
    expect(heartbeatAge(null, now)).toBe("never");
    expect(heartbeatAge("2026-11-10T11:59:30Z", now)).toBe("30s ago");
    expect(heartbeatAge("2026-11-10T11:50:00Z", now)).toBe("10 min ago");
    expect(heartbeatAge("2026-11-10T09:00:00Z", now)).toBe("3 h ago");
    expect(heartbeatAge("2026-11-05T12:00:00Z", now)).toBe("5 d ago");
  });
  it("signalLabel", () => {
    expect(signalLabel(-45)).toBe("Strong");
    expect(signalLabel(-65)).toBe("Good");
    expect(signalLabel(-75)).toBe("Weak");
    expect(signalLabel(-90)).toBe("Very weak");
    expect(signalLabel(null)).toBe("Unknown");
  });
});

describe("applyDeviceUpdate", () => {
  it("merges a pushed update into the matching device only", async () => {
    const { applyDeviceUpdate } = await import("./live");
    const list = [device(1, 1, 1), device(2, 1, 1)];
    const next = applyDeviceUpdate(list, { device_id: 2, status: "disabled", conn_state: "offline" });
    expect(next[1]).toMatchObject({ device_id: 2, status: "disabled", conn_state: "offline", serial_no: "SN-2" });
    expect(next[0]).toBe(list[0]);
  });

  it("returns the same list for unknown devices", async () => {
    const { applyDeviceUpdate } = await import("./live");
    const list = [device(1, 1, 1)];
    expect(applyDeviceUpdate(list, { device_id: 99, status: "disabled" })).toBe(list);
  });
});
