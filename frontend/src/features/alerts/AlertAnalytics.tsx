import type { AlertStats, FalseAlertStat } from "./types";

type Props = { stats: AlertStats | null; falseStats: FalseAlertStat[] };

export function AlertAnalytics({ stats, falseStats }: Props) {
  if (!stats) return <div className="empty-card">Analytics will appear after alerts are loaded.</div>;
  return <section className="analytics-grid">
    <div className="metric-card"><span>Total alerts</span><strong>{stats.total}</strong></div>
    <div className="metric-card"><span>Critical</span><strong>{stats.by_severity.critical ?? 0}</strong></div>
    <div className="metric-card"><span>Open</span><strong>{(stats.by_state.new ?? 0) + (stats.by_state.notified ?? 0) + (stats.by_state.escalated ?? 0)}</strong></div>
    <div className="chart-card"><h3>Alerts by category</h3>{Object.entries(stats.by_category).map(([label, value]) => <div className="bar-row" key={label}><span>{label}</span><div className="bar"><i style={{ width: `${stats.total ? Math.max(4, (value / stats.total) * 100) : 0}%` }} /></div><strong>{value}</strong></div>)}</div>
    <div className="chart-card"><h3>False-alert rate by sound</h3>{falseStats.length === 0 ? <p className="muted">No false-alert samples yet.</p> : falseStats.map((item) => <div className="bar-row" key={item.sound_type}><span>{item.sound_type}</span><div className="bar"><i className={item.low_sample ? "warning-bar" : ""} style={{ width: `${Math.max(4, item.rate * 100)}%` }} /></div><strong>{Math.round(item.rate * 100)}%{item.low_sample ? "*" : ""}</strong></div>)}<small className="muted">* Low sample: fewer than 20 observations.</small></div>
  </section>;
}
