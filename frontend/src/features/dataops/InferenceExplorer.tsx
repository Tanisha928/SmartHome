import { useEffect, useState } from "react";
import { dataOpsApi } from "./api";
import type { InferenceLog } from "./types";

export function InferenceExplorer() {
  const [items, setItems] = useState<InferenceLog[]>([]);
  const [modelVersion, setModelVersion] = useState("");
  const [label, setLabel] = useState("");

  const search = async () => {
    const params = new URLSearchParams({ page: "1", page_size: "25" });
    if (modelVersion) params.set("model_version", modelVersion);
    if (label) params.set("label", label);
    const data = await dataOpsApi.inferenceLogs(params);
    setItems(data.items);
  };

  // Load on open; the controls narrow or refresh the view.
  useEffect(() => {
    void search().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section aria-label="Inference explorer">
      <h2>D3 · Inference explorer</h2>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <label>
          Model version
          <input value={modelVersion} onChange={(e) => setModelVersion(e.target.value)} />
        </label>
        <label>
          Label
          <input value={label} onChange={(e) => setLabel(e.target.value)} />
        </label>
        <button type="button" style={{ minHeight: 44 }} onClick={() => void search()}>
          Search
        </button>
      </div>
      <ul>
        {items.map((log) => (
          <li key={log.id}>
            event {log.event_id} · {log.model?.version ?? "?"} ·{" "}
            {log.predictions?.[0]?.label ?? "—"} ({log.predictions?.[0]?.confidence ?? "—"})
          </li>
        ))}
      </ul>
    </section>
  );
}
