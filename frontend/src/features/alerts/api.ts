import type {
  AlertDetail,
  AlertFilters,
  AlertPage,
  AlertStats,
  FalseAlertStat,
  NotificationPreference,
  Threshold,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("X-Correlation-Id", crypto.randomUUID());
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = sessionStorage.getItem("access_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { message?: string };
    throw new Error(body.message ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

function query(params: Record<string, string | number | undefined>): string {
  const values = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") values.set(key, String(value));
  });
  const result = values.toString();
  return result ? `?${result}` : "";
}

export const alertsApi = {
  list: (filters: AlertFilters = {}) =>
    request<AlertPage>(`/api/alerts${query({ ...filters, page: 1, page_size: 100 })}`),
  detail: (id: number) => request<AlertDetail>(`/api/alerts/${id}`),
  transition: (id: number, to_state: string, expected_state: string, note?: string) =>
    request(`/api/alerts/${id}/state`, {
      method: "PATCH",
      body: JSON.stringify({ to_state, expected_state, note }),
    }),
  stats: (houseId?: number) => request<AlertStats>(`/api/stats/alerts${query({ house_id: houseId })}`),
  falseStats: (houseId?: number) =>
    request<{ items: FalseAlertStat[] }>(`/api/stats/false-alerts${query({ house_id: houseId })}`),
  preferences: (houseId: number) =>
    request<{ house_id: number; items: NotificationPreference[] }>(`/api/notification-prefs${query({ house_id: houseId })}`),
  savePreferences: (houseId: number, items: NotificationPreference[]) =>
    request<{ house_id: number; items: NotificationPreference[] }>(`/api/notification-prefs${query({ house_id: houseId })}`, {
      method: "PUT",
      body: JSON.stringify(items),
    }),
  thresholds: () => request<{ items: Threshold[] }>("/api/admin/thresholds"),
  saveThreshold: (threshold: Omit<Threshold, "id">) =>
    request<Threshold>("/api/admin/thresholds", { method: "PUT", body: JSON.stringify(threshold) }),
  exportUrl: (format: "csv" | "pdf", houseId?: number) =>
    `${API_BASE}/api/alerts/export${query({ format, house_id: houseId })}`,
  downloadExport: async (format: "csv" | "pdf", houseId?: number) => {
    const token = sessionStorage.getItem("access_token");
    const response = await fetch(alertsApi.exportUrl(format, houseId), {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) throw new Error("Unable to download alert export.");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = format === "csv" ? "alerts.csv" : "alerts.pdf";
    link.click();
    URL.revokeObjectURL(url);
  },
};
