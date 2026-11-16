import { useCallback, useEffect, useMemo, useState } from "react";
import { alertsApi } from "../features/alerts/api";
import { devicesApi } from "../features/devices/api";
import type { House } from "../features/devices/types";
import type { Alert } from "../features/alerts/types";
import { AlertDetailPanel } from "../features/alerts/AlertDetailPanel";
import { DataView } from "../components/DataView";
import { friendlyLabel } from "../lib/labels";
import { downloadCsv, toCsv } from "../lib/exportService";
export function AdminHistory(_props: { houseId?: number }) {
  const [houseId, setHouseId] = useState<number | undefined>(undefined);
  const [houses, setHouses] = useState<House[]>([]);
  const [items, setItems] = useState<Alert[]>([]);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Alert["severity"] | "">("");
  const [state, setState] = useState<Alert["state"] | "">("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string } | null>(null);

  useEffect(() => { void devicesApi.listHouses().then((page) => setHouses(page.items)).catch(() => undefined); }, []);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await alertsApi.list({ page, page_size: 25, house_id: houseId, q: query || undefined, severity: severity || undefined, state: state || undefined, from: from || undefined, to: to || undefined });
      setItems(result.items);
      setTotal(result.total);
      setError(null);
    } catch (err) { setError(err as { message: string }); }
    finally { setLoading(false); }
  }, [from, houseId, page, query, severity, state, to]);
  useEffect(() => { setPage(1); }, [from, houseId, query, severity, state, to]);
  useEffect(() => { void load(); }, [load]);

  const sortedItems = useMemo(() => [...items].sort((a, b) => {
    const aTime = new Date(a.created_at ?? 0).getTime();
    const bTime = new Date(b.created_at ?? 0).getTime();
    return sort === "newest" ? bTime - aTime : aTime - bTime;
  }), [items, sort]);
  function exportRows() { downloadCsv("alerts.csv", toCsv(sortedItems.map((item) => ({ alert: friendlyLabel(item.sound_type), severity: item.severity, state: item.state, created: item.created_at ?? "" })), ["alert", "severity", "state", "created"])); }
  const pageCount = Math.max(1, Math.ceil(total / 25));
  return <div className="app-shell"><header className="topbar"><div><p className="eyebrow">Operations / history</p><h1>Alert history</h1></div><div className="header-actions"><button className="secondary" onClick={exportRows}>Export CSV</button><button className="secondary" onClick={() => void alertsApi.downloadExport("pdf", houseId)}>Export PDF</button><button className="secondary" onClick={() => void load()}>Refresh</button></div></header><section className="card"><div className="history-toolbar"><select aria-label="House" value={houseId ?? ""} onChange={(e) => setHouseId(e.target.value ? Number(e.target.value) : undefined)}><option value="">All houses</option>{houses.map((item) => <option key={item.house_id} value={item.house_id}>House {item.house_id}{item.address_line ? ` · ${item.address_line}` : ""}</option>)}</select><input aria-label="Search alerts" placeholder="Search alert or house" value={query} onChange={(e) => setQuery(e.target.value)} /><select aria-label="Filter by severity" value={severity} onChange={(e) => setSeverity(e.target.value as typeof severity)}><option value="">All severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><select aria-label="Filter by state" value={state} onChange={(e) => setState(e.target.value as typeof state)}><option value="">All states</option><option value="new">New</option><option value="notified">Notified</option><option value="acknowledged">Acknowledged</option><option value="escalated">Escalated</option><option value="resolved">Resolved</option><option value="false_positive">False positive</option></select><label>From<input aria-label="From date" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label><label>To<input aria-label="To date" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label><select aria-label="Sort alerts" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></div><DataView loading={loading} error={error} onRetry={() => void load()} empty={!loading && sortedItems.length === 0}><table className="history-table"><thead><tr><th>Alert</th><th>Severity</th><th>State</th><th>House / room</th><th>Created</th></tr></thead><tbody>{sortedItems.map((item) => <tr key={item.alert_id} onClick={() => setSelected(item)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setSelected(item); }} tabIndex={0}><td><strong>{friendlyLabel(item.sound_type)}</strong><small>Alert #{item.alert_id}</small></td><td>{item.severity}</td><td>{item.state.replace("_", " ")}</td><td>{item.house_id} / {item.room_id}</td><td>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td></tr>)}</tbody></table></DataView><div className="history-pagination" aria-label="History pagination"><button className="secondary" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><span>Page {page} of {pageCount} · {total} alerts</span><button className="secondary" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)}>Next</button></div></section>{selected && <AlertDetailPanel alert={selected} role="admin" onClose={() => setSelected(null)} onChanged={() => { setSelected(null); void load(); }} />}</div>;
}
