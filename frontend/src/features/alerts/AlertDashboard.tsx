import { useCallback, useEffect, useMemo, useState } from "react";
import { getAccessToken, socketUrl } from "../../api/apiClient";
import { alertsApi } from "./api";
import { AlertAnalytics } from "./AlertAnalytics";
import { AlertDetailPanel } from "./AlertDetailPanel";
import { NotificationPreferences } from "./NotificationPreferences";
import { ThresholdManagement } from "./ThresholdManagement";
import type { Alert, AlertFilters, AlertRole, AlertSeverity, AlertState, AlertStats, FalseAlertStat } from "./types";

type Props = { role: AlertRole; houseId: number };
const date = (value: string | null) => value ? new Date(value).toLocaleString() : "—";

export function AlertDashboard({ role, houseId }: Props) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [falseStats, setFalseStats] = useState<FalseAlertStat[]>([]);
  const [filters, setFilters] = useState<AlertFilters>({ house_id: houseId });
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try { const [page, summary, falseData] = await Promise.all([alertsApi.list({ ...filters, house_id: houseId }), alertsApi.stats(houseId), alertsApi.falseStats(houseId)]); setAlerts(page.items); setStats(summary); setFalseStats(falseData.items); setMessage(""); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load alerts."); }
  }, [filters, houseId]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { const token = getAccessToken(); if (!token) return undefined; const socket = new WebSocket(socketUrl("/ws/alerts", { house_id: houseId }), ["bearer", token]); socket.onmessage = (message) => { const type = (JSON.parse(String(message.data)) as { type?: string }).type; if (type === "alert.created" || type === "alert.updated") void load(); }; return () => socket.close(); }, [houseId, load]);
  const visibleConfidence = role === "admin";
  const criticalCount = useMemo(() => alerts.filter((alert) => alert.severity === "critical" && !["resolved", "false_positive"].includes(alert.state)).length, [alerts]);
  const updateFilter = (patch: Partial<AlertFilters>) => setFilters((current) => ({ ...current, ...patch }));

  async function download(format: "csv" | "pdf") { try { await alertsApi.downloadExport(format, houseId); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to download export."); } }
  return <div className="app-shell"><header className="topbar"><div><p className="eyebrow">Smart Home / {role === "admin" ? "Operations" : "Resident"}</p><h1>Alert command center</h1></div><div className="header-actions"><span className="live-dot">Live</span><button className="secondary" onClick={() => void load()}>Refresh</button><button className="secondary" onClick={() => void download("csv")}>Export CSV</button><button className="secondary" onClick={() => void download("pdf")}>Export PDF</button></div></header>
    {message && <div className="error-banner">{message}</div>}
    <section className="hero"><div><span className="eyebrow">House #{houseId}</span><h2>{criticalCount ? `${criticalCount} critical alert${criticalCount === 1 ? "" : "s"} need attention` : "Your home is being monitored"}</h2><p>Review alert activity, notification delivery, and policy health from one place.</p></div><div className="hero-stat"><strong>{stats?.total ?? 0}</strong><span>alerts in view</span></div></section>
    <div className="dashboard-grid"><main>
      <section className="card"><div className="section-heading"><div><p className="eyebrow">Alert stream</p><h2>Recent detections</h2></div><span className="muted">{alerts.length} shown</span></div><div className="filters"><input placeholder="Search alert ID" value={filters.q ?? ""} onChange={(event) => updateFilter({ q: event.target.value || undefined })} /><select value={filters.severity ?? ""} onChange={(event) => updateFilter({ severity: (event.target.value || undefined) as AlertSeverity | undefined })}><option value="">All severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><select value={filters.state ?? ""} onChange={(event) => updateFilter({ state: (event.target.value || undefined) as AlertState | undefined })}><option value="">All states</option><option value="new">New</option><option value="notified">Notified</option><option value="acknowledged">Acknowledged</option><option value="escalated">Escalated</option><option value="resolved">Resolved</option><option value="false_positive">False positive</option></select><input type="date" value={filters.from ?? ""} onChange={(event) => updateFilter({ from: event.target.value || undefined })} /><input type="date" value={filters.to ?? ""} onChange={(event) => updateFilter({ to: event.target.value || undefined })} /></div><div className="alert-table"><div className="alert-table-head"><span>Alert</span><span>Severity</span><span>State</span><span>Created</span></div>{alerts.length === 0 ? <div className="empty-card">No alerts match these filters.</div> : alerts.map((alert) => <button className="alert-row" key={alert.alert_id} onClick={() => setSelected(alert)}><span><strong>#{alert.alert_id} · {alert.sound_type ?? "Unknown sound"}</strong><small>{alert.alert_category} · room {alert.room_id}</small></span><span className={`severity ${alert.severity}`}>{alert.severity}</span><span className={`status ${alert.state}`}>{alert.state}</span><span className="muted">{date(alert.created_at)}{visibleConfidence && alert.confidence !== undefined && <small>{Math.round(alert.confidence * 100)}% confidence</small>}</span></button>)}</div></section>
      <AlertAnalytics stats={stats} falseStats={falseStats} />
      {role === "owner" ? <NotificationPreferences houseId={houseId} /> : <ThresholdManagement />}
    </main><aside className="side-column"><div className="card quick-card"><p className="eyebrow">Access view</p><h3>{role === "admin" ? "Administrator" : "Owner"}</h3><p className="muted">{role === "admin" ? "Confidence and policy controls are visible only to administrators." : "This view excludes model confidence, inference payloads, and internal policy details."}</p></div><div className="card"><h3>State summary</h3>{Object.entries(stats?.by_state ?? {}).map(([state, count]) => <div className="summary-row" key={state}><span>{state.replace("_", " ")}</span><strong>{count}</strong></div>)}</div></aside></div>
    {selected && <AlertDetailPanel alert={selected} role={role} onClose={() => setSelected(null)} onChanged={() => { setSelected(null); void load(); }} />}
  </div>;
}
