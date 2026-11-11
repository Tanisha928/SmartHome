import type { ReactNode } from "react";

type Props = { loading?: boolean; empty?: boolean; error?: { message: string; correlationId?: string } | null; staleAt?: Date; onRetry?: () => void; children: ReactNode; emptyAction?: ReactNode };
export function DataView({ loading, empty, error, staleAt, onRetry, children, emptyAction }: Props) {
  if (loading) return <div className="data-view" role="status"><div className="skeleton" /><div className="skeleton short" /><span>Loading…</span></div>;
  if (error) return <div className="data-view error-state" role="alert"><strong>Unable to load this view</strong><p>{error.message}</p>{error.correlationId && <small>Correlation ID: {error.correlationId}</small>}<button className="primary" onClick={onRetry}>Retry</button></div>;
  if (empty) return <div className="data-view"><strong>No data yet</strong><p>There is nothing to show for the current filters.</p>{emptyAction}</div>;
  return <>{staleAt && <div className="stale-banner">Showing data from {staleAt.toLocaleTimeString()} <button onClick={onRetry}>Refresh</button></div>}{children}</>;
}
