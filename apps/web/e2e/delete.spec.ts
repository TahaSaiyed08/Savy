import { expect, test } from "@playwright/test";

// A fresh device always seeds a typed "ramen" (mock_data.py). The delete button sits behind the row, so the click is
// dispatched directly. The row goes at once; the DELETE follows when the 4 s undo window closes.
test("delete: the row disappears at once and DELETE follows after the undo window", async ({ page }) => {
  await page.goto("/list");

  const row = page.getByText(/^ramen$/i);
  await expect(row).toBeVisible();

  const deleted = page.waitForRequest((r) => r.method() === "DELETE" && r.url().includes("/items/"), { timeout: 7000 });
  await page.getByRole("button", { name: /^Delete:.*ramen/i }).dispatchEvent("click");

  await expect(row).toHaveCount(0);
  await deleted;
});

test("delete: Undo brings the row back and sends no DELETE", async ({ page }) => {
  await page.goto("/list");

  const row = page.getByText(/^ramen$/i);
  await expect(row).toBeVisible();
  let deletes = 0;
  page.on("request", (r) => {
    if (r.method() === "DELETE") deletes++;
  });

  await page.getByRole("button", { name: /^Delete:.*ramen/i }).dispatchEvent("click");
  await page.getByRole("button", { name: "Undo" }).click();

  await expect(row).toBeVisible();
  await page.waitForTimeout(4500);
  expect(deletes).toBe(0);
});
