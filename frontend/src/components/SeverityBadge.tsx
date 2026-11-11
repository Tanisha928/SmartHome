type Props = { severity: "critical" | "high" | "medium" | "low" };
const labels = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
const icons = { critical: "!", high: "▲", medium: "●", low: "•" };
export function SeverityBadge({ severity }: Props) { return <span className={`severity-badge ${severity}`} aria-label={`${labels[severity]} severity`}><span aria-hidden="true">{icons[severity]}</span> {labels[severity]}</span>; }
