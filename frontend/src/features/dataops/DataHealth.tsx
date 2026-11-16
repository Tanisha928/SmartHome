import { useEffect, useState } from "react";
import { dataOpsApi } from "./api";
import type { HealthSnapshot } from "./types";

const REFRESH_MS = 15_000;

export function DataHealth() {
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await dataOpsApi.health();
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load health");
      }
    };
    void load();
    const id = window.setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (error) return <p role="alert">Health error: {error}</p>;
  if (!health) return <p>Loading data health…</p>;

  const tiles: Array<{ label: string; service: string; value: string }> = [
    { label: "Application database", service: "PostgreSQL", value: health.postgres },
    { label: "Inference & telemetry storage", service: "MongoDB", value: health.mongo },
    { label: "Recording storage", service: "Amazon S3", value: health.s3 },
    { label: "Events waiting to process", service: "Amazon SQS · Waiting", value: String(health.sqs.visible) },
    { label: "Events being processed", service: "Amazon SQS · In progress", value: String(health.sqs.in_flight) },
    { label: "Failed events", service: "Amazon SQS · Dead-letter queue", value: String(health.dlq.visible) },
    { label: "Pending events", service: "Application processing backlog", value: String(health.unprocessed_events) },
  ];

  return (
    <section aria-label="Data health">
      <h2>Data health</h2>
      <p>Storage, processing, and queue activity at a glance. Updates every 15 seconds.</p>
      <div className="health-grid">
        {tiles.map((t) => (
          <div key={t.label} className="health-tile">
            <span>{t.label}</span>
            <strong>{t.value === "ok" ? "Operational" : t.value}</strong>
            <small>{t.service}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
