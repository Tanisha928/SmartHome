/** Data ops API helpers — uses shared apiClient once Mithil lands it. */

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("X-Correlation-Id", crypto.randomUUID());
  const token = sessionStorage.getItem("access_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw Object.assign(new Error(body.message ?? resp.statusText), {
      status: resp.status,
      error: body.error,
      details: body.details,
    });
  }
  if (resp.headers.get("content-type")?.includes("text/csv")) {
    return (await resp.text()) as T;
  }
  return resp.json() as Promise<T>;
}

export const dataOpsApi = {
  health: () => request<import("./types").HealthSnapshot>("/api/admin/data/health"),
  events: (params: URLSearchParams) =>
    request<{ items: import("./types").PipelineEvent[]; total: number }>(
      `/api/admin/events?${params}`,
    ),
  retry: (eventId: number) =>
    request<{ event_id: number; processing_state: string }>(
      `/api/admin/events/${eventId}/retry`,
      { method: "POST" },
    ),
  inferenceLogs: (params: URLSearchParams) =>
    request<{ items: import("./types").InferenceLog[]; total: number }>(
      `/api/admin/inference-logs?${params}`,
    ),
  audit: (params: URLSearchParams) =>
    request<{ items: import("./types").AuditRow[]; total: number }>(
      `/api/admin/audit?${params}`,
    ),
  auditCsv: (params: URLSearchParams) => {
    params.set("export", "csv");
    return request<string>(`/api/admin/audit?${params}`);
  },
  getRetention: () => request<import("./types").RetentionPolicy>("/api/admin/retention"),
  putRetention: (body: Partial<import("./types").RetentionPolicy>) =>
    request<import("./types").RetentionPolicy>("/api/admin/retention", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};
