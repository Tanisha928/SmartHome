// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataView } from "./DataView";

describe("DataView", () => {
  it("renders loading, empty, error and stale states", () => {
    const { rerender } = render(<DataView loading>content</DataView>);
    expect(screen.getByRole("status")).toBeTruthy();
    rerender(<DataView empty>content</DataView>);
    expect(screen.getByText("No data yet")).toBeTruthy();
    rerender(<DataView error={{ message: "No access", correlationId: "c-1" }} onRetry={() => undefined}>content</DataView>);
    expect(screen.getByRole("alert").textContent).toContain("c-1");
    rerender(<DataView staleAt={new Date("2026-01-01T00:00:00Z")}>content</DataView>);
    expect(screen.getByText(/Showing data from/)).toBeTruthy();
  });
});
