/** A4 · Admin device management: register houses/devices, house tree, cascade disable. */

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { devicesApi, errorText, listAllDevices } from "./api";
import { applyDeviceUpdate, useDeviceEvents } from "./live";
import {
  buildHouseTree,
  deviceHealth,
  filterTree,
  heartbeatAge,
  houseLabel,
  ROOM_TYPE_LABELS,
} from "./logic";
import type { Device, DeviceType, House, Room, RoomType } from "./types";
import {
  ApiKeyModal,
  button,
  card,
  ConfirmDialog,
  Field,
  HealthBadge,
  input,
  Notice,
  primaryButton,
} from "./ui";

const NEW_ROOM = "__new__";

type DeviceForm = {
  houseId: string;
  roomId: string;
  newRoomType: RoomType;
  newRoomLabel: string;
  deviceType: DeviceType;
  serial: string;
  label: string;
  threshold: string;
};

const emptyDeviceForm: DeviceForm = {
  houseId: "",
  roomId: "",
  newRoomType: "living",
  newRoomLabel: "",
  deviceType: "audio",
  serial: "",
  label: "",
  threshold: "",
};

export function DeviceManagement() {
  const [houses, setHouses] = useState<House[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Device | null>(null);
  const [form, setForm] = useState<DeviceForm>(emptyDeviceForm);
  const [newKey, setNewKey] = useState<{ key: string; label: string } | null>(null);
  const [confirm, setConfirm] = useState<
    { kind: "house"; house: House; count: number } | { kind: "remove"; device: Device } | null
  >(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [h, r, d] = await Promise.all([
        devicesApi.listHouses(),
        devicesApi.listRooms(),
        listAllDevices(),
      ]);
      setHouses(h.items);
      setRooms(r.items);
      setDevices(d);
      setError(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useDeviceEvents(undefined, (update) => setDevices((all) => applyDeviceUpdate(all, update)));

  const tree = useMemo(
    () => filterTree(buildHouseTree(houses, rooms, devices), query),
    [houses, rooms, devices, query],
  );
  const roomsForHouse = rooms.filter((r) => String(r.house_id) === form.houseId);

  const run = async (action: () => Promise<string | void>) => {
    setError(null);
    setInfo(null);
    try {
      const msg = await action();
      if (msg) setInfo(msg);
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const select = (d: Device) => {
    setSelected(d);
    setForm({
      ...emptyDeviceForm,
      houseId: String(d.house_id),
      roomId: String(d.room_id),
      deviceType: d.device_type,
      serial: d.serial_no,
      label: d.label ?? "",
      threshold: d.threshold != null ? d.threshold.toFixed(2) : "",
    });
  };

  const clearSelection = () => {
    setSelected(null);
    setForm((f) => ({ ...emptyDeviceForm, houseId: f.houseId }));
  };

  const resolveRoomId = async (): Promise<number> => {
    if (form.roomId !== NEW_ROOM) return Number(form.roomId);
    const room = await devicesApi.createRoom({
      house_id: Number(form.houseId),
      room_type: form.newRoomType,
      label: form.newRoomLabel.trim() || ROOM_TYPE_LABELS[form.newRoomType],
    });
    return room.room_id;
  };

  const addDevice = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const roomId = await resolveRoomId();
      const created = await devicesApi.createDevice({
        room_id: roomId,
        device_type: form.deviceType,
        serial_no: form.serial.trim(),
        label: form.label.trim() || undefined,
      });
      setNewKey({ key: created.api_key, label: created.label ?? created.serial_no });
      clearSelection();
      return `Registered device ${created.serial_no}`;
    });
  };

  const updateDevice = () =>
    selected &&
    void run(async () => {
      const roomId = await resolveRoomId();
      await devicesApi.updateDevice(selected.device_id, {
        label: form.label.trim() || undefined,
        room_id: roomId !== selected.room_id ? roomId : undefined,
        threshold: form.threshold ? Number(form.threshold) : undefined,
      });
      return "Device updated";
    });

  const setStatus = (d: Device, status: "enabled" | "disabled") =>
    void run(async () => {
      await devicesApi.updateDevice(d.device_id, { status });
      return status === "enabled" ? "Device enabled" : "Device disabled";
    });

  const rotate = (d: Device) =>
    void run(async () => {
      const res = await devicesApi.rotateKey(d.device_id);
      setNewKey({ key: res.api_key, label: res.label ?? res.serial_no });
      return "Key rotated; the old key no longer works";
    });

  return (
    <section aria-label="Device management" style={{ display: "grid", gap: "1rem" }}>
      <h2 style={{ margin: 0 }}>A4 · Device management</h2>
      {error && <Notice kind="error">{error}</Notice>}
      {info && <Notice kind="info">{info}</Notice>}

      <div
        style={{
          display: "grid",
          gap: "1rem",
          gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
          alignItems: "start",
        }}
      >
        <div style={{ display: "grid", gap: "1rem" }}>
          <HouseForm onCreated={(msg) => void run(async () => msg)} onError={setError} />

          <form onSubmit={addDevice} style={{ ...card, display: "grid", gap: 12 }}>
            <h3 style={{ margin: 0 }}>
              {selected ? `Edit device ${selected.serial_no}` : "Register device"}
            </h3>
            <Field label="House">
              <select
                required
                style={input}
                value={form.houseId}
                disabled={!!selected}
                onChange={(e) => setForm({ ...form, houseId: e.target.value, roomId: "" })}
              >
                <option value="">Select a house…</option>
                {houses.map((h) => (
                  <option key={h.house_id} value={h.house_id}>
                    #{h.house_id} · {houseLabel(h)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Room">
              <select
                required
                style={input}
                value={form.roomId}
                disabled={!form.houseId}
                onChange={(e) => setForm({ ...form, roomId: e.target.value })}
              >
                <option value="">Select a room…</option>
                {roomsForHouse.map((r) => (
                  <option key={r.room_id} value={r.room_id}>
                    {r.label} ({ROOM_TYPE_LABELS[r.room_type]})
                  </option>
                ))}
                <option value={NEW_ROOM}>+ New room…</option>
              </select>
            </Field>
            {form.roomId === NEW_ROOM && (
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
                <Field label="Room type">
                  <select
                    style={input}
                    value={form.newRoomType}
                    onChange={(e) => setForm({ ...form, newRoomType: e.target.value as RoomType })}
                  >
                    {Object.entries(ROOM_TYPE_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Room name">
                  <input
                    style={input}
                    value={form.newRoomLabel}
                    placeholder={ROOM_TYPE_LABELS[form.newRoomType]}
                    onChange={(e) => setForm({ ...form, newRoomLabel: e.target.value })}
                  />
                </Field>
              </div>
            )}
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
              <Field label="Device type">
                <select
                  style={input}
                  value={form.deviceType}
                  disabled={!!selected}
                  onChange={(e) => setForm({ ...form, deviceType: e.target.value as DeviceType })}
                >
                  <option value="audio">Audio sensor</option>
                  <option value="camera">Camera</option>
                </select>
              </Field>
              <Field label="Serial number">
                <input
                  required
                  style={input}
                  value={form.serial}
                  disabled={!!selected}
                  onChange={(e) => setForm({ ...form, serial: e.target.value })}
                />
              </Field>
            </div>
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
              <Field label="Label (optional)">
                <input
                  style={input}
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                />
              </Field>
              <Field label="Threshold override (0.50–0.99)">
                <input
                  style={input}
                  type="number"
                  min={0.5}
                  max={0.99}
                  step={0.01}
                  value={form.threshold}
                  disabled={!selected}
                  onChange={(e) => setForm({ ...form, threshold: e.target.value })}
                />
              </Field>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {!selected && (
                <button type="submit" style={primaryButton}>
                  Add
                </button>
              )}
              {selected && (
                <>
                  <button type="button" style={primaryButton} onClick={updateDevice}>
                    Update
                  </button>
                  {selected.status === "enabled" ? (
                    <button type="button" style={button} onClick={() => setStatus(selected, "disabled")}>
                      Disable
                    </button>
                  ) : (
                    <button type="button" style={button} onClick={() => setStatus(selected, "enabled")}>
                      Enable
                    </button>
                  )}
                  <button type="button" style={button} onClick={() => rotate(selected)}>
                    Rotate key
                  </button>
                  <button
                    type="button"
                    style={{ ...button, color: "#b91c1c" }}
                    onClick={() => setConfirm({ kind: "remove", device: selected })}
                  >
                    Remove
                  </button>
                  <button type="button" style={button} onClick={clearSelection}>
                    Cancel
                  </button>
                </>
              )}
            </div>
          </form>
        </div>

        <div style={{ ...card, display: "grid", gap: 12 }}>
          <Field label="Search by house ID, device ID, address or serial">
            <input
              type="search"
              style={input}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. 12 or SN-0042"
            />
          </Field>
          {loading && <p aria-busy="true">Loading houses…</p>}
          {!loading && tree.length === 0 && (
            <p>{query ? "No matches." : "No houses yet. Register one on the left."}</p>
          )}
          <ul aria-label="House tree" style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {tree.map((node) => (
              <li key={node.house.house_id} style={{ borderTop: "1px solid #e2e8f0", padding: "0.75rem 0" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <strong>
                    #{node.house.house_id} · {houseLabel(node.house)}
                  </strong>
                  <HealthBadge
                    health={node.house.status === "active" ? "online" : "disabled"}
                    text={node.house.status === "active" ? "● Active" : "⏸ Disabled"}
                  />
                  <span style={{ marginLeft: "auto" }} />
                  {node.house.status === "active" ? (
                    <button
                      type="button"
                      style={button}
                      onClick={() =>
                        setConfirm({ kind: "house", house: node.house, count: node.deviceCount })
                      }
                    >
                      Disable house
                    </button>
                  ) : (
                    <button
                      type="button"
                      style={button}
                      onClick={() =>
                        void run(async () => {
                          const r = await devicesApi.enableHouse(node.house.house_id);
                          return `House enabled; ${r.devices_updated} device(s) re-enabled`;
                        })
                      }
                    >
                      Enable house
                    </button>
                  )}
                </div>
                {node.rooms.map(({ room, devices: roomDevices }) => (
                  <div key={room.room_id} style={{ marginLeft: 16, marginTop: 8 }}>
                    <div style={{ color: "#475569" }}>{room.label}</div>
                    {roomDevices.length === 0 && (
                      <div style={{ marginLeft: 16, color: "#94a3b8" }}>No devices</div>
                    )}
                    {roomDevices.map((d) => (
                      <DeviceRow
                        key={d.device_id}
                        device={d}
                        selected={selected?.device_id === d.device_id}
                        onSelect={() => select(d)}
                      />
                    ))}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {newKey && (
        <ApiKeyModal apiKey={newKey.key} deviceLabel={newKey.label} onClose={() => setNewKey(null)} />
      )}
      {confirm?.kind === "house" && (
        <ConfirmDialog
          title="Disable house?"
          body={
            <p>
              This disables <strong>{houseLabel(confirm.house)}</strong> and all{" "}
              <strong>{confirm.count}</strong> device(s) in it. Devices stop uploading on their
              next heartbeat.
            </p>
          }
          confirmLabel={`Disable house and ${confirm.count} device(s)`}
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            const house = confirm.house;
            setConfirm(null);
            void run(async () => {
              const r = await devicesApi.disableHouse(house.house_id);
              return `House disabled; ${r.devices_updated} device(s) disabled`;
            });
          }}
        />
      )}
      {confirm?.kind === "remove" && (
        <ConfirmDialog
          title="Remove device?"
          body={
            <p>
              Device <strong>{confirm.device.serial_no}</strong> will be removed and its key
              revoked. Its alert history is kept.
            </p>
          }
          confirmLabel="Remove device"
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            const d = confirm.device;
            setConfirm(null);
            void run(async () => {
              await devicesApi.removeDevice(d.device_id);
              clearSelection();
              return "Device removed";
            });
          }}
        />
      )}
    </section>
  );
}

function DeviceRow({
  device,
  selected,
  onSelect,
}: {
  device: Device;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      style={{
        ...button,
        display: "flex",
        width: "calc(100% - 16px)",
        marginLeft: 16,
        marginTop: 4,
        gap: 8,
        alignItems: "center",
        textAlign: "left",
        flexWrap: "wrap",
        background: selected ? "#ccfbf1" : "#fff",
      }}
    >
      <span>
        #{device.device_id} · {device.label ?? device.serial_no}
      </span>
      <HealthBadge health={deviceHealth(device)} />
      <span style={{ marginLeft: "auto", fontSize: 14, color: "#475569" }}>
        {heartbeatAge(device.last_heartbeat)} · {device.wifi_rssi ?? "–"} dBm
      </span>
    </button>
  );
}

function HouseForm({
  onCreated,
  onError,
}: {
  onCreated: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [f, setF] = useState({
    address_line: "",
    city: "",
    state: "",
    postal_code: "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Los_Angeles",
    owner_email: "",
    latitude: "",
    longitude: "",
  });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const res = await devicesApi.createHouse({
        address_line: f.address_line.trim(),
        city: f.city.trim() || undefined,
        state: f.state.trim() || undefined,
        postal_code: f.postal_code.trim(),
        timezone: f.timezone,
        owner_email: f.owner_email.trim() || undefined,
        latitude: f.latitude ? Number(f.latitude) : undefined,
        longitude: f.longitude ? Number(f.longitude) : undefined,
      });
      setF({ ...f, address_line: "", city: "", state: "", postal_code: "", owner_email: "", latitude: "", longitude: "" });
      const owner = res.owner ? ` Owner ${res.owner.email} linked.` : "";
      onCreated(`House #${res.house_id} registered.${owner}`);
    } catch (err) {
      onError(errorText(err));
    }
  };
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF({ ...f, [k]: e.target.value });
  return (
    <form onSubmit={(e) => void submit(e)} style={{ ...card, display: "grid", gap: 12 }}>
      <h3 style={{ margin: 0 }}>Register house</h3>
      <Field label="Address">
        <input required style={input} value={f.address_line} onChange={set("address_line")} />
      </Field>
      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "2fr 1fr 1fr" }}>
        <Field label="City">
          <input style={input} value={f.city} onChange={set("city")} />
        </Field>
        <Field label="State">
          <input style={input} value={f.state} onChange={set("state")} />
        </Field>
        <Field label="Postal code">
          <input required style={input} value={f.postal_code} onChange={set("postal_code")} />
        </Field>
      </div>
      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
        <Field label="Latitude">
          <input style={input} type="number" step="any" value={f.latitude} onChange={set("latitude")} />
        </Field>
        <Field label="Longitude">
          <input style={input} type="number" step="any" value={f.longitude} onChange={set("longitude")} />
        </Field>
      </div>
      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
        <Field label="Time zone">
          <input required style={input} value={f.timezone} onChange={set("timezone")} />
        </Field>
        <Field label="Owner email (optional)">
          <input style={input} type="email" value={f.owner_email} onChange={set("owner_email")} />
        </Field>
      </div>
      <div>
        <button type="submit" style={primaryButton}>
          Add house
        </button>
      </div>
    </form>
  );
}
