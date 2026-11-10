/** Device-manager API helpers. Swap `request` for Mithil's shared apiClient once it lands. */

import type {
  ApiError,
  Device,
  DeviceCommand,
  DevicePatch,
  DeviceType,
  DeviceWithKey,
  House,
  HouseCascadeResult,
  HouseCreate,
  HouseCreated,
  Page,
  Room,
  RoomType,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("X-Correlation-Id", crypto.randomUUID());
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = sessionStorage.getItem("access_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const err = new Error(body.message ?? resp.statusText) as ApiError;
    err.status = resp.status;
    err.error = body.error;
    err.details = body.details;
    err.correlationId = resp.headers.get("X-Correlation-Id");
    throw err;
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

function query(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const devicesApi = {
  // houses (persistence/api/houses.py + iot cascade)
  listHouses: () => request<Page<House>>("/api/houses?page_size=100"),
  createHouse: (body: HouseCreate) => request<HouseCreated>("/api/houses", json("POST", body)),
  disableHouse: (id: number) =>
    request<HouseCascadeResult>(`/api/houses/${id}/disable`, { method: "POST" }),
  enableHouse: (id: number) =>
    request<HouseCascadeResult>(`/api/houses/${id}/enable`, { method: "POST" }),

  // rooms
  listRooms: (houseId?: number) =>
    request<{ items: Room[]; total: number }>(`/api/rooms${query({ house_id: houseId })}`),
  createRoom: (body: { house_id: number; room_type: RoomType; label: string }) =>
    request<Room>("/api/rooms", json("POST", body)),
  updateRoom: (id: number, body: { label?: string; room_type?: RoomType }) =>
    request<Room>(`/api/rooms/${id}`, json("PATCH", body)),

  // devices
  listDevices: (filters: {
    house_id?: number;
    room_id?: number;
    status?: string;
    connectivity?: string;
    page?: number;
    page_size?: number;
  } = {}) => request<Page<Device>>(`/api/devices${query({ page_size: 100, ...filters })}`),
  createDevice: (body: {
    room_id: number;
    device_type: DeviceType;
    serial_no: string;
    label?: string;
  }) => request<DeviceWithKey>("/api/devices", json("POST", body)),
  updateDevice: (id: number, body: DevicePatch) =>
    request<Device>(`/api/devices/${id}`, json("PATCH", body)),
  removeDevice: (id: number) => request<void>(`/api/devices/${id}`, { method: "DELETE" }),
  rotateKey: (id: number) =>
    request<DeviceWithKey>(`/api/devices/${id}/rotate-key`, { method: "POST" }),
  sendCommand: (id: number, command: DeviceCommand) =>
    request<{ command_id: number; command: string; status: string }>(
      `/api/devices/${id}/command`,
      json("POST", { command }),
    ),
};

/** Page through every device (fleet view). */
export async function listAllDevices(filters: { house_id?: number } = {}): Promise<Device[]> {
  const out: Device[] = [];
  for (let page = 1; ; page++) {
    const data = await devicesApi.listDevices({ ...filters, page, page_size: 100 });
    out.push(...data.items);
    if (out.length >= data.total || data.items.length === 0) return out;
  }
}

export function errorText(err: unknown): string {
  const e = err as Partial<ApiError>;
  const messages: Record<string, string> = {
    duplicate_serial: "That serial number is already registered.",
    duplicate_label: "A room with that name already exists in this house.",
    command_pending: "That command is already waiting for the device.",
    invalid_threshold: "Threshold must be between 0.50 and 0.99.",
    scope_violation: "You don't have access to that house.",
    duplicate_address: "A house at that address is already registered.",
  };
  const code = e.error ?? (e.details?.error as string | undefined);
  const text = (code && messages[code]) || e.message || "Something went wrong.";
  return e.correlationId ? `${text} (ref ${e.correlationId})` : text;
}
