/** H2 · Owner "My devices": add a room, add a device by serial, toggle capture. No raw IDs. */

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { devicesApi, errorText } from "./api";
import { applyDeviceUpdate, useDeviceEvents } from "./live";
import { deviceHealth, heartbeatAge, ROOM_TYPE_LABELS, signalLabel } from "./logic";
import type { Device, Room, RoomType } from "./types";
import { ApiKeyModal, button, card, Field, HealthBadge, input, Notice, primaryButton } from "./ui";

export function MyDevices({ houseId }: { houseId: number }) {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [newKey, setNewKey] = useState<{ key: string; label: string } | null>(null);
  const [roomForm, setRoomForm] = useState({ type: "living" as RoomType, label: "" });
  const [deviceForm, setDeviceForm] = useState({ roomId: "", serial: "", label: "" });

  const load = useCallback(async () => {
    try {
      const [r, d] = await Promise.all([
        devicesApi.listRooms(houseId),
        devicesApi.listDevices({ house_id: houseId }),
      ]);
      setRooms(r.items);
      setDevices(d.items);
      setError(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [houseId]);

  useEffect(() => {
    void load();
  }, [load]);

  useDeviceEvents(houseId, (update) => setDevices((all) => applyDeviceUpdate(all, update)));

  const addRoom = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const label = roomForm.label.trim() || ROOM_TYPE_LABELS[roomForm.type];
      await devicesApi.createRoom({ house_id: houseId, room_type: roomForm.type, label });
      setRoomForm({ ...roomForm, label: "" });
      setInfo(`Added ${label}`);
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const addDevice = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const created = await devicesApi.createDevice({
        room_id: Number(deviceForm.roomId),
        device_type: "audio",
        serial_no: deviceForm.serial.trim(),
        label: deviceForm.label.trim() || undefined,
      });
      setNewKey({ key: created.api_key, label: created.label ?? "your device" });
      setDeviceForm({ roomId: deviceForm.roomId, serial: "", label: "" });
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const toggle = async (d: Device) => {
    const next = d.status === "enabled" ? "disabled" : "enabled";
    setBusy(d.device_id);
    // optimistic: the switch flips immediately, reverts on error
    setDevices((all) => all.map((x) => (x.device_id === d.device_id ? { ...x, status: next } : x)));
    try {
      await devicesApi.updateDevice(d.device_id, { status: next });
      setInfo(next === "enabled" ? "Listening turned on" : "Listening turned off");
    } catch (err) {
      setDevices((all) => all.map((x) => (x.device_id === d.device_id ? d : x)));
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  };

  const roomName = (id: number) => rooms.find((r) => r.room_id === id)?.label ?? "Unassigned";

  return (
    <section aria-label="My devices" style={{ display: "grid", gap: "1rem", maxWidth: 900 }}>
      <h2 style={{ margin: 0 }}>My devices</h2>
      {error && <Notice kind="error">{error}</Notice>}
      {info && <Notice kind="info">{info}</Notice>}

      {loading && <p aria-busy="true">Loading your devices…</p>}
      {!loading && devices.length === 0 && (
        <div style={card}>
          <p style={{ marginTop: 0 }}>No devices yet.</p>
          <p style={{ marginBottom: 0 }}>Add a room below, then add a device using the serial number on its label.</p>
        </div>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
        {devices.map((d) => {
          const on = d.status === "enabled";
          return (
            <li key={d.device_id} style={{ ...card, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ display: "grid", gap: 2 }}>
                <strong>{d.label ?? (d.device_type === "camera" ? "Camera" : "Sound sensor")}</strong>
                <span style={{ color: "#475569", fontSize: 14 }}>
                  {roomName(d.room_id)} · Signal {signalLabel(d.wifi_rssi).toLowerCase()} · Last seen{" "}
                  {heartbeatAge(d.last_heartbeat)}
                </span>
              </div>
              <HealthBadge health={deviceHealth(d)} />
              <label style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, minHeight: 44 }}>
                <span>Listening</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  aria-label={`Listening for ${d.label ?? roomName(d.room_id)}`}
                  disabled={busy === d.device_id}
                  onClick={() => void toggle(d)}
                  style={{
                    width: 64,
                    height: 36,
                    borderRadius: 999,
                    border: "none",
                    cursor: "pointer",
                    background: on ? "#0f766e" : "#94a3b8",
                    color: "#fff",
                    fontSize: 14,
                  }}
                >
                  {on ? "On" : "Off"}
                </button>
              </label>
            </li>
          );
        })}
      </ul>

      <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
        <form onSubmit={(e) => void addRoom(e)} style={{ ...card, display: "grid", gap: 12 }}>
          <h3 style={{ margin: 0 }}>Add a room</h3>
          <Field label="Room type">
            <select
              style={input}
              value={roomForm.type}
              onChange={(e) => setRoomForm({ ...roomForm, type: e.target.value as RoomType })}
            >
              {Object.entries(ROOM_TYPE_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Name (optional)">
            <input
              style={input}
              value={roomForm.label}
              placeholder={ROOM_TYPE_LABELS[roomForm.type]}
              onChange={(e) => setRoomForm({ ...roomForm, label: e.target.value })}
            />
          </Field>
          <div>
            <button type="submit" style={primaryButton}>
              Add room
            </button>
          </div>
        </form>

        <form onSubmit={(e) => void addDevice(e)} style={{ ...card, display: "grid", gap: 12 }}>
          <h3 style={{ margin: 0 }}>Add a device</h3>
          <Field label="Room">
            <select
              required
              style={input}
              value={deviceForm.roomId}
              onChange={(e) => setDeviceForm({ ...deviceForm, roomId: e.target.value })}
            >
              <option value="">Choose a room…</option>
              {rooms.map((r) => (
                <option key={r.room_id} value={r.room_id}>
                  {r.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Serial number (on the device label)">
            <input
              required
              style={input}
              value={deviceForm.serial}
              onChange={(e) => setDeviceForm({ ...deviceForm, serial: e.target.value })}
            />
          </Field>
          <Field label="Nickname (optional)">
            <input
              style={input}
              value={deviceForm.label}
              placeholder="e.g. Kitchen sensor"
              onChange={(e) => setDeviceForm({ ...deviceForm, label: e.target.value })}
            />
          </Field>
          <div>
            <button type="submit" style={primaryButton} disabled={rooms.length === 0}>
              Add device
            </button>
          </div>
        </form>
      </div>

      {newKey && (
        <ApiKeyModal apiKey={newKey.key} deviceLabel={newKey.label} onClose={() => setNewKey(null)} />
      )}
      <button type="button" style={{ ...button, justifySelf: "start" }} onClick={() => void load()}>
        Refresh
      </button>
    </section>
  );
}
