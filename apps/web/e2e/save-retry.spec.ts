import { expect, test } from "@playwright/test";

// A failed POST /items must not lose the confirmed item: the sheet stays open with an inline
// "tap to retry" banner, and retrying (once the fault clears) actually saves it.
test("save retry: a failed save shows a retry banner, and retrying succeeds", async ({ page }) => {
  let postAttempts = 0;
  await page.route("**/api/items", async (route) => {
    if (route.request().method() === "POST") {
      postAttempts++;
      if (postAttempts === 1) {
        await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
        return;
      }
    }
    await route.continue();
  });

  await page.goto("/list");
  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Type or say it").click();

  await page.getByPlaceholder("e.g. a 4 L jug of 2% milk").fill("retry test item");
  await page.keyboard.press("Enter");

  const addToList = page.getByRole("button", { name: "Add to list" });
  await expect(addToList).toBeEnabled();
  await addToList.click();

  const retryBanner = page.getByText("Couldn't save — tap to retry");
  await expect(retryBanner).toBeVisible();

  await retryBanner.click();

  await expect(retryBanner).toHaveCount(0);
  await expect(page.getByText(/retry test item/i).first()).toBeVisible();
  expect(postAttempts).toBe(2);
});
