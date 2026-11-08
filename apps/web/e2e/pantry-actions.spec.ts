import { expect, test } from "@playwright/test";

// Pantry = every item ever added; Basket = only the items explicitly moved there. A manually-typed item
// starts out of the Basket, so this adds one, moves it in via the swipe action, and confirms it shows up
// on the Basket tab (as "no deal this week", since an arbitrary string won't match any flyer item).
test("pantry: move an item to Basket, it shows up on the Basket tab", async ({ page }) => {
  await page.goto("/list");

  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Type or say it").click();
  await page.getByPlaceholder("e.g. a 4 L jug of 2% milk").fill("zzz basket test item");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Add to list" }).click();

  await expect(page.getByText(/zzz basket test item/i).first()).toBeVisible();

  await page.getByRole("button", { name: /^Move to Basket:.*zzz basket test item/i }).dispatchEvent("click");

  await page.getByRole("link", { name: "Basket" }).click();
  await expect(page.getByText(/zzz basket test item/i).first()).toBeVisible();
});

test("pantry: editing an item's name updates it in place", async ({ page }) => {
  await page.goto("/list");

  const row = page.getByText(/^ramen$/i);
  await expect(row).toBeVisible();

  await page.getByRole("button", { name: /^Edit:.*ramen/i }).dispatchEvent("click");
  await expect(page.getByText("Edit item")).toBeVisible();

  const itemField = page.getByLabel("Item", { exact: true });
  await itemField.fill("instant ramen noodles");
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(page.getByText(/^ramen$/i)).toHaveCount(0);
  await expect(page.getByText(/instant ramen noodles/i).first()).toBeVisible();
});
