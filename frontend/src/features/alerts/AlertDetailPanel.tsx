import { useEffect, useState } from "react";
import { alertsApi } from "./api";
import type { Alert, AlertDetail, AlertRole, AlertState } from "./types";

type Props = { alert: Alert; role: AlertRole; onClose: () => void; onChanged: () => void };

const date = (value: string | null) => value ? new Date(value).toLocaleString() : "—";

export function AlertDetailPanel({ alert, role, onClose, onChanged }: Props) {
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [message, setMessage] = useState("");
  const [nextState, setNextState] = useState<AlertState>(alert.state === "new" ? "acknowledged" : "resolved");

  useEffect(() => {
    alertsApi.detail(alert.alert_id).then(setDetail).catch((error: unknown) => setMessage(String(error)));
  }, [alert.alert_id]);

  async function updateState() {
    try {
      await alertsApi.transition(alert.alert_id, nextState, alert.state, message || undefined);
      setMessage("State updated.");
      onChanged();
    } catch (error) {
      const apiError = error as { status?: number; message?: string; details?: { last_actor?: string; current_state?: string } };
      if (apiError.status === 409) {
        setMessage(`Conflict: changed by ${apiError.details?.last_actor ?? "another user"}${apiError.details?.current_state ? ` (now ${apiError.details.current_state})` : ""}. Refresh and try again.`);
      } else {
        setMessage(error instanceof Error ? error.message : "Unable to update state.");
      }
    }
  }

  return (
    <aside className="detail-panel" aria-label="Alert details">
      <div className="panel-heading"><div><span className={`severity ${alert.severity}`}>{alert.severity}</span><h2>Alert #{alert.alert_id}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close details">×</button></div>
      <div className="detail-grid"><span>Sound</span><strong>{alert.sound_type ?? "Unknown"}</strong><span>Category</span><strong>{alert.alert_category}</strong><span>House / room</span><strong>{alert.house_id} / {alert.room_id}</strong><span>Created</span><strong>{date(alert.created_at)}</strong></div>
      {role === "admin" && <div className="confidence-card"><span>Model confidence</span><strong>{alert.confidence === undefined ? "—" : `${Math.round(alert.confidence * 100)}%`}</strong></div>}
      {role === "admin" && <section><h3>Update state</h3><div className="inline-form"><select value={nextState} onChange={(event) => setNextState(event.target.value as AlertState)}><option value="acknowledged">Acknowledge</option><option value="escalated">Escalate</option><option value="resolved">Resolve</option><option value="false_positive">Mark false positive</option></select><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Optional note" /><button className="primary" onClick={updateState}>Save</button></div></section>}
      {detail && <>
        <section><h3>State history</h3><div className="timeline">{detail.history.map((item) => <div className="timeline-item" key={item.history_id}><span className="timeline-dot" /><div><strong>{item.to_state}</strong><small>{date(item.changed_at)} · user {item.actor_user_id ?? "system"}</small>{item.note && <p>{item.note}</p>}</div></div>)}</div></section>
        <section><h3>Notification delivery</h3><div className="delivery-list">{detail.deliveries.length === 0 ? <p className="muted">No notification attempts recorded.</p> : detail.deliveries.map((delivery) => <div className="delivery-row" key={delivery.notification_id}><div><strong>{delivery.channel.toUpperCase()}</strong><small>{delivery.recipient_label ?? "Unknown recipient"}</small></div><span className={`status ${delivery.status}`}>{delivery.status} · {delivery.attempts} attempt{delivery.attempts === 1 ? "" : "s"}</span></div>)}</div></section>
      </>}
      {message && <p className="notice">{message}</p>}
    </aside>
  );
}
