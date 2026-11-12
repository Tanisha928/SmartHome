import { useEffect, useState } from "react";
import { alertsApi } from "./api";
import type { AlertSeverity, NotificationPreference } from "./types";

// Must match the backend sound catalog (backend/app/alerts/catalog.py).
const categories = ["emergency", "safety", "security", "resident", "animal"];
const initial = (category: string): NotificationPreference => ({ alert_category: category, email: true, sms: false, min_severity: "high" });

export function NotificationPreferences({ houseId }: { houseId: number }) {
  const [items, setItems] = useState<NotificationPreference[]>(categories.map(initial));
  const [message, setMessage] = useState("");
  useEffect(() => { alertsApi.preferences(houseId).then((data) => setItems(categories.map((category) => data.items.find((item) => item.alert_category === category) ?? initial(category)))).catch(() => undefined); }, [houseId]);
  const update = (index: number, patch: Partial<NotificationPreference>) => setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  async function save() { try { await alertsApi.savePreferences(houseId, items); setMessage("Preferences saved."); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save preferences."); } }
  return <section className="card"><div className="section-heading"><div><p className="eyebrow">Owner profile</p><h2>Notification matrix</h2><p className="muted">Choose how this household should receive each alert category.</p></div><button className="primary" onClick={save}>Save preferences</button></div><div className="preference-table"><div className="preference-head"><span>Category</span><span>Email</span><span>SMS</span><span>Minimum severity</span></div>{items.map((item, index) => <div className="preference-row" key={item.alert_category}><strong>{item.alert_category}</strong><label><input type="checkbox" checked={item.email} onChange={(event) => update(index, { email: event.target.checked })} /> enabled</label><label><input type="checkbox" checked={item.sms} onChange={(event) => update(index, { sms: event.target.checked })} /> enabled</label><select value={item.min_severity} onChange={(event) => update(index, { min_severity: event.target.value as AlertSeverity })}><option value="critical">Critical only</option><option value="high">High and above</option><option value="medium">Medium and above</option><option value="low">All alerts</option></select></div>)}</div>{message && <p className="notice">{message}</p>}</section>;
}
