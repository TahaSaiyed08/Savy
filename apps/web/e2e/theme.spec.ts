import { expect, test } from "@playwright/test";

// The toggle lives in the header on all three tabs; it's the same stored override everywhere, so one flip
// shows up on every tab and survives a reload (localStorage persisted, re-applied before paint).
test("theme: toggling dark mode persists across tabs and a reload", async ({ page }) => {
  await page.goto("/list");
  const toggle = page.getByRole("button", { name: /^Switch to (dark|light) mode$/ });
  await expect(toggle).toHaveAttribute("aria-label", "Switch to dark mode");

  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-force-theme", "dark");
  await expect(toggle).toHaveAttribute("aria-label", "Switch to light mode");

  await page.getByRole("link", { name: "Basket" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-force-theme", "dark");
  await expect(page.getByRole("button", { name: "Switch to light mode" })).toBeVisible();

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-force-theme", "dark");

  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-force-theme", "light");
});

test("theme: an old dev-only override is migrated to the real setting on load", async ({ page }) => {
  await page.goto("/list");
  await page.evaluate(() => {
    localStorage.removeItem("realdeal.theme");
    localStorage.setItem("realdeal.dev.theme", "dark");
  });
  await page.reload();

  await expect(page.locator("html")).toHaveAttribute("data-force-theme", "dark");
  await expect(page.getByRole("button", { name: "Switch to light mode" })).toBeVisible();
  const [migrated, oldKeyGone] = await page.evaluate(() => [localStorage.getItem("realdeal.theme"), localStorage.getItem("realdeal.dev.theme")]);
  expect(migrated).toBe("dark");
  expect(oldKeyGone).toBeNull();
});
