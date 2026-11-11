// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, afterEach } from "vitest";
import { RouteGuard } from "./RouteGuard";
import { useAuthStore } from "../stores/authStore";
afterEach(() => useAuthStore.setState({ user: null }));
describe("RouteGuard", () => { it("redirects owners away from admin routes", () => { useAuthStore.setState({ user: { id: 2, email: "owner@example.com", role: "owner", house_ids: [1] } }); render(<MemoryRouter initialEntries={["/admin"]}><Routes><Route element={<RouteGuard role="admin" />}><Route path="/admin" element={<div>Admin</div>} /></Route><Route path="/owner" element={<div>Owner</div>} /></Routes></MemoryRouter>); expect(screen.getByText("Owner")).toBeTruthy(); }); });
