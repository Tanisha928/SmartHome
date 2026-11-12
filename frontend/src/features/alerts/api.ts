import type {
  AlertDetail,
  AlertFilters,
  AlertPage,
  AlertStats,
  FalseAlertStat,
  NotificationPreference,
  Threshold,
} from "./types";
import { apiRequest, getAccessToken } from "../../api/apiClient";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(path, init);

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
  transition: (id: number, to_state: string, expected_state: string, note?: string) => {
    const headers = new Headers();
    if (import.meta.env.VITE_DEMO_MODE === "true" && localStorage.getItem("smarthome:demo-conflict") === "true") headers.set("X-Demo-Conflict", "true");
    return request(`/api/alerts/${id}/state`, { method: "PATCH", headers, body: JSON.stringify({ to_state, expected_state, note }) });
  },
  stats: (houseId?: number) => request<AlertStats>(`/api/stats/alerts${query({ house_id: houseId })}`),
  falseStats: (houseId?: number) =>
    request<{ items: FalseAlertStat[] }>(`/api/stats/false-alerts${query({ house_id: houseId })}`),
  savedViews: () => request<{ views: AlertFilters[] }>("/api/users/me/saved-views"),
  saveViews: (views: AlertFilters[]) => request<{ views: AlertFilters[] }>("/api/users/me/saved-views", { method: "PUT", body: JSON.stringify({ views }) }),
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
    const token = getAccessToken();
    const response = await fetch(alertsApi.exportUrl(format, houseId), {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      credentials: "include",
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
