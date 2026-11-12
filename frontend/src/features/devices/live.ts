/** Live `device.updated` events (FR-4: enable/disable visible within 5 s). */

import { useLiveEvents } from "../../api/liveEvents";
import type { Device } from "./types";

export type DeviceUpdate = Pick<Device, "device_id"> &
  Partial<Pick<Device, "room_id" | "label" | "status" | "conn_state" | "wifi_rssi" | "last_heartbeat">>;

/** Merge one pushed update into a device list; unknown devices are ignored (a reload adds them). */
export function applyDeviceUpdate(devices: Device[], update: DeviceUpdate): Device[] {
  let changed = false;
  const next = devices.map((d) => {
    if (d.device_id !== update.device_id) return d;
    changed = true;
    return { ...d, ...update };
  });
  return changed ? next : devices;
}

/** Subscribe to `device.updated` for one house, or every house (admins, `houseId` undefined). */
export function useDeviceEvents(houseId: number | undefined, onUpdate: (update: DeviceUpdate) => void) {
  useLiveEvents(houseId, (event) => {
    if (event.type === "device.updated" && event.device) onUpdate(event.device as DeviceUpdate);
  });
}
