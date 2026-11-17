import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

async function login(page: Page, role: "admin" | "owner", path: string) {
  await page.goto(`/login?return=${encodeURIComponent(path)}`);
  await page.getByLabel("Email", { exact: true }).fill(`${role}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("password123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(path);
  await expect(page.getByText("Presentation workspace", { exact: true })).toHaveCount(0);
}

test("house and device registration persist submitted values", async ({ page }) => {
  await login(page, "admin", "/admin/devices");
  await page.getByLabel("Address", { exact: true }).fill("48 Acceptance Lane");
  await page.getByLabel("Postal code", { exact: true }).fill("98101");
  await page.getByRole("button", { name: "Add house", exact: true }).click();
  await expect(page.getByRole("list", { name: "House tree" })).toContainText("48 Acceptance Lane");
  await page.getByRole("combobox", { name: "House", exact: true }).selectOption("1");
  await page.getByRole("combobox", { name: "Room", exact: true }).selectOption("1");
  await page.getByLabel("Serial number", { exact: true }).fill("acceptance-sensor");
  await page.getByLabel("Label (optional)", { exact: true }).fill("Acceptance sensor");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Device key for Acceptance sensor" })).toBeVisible();
  await page.getByRole("button", { name: "I've saved it" }).click();
  await page.getByRole("link", { name: "Fleet", exact: true }).click();
  await expect(page.getByRole("row", { name: /Acceptance sensor/ })).toBeVisible();
});

test("device edits and disable state survive reopening the screen", async ({ page }) => {
  await login(page, "admin", "/admin/devices");
  await page.getByRole("button", { name: /Kitchen monitor.*Online/ }).click();
  await page.getByLabel("Label (optional)", { exact: true }).fill("Updated monitor");
  await page.getByRole("button", { name: "Update", exact: true }).click();
  await expect(page.getByRole("button", { name: /Updated monitor.*Online/ })).toBeVisible();
  await page.getByRole("button", { name: "Disable", exact: true }).click();
  await expect(page.getByRole("button", { name: "Enable", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Fleet", exact: true }).click();
  await page.getByRole("button", { name: "Disabled 1", exact: true }).click();
  await expect(page.getByRole("row", { name: /Updated monitor.*Disabled/ })).toBeVisible();
});

test("owner profile, preferences and capture state survive navigation", async ({ page }) => {
  await login(page, "owner", "/owner/profile");
  await expect(page.getByLabel("Name", { exact: true })).toBeEnabled();
  await page.getByLabel("Name", { exact: true }).fill("Acceptance Owner");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(page.getByText("Profile saved.", { exact: true })).toBeVisible();
  await page.getByRole("combobox").first().selectOption("critical");
  await page.getByRole("button", { name: "Save preferences", exact: true }).click();
  await expect(page.getByText("Preferences saved.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "My devices", exact: true }).click();
  await page.getByRole("switch").first().click();
  await expect(page.getByText("Listening turned off", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Acceptance Owner");
  await expect(page.getByRole("combobox").first()).toHaveValue("critical");
  await page.getByRole("link", { name: "My devices", exact: true }).click();
  await expect(page.getByRole("switch").first()).toHaveAttribute("aria-checked", "false");
});

test("retention rejects invalid ranges and retains a valid policy", async ({ page }) => {
  await login(page, "admin", "/admin/data/retention");
  await expect(page.getByLabel("Clip expire days")).toBeEnabled();
  await page.getByLabel("Clip expire days").fill("10");
  await page.getByLabel("IA transition days (optional)").fill("20");
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByRole("alert")).toContainText("earlier than recording expiry");
  await page.getByLabel("Clip expire days").fill("40");
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByText("Retention policy saved.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Health", exact: true }).click();
  await page.getByRole("link", { name: "Retention", exact: true }).click();
  await expect(page.getByLabel("Clip expire days")).toHaveValue("40");
});

test("pipeline state filters exclude failed events from scored and queued", async ({ page }) => {
  await login(page, "admin", "/admin/data/events");
  await page.getByRole("button", { name: "failed", exact: true }).click();
  await expect(page.getByRole("cell", { name: "failed", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "scored", exact: true }).click();
  await expect(page.getByRole("cell", { name: "failed", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "failed", exact: true }).click();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Retried event 1");
  await page.getByRole("button", { name: "queued", exact: true }).click();
  await expect(page.getByRole("cell", { name: "queued", exact: true })).toBeVisible();
});

test("PDF export downloads a complete PDF document", async ({ page }) => {
  await login(page, "admin", "/admin/history");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("alerts.pdf");
  const text = await readFile((await file.path())!, "utf8");
  expect(text.startsWith("%PDF-1.4")).toBe(true);
  expect(text.trimEnd().endsWith("%%EOF")).toBe(true);
});

test("owner profile fits a phone viewport without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "owner", "/owner/profile");
  await expect(page.getByRole("heading", { name: "Notification matrix" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
});
