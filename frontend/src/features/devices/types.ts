export type RoomType = "kitchen" | "living" | "bedroom" | "bath" | "other";
export type DeviceType = "audio" | "camera";
export type DeviceStatus = "enabled" | "disabled";
export type ConnState = "online" | "offline";
export type DeviceCommand = "enable" | "disable" | "reboot";

export type House = {
  house_id: number;
  address_line: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  timezone: string;
  status: "active" | "disabled";
};

export type HouseCreate = {
  address_line: string;
  city?: string;
  state?: string;
  postal_code: string;
  latitude?: number;
  longitude?: number;
  timezone: string;
  owner_email?: string;
};

export type HouseCreated = House & {
  owner: { user_id: number; email: string; must_reset: boolean; temp_password?: string } | null;
};

export type Room = {
  room_id: number;
  house_id: number;
  room_type: RoomType;
  label: string;
};

export type Device = {
  device_id: number;
  house_id: number;
  room_id: number;
  device_type: DeviceType;
  serial_no: string;
  label: string | null;
  status: DeviceStatus;
  conn_state: ConnState;
  wifi_rssi: number | null;
  last_heartbeat: string | null;
  config_version: number;
  // admin-only fields
  threshold?: number | null;
  api_key_prefix?: string | null;
  key_revoked_at?: string | null;
};

/** Returned by register / rotate-key only. The raw key is never retrievable again. */
export type DeviceWithKey = Device & { api_key: string };

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type DevicePatch = Partial<Pick<Device, "status" | "label" | "threshold" | "room_id">>;

export type HouseCascadeResult = {
  house_id: number;
  status: "active" | "disabled";
  devices_updated: number;
  at: string;
};

export type ApiError = Error & {
  status: number;
  error?: string;
  details?: Record<string, unknown>;
  correlationId?: string | null;
};
