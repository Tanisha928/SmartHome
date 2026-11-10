import { useState } from "react";
import { dataOpsApi } from "./api";
import type { AuditRow } from "./types";

export function AuditLog() {
  const [items, setItems] = useState<AuditRow[]>([]);

  const load = async () => {
    const data = await dataOpsApi.audit(new URLSearchParams({ page: "1", page_size: "50" }));
    setItems(data.items);
  };

  const exportCsv = async () => {
    const csv = await dataOpsApi.auditCsv(new URLSearchParams({ page: "1", page_size: "100" }));
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section aria-label="Audit log">
      <h2>D4 · Audit log</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button type="button" style={{ minHeight: 44 }} onClick={() => void load()}>
          Load
        </button>
        <button type="button" style={{ minHeight: 44 }} onClick={() => void exportCsv()}>
          Export CSV
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Actor</th>
            <th>House</th>
            <th>Action</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.audit_id}>
              <td>{row.audit_id}</td>
              <td>{row.actor_user_id}</td>
              <td>{row.house_id ?? "—"}</td>
              <td>{row.action}</td>
              <td>{row.ts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
