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

  const tiles: Array<{ label: string; value: string }> = [
    { label: "PostgreSQL", value: health.postgres },
    { label: "MongoDB", value: health.mongo },
    { label: "S3", value: health.s3 },
    { label: "SQS visible", value: String(health.sqs.visible) },
    { label: "SQS in-flight", value: String(health.sqs.in_flight) },
    { label: "DLQ", value: String(health.dlq.visible) },
    { label: "Unprocessed", value: String(health.unprocessed_events) },
  ];

  return (
    <section aria-label="Data health">
      <h2>D1 · Data health</h2>
      <p>Refreshes every 15 seconds.</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: "1rem" }}>
        {tiles.map((t) => (
          <div key={t.label} style={{ padding: "1rem", background: "#fff", borderRadius: 8 }}>
            <div style={{ fontSize: 12, color: "#64748b" }}>{t.label}</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>{t.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
