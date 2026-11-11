// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, setAccessToken } from "./apiClient";

const response = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => { vi.unstubAllGlobals(); setAccessToken(null); });

describe("apiRequest", () => {
  it("refreshes once and retries a 401 with the new bearer token", async () => {
    const calls: RequestInit[] = [];
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      calls.push(init ?? {});
      if (calls.length === 1) return response(401, { error: "unauthenticated", message: "expired" });
      if (calls.length === 2) return response(200, { access_token: "fresh-token" });
      return response(200, { ok: true });
    }));
    setAccessToken("old-token");
    await expect(apiRequest<{ ok: boolean }>("/api/private")).resolves.toEqual({ ok: true });
    expect(calls).toHaveLength(3);
    expect(new Headers(calls[2].headers).get("Authorization")).toBe("Bearer fresh-token");
  });

  it("normalizes a forbidden response with its correlation id", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response(403, { error: "scope_violation", message: "Not your house" })));
    await expect(apiRequest("/api/private")).rejects.toMatchObject({ status: 403, error: "scope_violation", message: "Not your house" });
  });
});
