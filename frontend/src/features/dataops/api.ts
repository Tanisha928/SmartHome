/** Data ops API helpers — JSON goes through the shared apiClient (auth, refresh, errors). */

import { apiRequest, getAccessToken, refreshAccessToken } from "../../api/apiClient";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function fetchCsv(path: string, retried = false): Promise<string> {
  const headers = new Headers({ "X-Correlation-Id": crypto.randomUUID() });
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  if (resp.status === 401 && !retried && (await refreshAccessToken())) return fetchCsv(path, true);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw { status: resp.status, error: body.error, message: body.message ?? resp.statusText, details: body.details };
  }
  return resp.text();
}

function request<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, init);
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
    return fetchCsv(`/api/admin/audit?${params}`);
  },
  getRetention: () => request<import("./types").RetentionPolicy>("/api/admin/retention"),
  putRetention: (body: Partial<import("./types").RetentionPolicy>) =>
    request<import("./types").RetentionPolicy>("/api/admin/retention", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};
