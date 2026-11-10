// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { errorText } from "./api";
import { DeviceManagement } from "./DeviceManagement";
import { FleetView } from "./FleetView";
import { MyDevices } from "./MyDevices";
import type { Device, House, Room } from "./types";

type Call = { method: string; path: string; body: unknown };

const houses: House[] = [
  {
    house_id: 3,
    address_line: "3 Elm St",
    city: "Tacoma",
    state: "WA",
    postal_code: "98402",
    latitude: null,
    longitude: null,
    timezone: "UTC",
    status: "active",
  },
];
const rooms: Room[] = [{ room_id: 31, house_id: 3, room_type: "kitchen", label: "Kitchen" }];
let devices: Device[];
let calls: Call[];

function respond(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Correlation-Id": "c-test" },
  });
}

function mockFetch(overrides: (call: Call) => Response | undefined = () => undefined) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      const call: Call = {
        method: init?.method ?? "GET",
        path,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      };
      calls.push(call);
      const o = overrides(call);
      if (o) return o;
      if (path.startsWith("/api/houses?")) return respond(200, { items: houses, total: 1, page: 1, page_size: 100 });
      if (path.startsWith("/api/rooms")) return respond(200, { items: rooms, total: rooms.length });
      if (call.method === "GET" && path.startsWith("/api/devices"))
        return respond(200, { items: devices, total: devices.length, page: 1, page_size: 100 });
      if (call.method === "PATCH" && path.startsWith("/api/devices/")) {
        const id = Number(path.split("/")[3]);
        const d = devices.find((x) => x.device_id === id)!;
        return respond(200, { ...d, ...(call.body as object) });
      }
      if (call.method === "POST" && path === "/api/devices")
        return respond(201, { ...devices[0], device_id: 99, serial_no: "SN-NEW", label: null, api_key: "dk_secret_once" });
      if (path.endsWith("/disable")) return respond(200, { house_id: 3, status: "disabled", devices_updated: 2, at: "" });
      return respond(404, { error: "not_found", message: path });
    }),
  );
}

beforeEach(() => {
  calls = [];
  devices = [
    {
      device_id: 501,
      house_id: 3,
      room_id: 31,
      device_type: "audio",
      serial_no: "SN-OWNER-1",
      label: "Kitchen sensor",
      status: "enabled",
      conn_state: "online",
      wifi_rssi: -58,
      last_heartbeat: new Date().toISOString(),
      config_version: 1,
    },
    {
      device_id: 502,
      house_id: 3,
      room_id: 31,
      device_type: "camera",
      serial_no: "SN-OWNER-2",
      label: null,
      status: "disabled",
      conn_state: "offline",
      wifi_rssi: null,
      last_heartbeat: null,
      config_version: 2,
    },
  ];
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("H2 MyDevices", () => {
  it("never shows raw device ids, serials or dBm to owners", async () => {
    mockFetch();
    const { container } = render(<MyDevices houseId={3} />);
    await screen.findByText("Kitchen sensor");
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/501|502/);
    expect(text).not.toContain("SN-OWNER");
    expect(text).not.toContain("dBm");
    expect(text).toContain("Signal strong");
  });

  it("capture toggle sends PATCH {status} only", async () => {
    mockFetch();
    render(<MyDevices houseId={3} />);
    const sw = await screen.findByRole("switch", { name: /Kitchen sensor/ });
    expect(sw.getAttribute("aria-checked")).toBe("true");
    await act(async () => {
      fireEvent.click(sw);
    });
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch).toEqual({ method: "PATCH", path: "/api/devices/501", body: { status: "disabled" } });
    expect(sw.getAttribute("aria-checked")).toBe("false");
    expect(await screen.findByText("Listening turned off")).toBeTruthy();
  });

  it("reverts the toggle when the API refuses", async () => {
    mockFetch((c) => (c.method === "PATCH" ? respond(403, { error: "scope_violation", message: "no" }) : undefined));
    render(<MyDevices houseId={3} />);
    const sw = await screen.findByRole("switch", { name: /Kitchen sensor/ });
    await act(async () => {
      fireEvent.click(sw);
    });
    await waitFor(() => expect(sw.getAttribute("aria-checked")).toBe("true"));
    expect(screen.getByRole("alert").textContent).toContain("You don't have access");
  });

  it("shows the API key once after adding a device", async () => {
    mockFetch();
    render(<MyDevices houseId={3} />);
    await screen.findByText("Kitchen sensor");
    fireEvent.change(screen.getByLabelText("Room"), { target: { value: "31" } });
    fireEvent.change(screen.getByLabelText(/Serial number/), { target: { value: "SN-NEW" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add device" }));
    });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("api-key").textContent).toBe("dk_secret_once");
    fireEvent.click(within(dialog).getByRole("button", { name: "I've saved it" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.body.textContent).not.toContain("dk_secret_once");
  });
});

describe("A4 DeviceManagement", () => {
  it("disable-house confirm shows the device count and calls the cascade", async () => {
    mockFetch();
    render(<DeviceManagement />);
    fireEvent.click(await screen.findByRole("button", { name: "Disable house" }));
    const dialog = screen.getByRole("dialog", { name: "Disable house?" });
    expect(dialog.textContent).toContain("all 2 device(s)");
    await act(async () => {
      fireEvent.click(within(dialog).getByRole("button", { name: "Disable house and 2 device(s)" }));
    });
    expect(calls.some((c) => c.method === "POST" && c.path === "/api/houses/3/disable")).toBe(true);
    expect(await screen.findByText(/2 device\(s\) disabled/)).toBeTruthy();
  });

  it("selecting a device in the tree loads it into the form", async () => {
    mockFetch();
    render(<DeviceManagement />);
    fireEvent.click(await screen.findByRole("button", { name: /#501 · Kitchen sensor/ }));
    expect(screen.getByRole("heading", { name: "Edit device SN-OWNER-1" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Disable" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Rotate key" })).toBeTruthy();
  });
});

describe("A8 FleetView", () => {
  it("shows connectivity tiles and filters the table", async () => {
    mockFetch();
    render(<FleetView />);
    const online = await screen.findByRole("button", { name: /Online\s*1/ });
    expect(screen.getByRole("button", { name: /Disabled\s*1/ })).toBeTruthy();
    fireEvent.click(online);
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(2); // header + one online device
    expect(rows[1].textContent).toContain("#501");
  });
});

describe("errorText", () => {
  it("maps machine codes and appends the correlation id", () => {
    const err = Object.assign(new Error("x"), { status: 409, error: "duplicate_serial", correlationId: "c-1" });
    expect(errorText(err)).toBe("That serial number is already registered. (ref c-1)");
  });
});
