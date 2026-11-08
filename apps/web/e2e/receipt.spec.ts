import { expect, test } from "@playwright/test";

// Receipt scan -> confirm (low-confidence rows flagged) -> save -> appears in My List. Mock mode's
// MockExtractor returns the same canned extraction regardless of the actual image bytes.
test("receipt photo: scan, confirm, items land in My List", async ({ page }) => {
  await page.goto("/list");

  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Scan a receipt").click();

  await page.getByTestId("receipt-file-input").setInputFiles({
    name: "receipt.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("fake-receipt-bytes"),
  });

  await expect(page.getByText("CHECK THESE")).toBeVisible(); // oat milk, confidence 0.55
  await expect(page.getByText("LOOKS RIGHT")).toBeVisible();

  await page.getByRole("button", { name: /Save \d+ item/ }).click();

  await expect(page.getByText(/chicken thigh/i).first()).toBeVisible();
  await expect(page.getByText(/oat milk/i).first()).toBeVisible();
});
