export type ApiError = { status: number; error: string; message: string; correlationId: string };

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";
let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) { accessToken = token; }
export function getAccessToken() { return accessToken; }

function correlationId() { return crypto.randomUUID(); }

async function refresh(): Promise<string | null> {
  const response = await fetch(`${API_BASE}/api/auth/refresh`, { method: "POST", credentials: "include", headers: { "X-Correlation-Id": correlationId() } });
  if (!response.ok) return null;
  const body = await response.json() as { access_token: string };
  accessToken = body.access_token;
  return accessToken;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  if (DEMO_MODE) return demoRequest<T>(path, init);
  const id = correlationId();
  const headers = new Headers(init.headers);
  headers.set("X-Correlation-Id", id);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && !retried) {
    refreshPromise ??= refresh().finally(() => { refreshPromise = null; });
    if (await refreshPromise) return apiRequest<T>(path, init, true);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as Partial<ApiError>;
    throw { status: response.status, error: body.error ?? "request_failed", message: body.message ?? response.statusText, correlationId: body.correlationId ?? id } satisfies ApiError;
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function demoRequest<T>(path: string, init: RequestInit): Promise<T> {
  const { demoAlerts, demoPage, demoStats } = await import("../demo/fixtures");
  if (path === "/api/auth/login") return { access_token: "demo-token", user: { id: 1, email: "admin@example.com", full_name: "Demo Admin", role: "admin", house_ids: [1] } } as T;
  if (path === "/api/auth/signup") return { id: 2, email: "owner@example.com", full_name: "Demo Owner", role: "owner", house_ids: [] } as T;
  if (path === "/api/users/me") return { id: 1, email: "admin@example.com", full_name: "Demo Admin", role: "admin", house_ids: [1] } as T;
  if (path.startsWith("/api/alerts") && init.method === "PATCH") return demoAlerts[0] as T;
  if (path.startsWith("/api/alerts")) return demoPage as T;
  if (path.startsWith("/api/stats/alerts")) return demoStats as T;
  return {} as T;
}

export const api = {
  login: (email: string, password: string) => apiRequest<{ access_token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  signup: (body: { email: string; password: string; full_name: string; phone?: string }) => apiRequest<User>("/api/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  logout: () => apiRequest<void>("/api/auth/logout", { method: "POST" }),
  me: () => apiRequest<User>("/api/users/me"),
};

export type User = { id: number; email: string; full_name?: string; role: "admin" | "owner"; house_ids: number[] };
