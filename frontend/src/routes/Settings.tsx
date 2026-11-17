import { useEffect, useState } from "react";
import { api, apiRequest, type DashboardSettingsInput } from "../api/apiClient";

type Audit = { action?: string; actor_email?: string; actor_user_id?: number; created_at?: string; ts?: string; house_id?: number };
const defaults: DashboardSettingsInput = { default_map_latitude: 47.6062, default_map_longitude: -122.3321, show_critical_toasts: true, play_alert_sound: true };

export function Settings() {
  const [form, setForm] = useState<DashboardSettingsInput>(defaults);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [activity, setActivity] = useState<Audit[]>([]);
  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      api.dashboardSettings(),
      apiRequest<{ items?: Audit[] }>("/api/admin/audit?page_size=10").catch(() => ({ items: [] })),
    ]).then(([settings, audit]) => {
      if (cancelled) return;
      setForm(settings);
      setActivity(audit.items ?? []);
      setLoaded(true);
    }).catch(() => { if (!cancelled) setError("Unable to load dashboard settings. Please try again."); });
    return () => { cancelled = true; };
  }, []);

  async function save() {
    setSaving(true); setSaved(false); setError("");
    try { await api.saveDashboardSettings(form); setSaved(true); }
    catch { setError("Unable to save dashboard settings. Please try again."); }
    finally { setSaving(false); }
  }

  return <div className="app-shell">
    <header className="topbar"><div><p className="eyebrow">Account / settings</p><h1>Dashboard settings</h1></div></header>
    {error && <p role="alert" className="error-banner">{error}</p>}
    {!loaded && !error && <p role="status">Loading settings…</p>}
    <fieldset disabled={!loaded || saving} className="settings-grid settings-fields">
      <div className="card">
        <h2>Default map location</h2><p>Saved to your dashboard profile.</p>
        <div className="two-col">
          <label>Latitude<input type="number" min="-90" max="90" step="any" value={form.default_map_latitude ?? ""} onChange={e => setForm({ ...form, default_map_latitude: e.target.value ? Number(e.target.value) : null })} /></label>
          <label>Longitude<input type="number" min="-180" max="180" step="any" value={form.default_map_longitude ?? ""} onChange={e => setForm({ ...form, default_map_longitude: e.target.value ? Number(e.target.value) : null })} /></label>
        </div>
      </div>
      <div className="card">
        <h2>Notification defaults</h2>
        <label className="check-row"><input type="checkbox" checked={form.show_critical_toasts} onChange={e => setForm({ ...form, show_critical_toasts: e.target.checked })} /> Show critical alert toasts</label>
        <label className="check-row"><input type="checkbox" checked={form.play_alert_sound} onChange={e => setForm({ ...form, play_alert_sound: e.target.checked })} /> Play an alert sound</label>
        <button className="primary" onClick={() => void save()}>{saving ? "Saving…" : "Save settings"}</button>
        {saved && <p role="status" className="notice">Settings saved to your account.</p>}
      </div>
    </fieldset>
    <section className="card activity-card"><h2>Recent activity</h2>
      {activity.length === 0 ? <p className="muted">No activity available.</p> : <table className="history-table"><thead><tr><th>Action</th><th>Actor</th><th>House</th><th>Time</th></tr></thead><tbody>{activity.map((item, index) => <tr key={`${item.action}-${index}`}><td>{item.action ?? "—"}</td><td>{item.actor_email ?? item.actor_user_id ?? "—"}</td><td>{item.house_id ?? "—"}</td><td>{item.created_at || item.ts ? new Date((item.created_at ?? item.ts)!).toLocaleString() : "—"}</td></tr>)}</tbody></table>}
    </section>
  </div>;
}
