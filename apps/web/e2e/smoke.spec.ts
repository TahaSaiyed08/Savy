import { expect, test } from "@playwright/test";

// Plan.md WS3 step 9: open the PWA, add an item manually, see it in Deals. Runs in mock mode.
test("add an item manually and see it matched in Deals", async ({ page }) => {
  await page.goto("/list");

  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Type or say it").click();

  await page.getByPlaceholder("e.g. a 4 L jug of 2% milk").fill("olive oil");
  await page.keyboard.press("Enter");

  const addToList = page.getByRole("button", { name: "Add to list" });
  await expect(addToList).toBeEnabled();
  await addToList.click();

  await expect(page.getByText("olive oil", { exact: true }).first()).toBeVisible();

  await page.getByRole("link", { name: "Deals" }).click();
  await expect(page.getByText(/olive oil/i).first()).toBeVisible();
});
