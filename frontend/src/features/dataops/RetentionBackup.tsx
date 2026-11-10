import { useEffect, useState } from "react";
import { dataOpsApi } from "./api";
import type { RetentionPolicy } from "./types";

export function RetentionBackup() {
  const [policy, setPolicy] = useState<RetentionPolicy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expire, setExpire] = useState(30);
  const [ia, setIa] = useState<number | "">("");
  const [ttl, setTtl] = useState(30);

  useEffect(() => {
    void dataOpsApi.getRetention().then((p) => {
      setPolicy(p);
      setExpire(p.clip_expire_days);
      setIa(p.clip_ia_transition_days ?? "");
      setTtl(p.telemetry_ttl_days);
    });
  }, []);

  const save = async () => {
    try {
      const updated = await dataOpsApi.putRetention({
        clip_expire_days: expire,
        clip_ia_transition_days: ia === "" ? null : Number(ia),
        telemetry_ttl_days: ttl,
      });
      setPolicy(updated);
      setError(null);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e.message ?? "Invalid retention settings");
    }
  };

  return (
    <section aria-label="Retention and backup">
      <h2>D5 · Retention &amp; backup</h2>
      {error && <p role="alert">{error}</p>}
      <div style={{ display: "grid", gap: "0.75rem", maxWidth: 420 }}>
        <label>
          Clip expire days
          <input
            type="number"
            value={expire}
            onChange={(e) => setExpire(Number(e.target.value))}
          />
        </label>
        <label>
          IA transition days (optional)
          <input
            type="number"
            value={ia}
            onChange={(e) => setIa(e.target.value === "" ? "" : Number(e.target.value))}
          />
        </label>
        <label>
          Telemetry TTL days
          <input type="number" value={ttl} onChange={(e) => setTtl(Number(e.target.value))} />
        </label>
        <button type="button" style={{ minHeight: 44 }} onClick={() => void save()}>
          Save policy
        </button>
      </div>
      {policy && (
        <p>
          Current: expire {policy.clip_expire_days}d · IA {policy.clip_ia_transition_days ?? "off"} ·
          telemetry {policy.telemetry_ttl_days}d
        </p>
      )}
    </section>
  );
}
