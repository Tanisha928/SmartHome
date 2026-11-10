/** Pure helpers for the device screens (unit-tested in logic.test.ts). */

import type { Device, House, Room } from "./types";

export type FleetStats = { total: number; online: number; offline: number; disabled: number };

/** Disabled wins over connectivity: a disabled device that still heartbeats counts as disabled. */
export function fleetStats(devices: Device[]): FleetStats {
  const stats: FleetStats = { total: devices.length, online: 0, offline: 0, disabled: 0 };
  for (const d of devices) {
    if (d.status === "disabled") stats.disabled++;
    else if (d.conn_state === "online") stats.online++;
    else stats.offline++;
  }
  return stats;
}

export type DeviceHealth = "online" | "offline" | "disabled";

export function deviceHealth(d: Device): DeviceHealth {
  if (d.status === "disabled") return "disabled";
  return d.conn_state === "online" ? "online" : "offline";
}

export type HouseNode = {
  house: House;
  rooms: Array<{ room: Room; devices: Device[] }>;
  unassigned: Device[];
  deviceCount: number;
};

export function buildHouseTree(houses: House[], rooms: Room[], devices: Device[]): HouseNode[] {
  return houses.map((house) => {
    const houseRooms = rooms.filter((r) => r.house_id === house.house_id);
    const houseDevices = devices.filter((d) => d.house_id === house.house_id);
    const roomIds = new Set(houseRooms.map((r) => r.room_id));
    return {
      house,
      rooms: houseRooms.map((room) => ({
        room,
        devices: houseDevices.filter((d) => d.room_id === room.room_id),
      })),
      unassigned: houseDevices.filter((d) => !roomIds.has(d.room_id)),
      deviceCount: houseDevices.length,
    };
  });
}

/**
 * Search box for A4: "12" matches house 12 or device 12; text matches address, serial, label.
 * A matching house keeps all its rooms; a matching device keeps only its branch.
 */
export function filterTree(tree: HouseNode[], q: string): HouseNode[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return tree;
  const asId = /^#?\d+$/.test(needle) ? Number(needle.replace("#", "")) : null;
  const houseMatches = (h: House) =>
    h.house_id === asId ||
    [h.address_line, h.city, h.postal_code].some((v) => v?.toLowerCase().includes(needle));
  const deviceMatches = (d: Device) =>
    d.device_id === asId ||
    d.serial_no.toLowerCase().includes(needle) ||
    (d.label ?? "").toLowerCase().includes(needle);

  const out: HouseNode[] = [];
  for (const node of tree) {
    if (houseMatches(node.house)) {
      out.push(node);
      continue;
    }
    const rooms = node.rooms
      .map((r) => ({ room: r.room, devices: r.devices.filter(deviceMatches) }))
      .filter((r) => r.devices.length > 0);
    const unassigned = node.unassigned.filter(deviceMatches);
    if (rooms.length || unassigned.length) {
      out.push({ ...node, rooms, unassigned });
    }
  }
  return out;
}

export function heartbeatAge(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "never";
  const sec = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

/** Wi-Fi signal in words (owners never see raw dBm). */
export function signalLabel(rssi: number | null): string {
  if (rssi === null) return "Unknown";
  if (rssi >= -60) return "Strong";
  if (rssi >= -70) return "Good";
  if (rssi >= -80) return "Weak";
  return "Very weak";
}

export function houseLabel(h: House): string {
  return [h.address_line, h.city].filter(Boolean).join(", ") || `House ${h.house_id}`;
}

export const ROOM_TYPE_LABELS = {
  kitchen: "Kitchen",
  living: "Living room",
  bedroom: "Bedroom",
  bath: "Bathroom",
  other: "Other",
} as const;
