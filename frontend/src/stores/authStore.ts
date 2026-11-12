import { create } from "zustand";
import { api, setAccessToken, type User } from "../api/apiClient";

type AuthState = { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<User>; signup: (body: { email: string; password: string; full_name: string; phone?: string }) => Promise<User>; logout: () => Promise<void> };

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: false,
  login: async (email, password) => { set({ loading: true }); try { const result = await api.login(email, password); setAccessToken(result.access_token); set({ user: result.user }); return result.user; } finally { set({ loading: false }); } },
  signup: async (body) => { set({ loading: true }); try { await api.signup(body); const result = await api.login(body.email, body.password); setAccessToken(result.access_token); set({ user: result.user }); return result.user; } finally { set({ loading: false }); } },
  logout: async () => { await api.logout().catch(() => undefined); setAccessToken(null); set({ user: null }); },
}));
