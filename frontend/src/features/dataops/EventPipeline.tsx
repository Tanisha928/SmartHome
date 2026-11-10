import { useState } from "react";
import { dataOpsApi } from "./api";
import type { PipelineEvent } from "./types";

const STATES = ["queued", "scored", "failed"] as const;

export function EventPipeline() {
  const [state, setState] = useState<(typeof STATES)[number]>("queued");
  const [items, setItems] = useState<PipelineEvent[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const load = async (next = state) => {
    const params = new URLSearchParams({ state: next, page: "1", page_size: "25" });
    const data = await dataOpsApi.events(params);
    setItems(data.items);
  };

  const retry = async (eventId: number) => {
    try {
      await dataOpsApi.retry(eventId);
      setMessage(`Retried event ${eventId}`);
      await load();
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string };
      if (e.status === 409) setMessage("Already scored");
      else setMessage(e.message ?? "Retry failed");
    }
  };

  return (
    <section aria-label="Event pipeline">
      <h2>D2 · Event pipeline</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        {STATES.map((s) => (
          <button
            key={s}
            type="button"
            style={{ minHeight: 44, padding: "0 1rem" }}
            aria-pressed={state === s}
            onClick={() => {
              setState(s);
              void load(s);
            }}
          >
            {s}
          </button>
        ))}
        <button type="button" style={{ minHeight: 44 }} onClick={() => void load()}>
          Refresh
        </button>
      </div>
      {message && <p role="status">{message}</p>}
      <table>
        <thead>
          <tr>
            <th>Event</th>
            <th>House</th>
            <th>State</th>
            <th>Retries</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((ev) => (
            <tr key={ev.event_id}>
              <td>{ev.event_id}</td>
              <td>{ev.house_id}</td>
              <td>{ev.processing_state}</td>
              <td>{ev.retry_count}</td>
              <td>
                {ev.processing_state !== "scored" && (
                  <button type="button" style={{ minHeight: 44 }} onClick={() => void retry(ev.event_id)}>
                    Retry
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
