/** A8 · Fleet view: connectivity stats and a filterable device table (admin). */

import { useCallback, useEffect, useMemo, useState } from "react";
import { devicesApi, errorText, listAllDevices } from "./api";
import { applyDeviceUpdate, useDeviceEvents } from "./live";
import { deviceHealth, fleetStats, heartbeatAge, houseLabel, type DeviceHealth } from "./logic";
import type { Device, House } from "./types";
import { button, card, colors, HealthBadge, input, Notice } from "./ui";

const REFRESH_MS = 15_000;

export function FleetView() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [houses, setHouses] = useState<House[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);
  const [filter, setFilter] = useState<DeviceHealth | "all">("all");
  const [houseId, setHouseId] = useState("");

  const load = useCallback(async () => {
    try {
      const [d, h] = await Promise.all([listAllDevices(), devicesApi.listHouses()]);
      setDevices(d);
      setHouses(h.items);
      setLoadedAt(Date.now());
      setError(null);
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  useDeviceEvents(undefined, (update) => setDevices((all) => applyDeviceUpdate(all, update)));

  const scoped = houseId ? devices.filter((d) => String(d.house_id) === houseId) : devices;
  const stats = fleetStats(scoped);
  const rows = useMemo(
    () =>
      scoped
        .filter((d) => filter === "all" || deviceHealth(d) === filter)
        .sort((a, b) => (a.last_heartbeat ?? "").localeCompare(b.last_heartbeat ?? "")),
    [scoped, filter],
  );
  const houseName = (id: number) => {
    const h = houses.find((x) => x.house_id === id);
    return h ? houseLabel(h) : `House ${id}`;
  };

  const tiles: Array<{ key: DeviceHealth | "all"; label: string; value: number }> = [
    { key: "all", label: "All devices", value: stats.total },
    { key: "online", label: "Online", value: stats.online },
    { key: "offline", label: "Offline", value: stats.offline },
    { key: "disabled", label: "Disabled", value: stats.disabled },
  ];

  return (
    <section aria-label="Fleet" style={{ display: "grid", gap: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>A8 · Fleet</h2>
        <span style={{ color: "#64748b", fontSize: 14 }}>
          {loadedAt ? `Updated ${heartbeatAge(new Date(loadedAt).toISOString())}` : "Loading…"}
        </span>
        <button type="button" style={{ ...button, marginLeft: "auto" }} onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}

      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
        {tiles.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-pressed={filter === t.key}
            onClick={() => setFilter(t.key)}
            style={{
              ...card,
              cursor: "pointer",
              textAlign: "left",
              borderColor: filter === t.key ? colors.primary : colors.border,
              borderWidth: filter === t.key ? 2 : 1,
            }}
          >
            <div style={{ fontSize: 14, color: "#475569" }}>{t.label}</div>
            <div style={{ fontSize: 32, fontWeight: 600 }}>{t.value}</div>
          </button>
        ))}
      </div>

      <div style={{ ...card, display: "grid", gap: 12 }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center", maxWidth: 420 }}>
          <span style={{ whiteSpace: "nowrap" }}>House</span>
          <select style={input} value={houseId} onChange={(e) => setHouseId(e.target.value)}>
            <option value="">All houses</option>
            {houses.map((h) => (
              <option key={h.house_id} value={h.house_id}>
                #{h.house_id} · {houseLabel(h)}
              </option>
            ))}
          </select>
        </label>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left" }}>
                <th>Device</th>
                <th>House</th>
                <th>Type</th>
                <th>State</th>
                <th>Last heartbeat</th>
                <th>RSSI</th>
                <th>Config v</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: "1rem 0", color: "#64748b" }}>
                    No devices match this filter.
                  </td>
                </tr>
              )}
              {rows.map((d) => (
                <tr key={d.device_id} style={{ borderTop: "1px solid #e2e8f0" }}>
                  <td style={{ padding: "0.5rem 0" }}>
                    #{d.device_id} · {d.label ?? d.serial_no}
                  </td>
                  <td>{houseName(d.house_id)}</td>
                  <td>{d.device_type}</td>
                  <td>
                    <HealthBadge health={deviceHealth(d)} />
                  </td>
                  <td>{heartbeatAge(d.last_heartbeat)}</td>
                  <td>{d.wifi_rssi != null ? `${d.wifi_rssi} dBm` : "–"}</td>
                  <td>{d.config_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
