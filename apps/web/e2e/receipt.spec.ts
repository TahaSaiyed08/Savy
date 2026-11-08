import { expect, test } from "@playwright/test";

// Receipt scan -> confirm (low-confidence rows flagged) -> save -> appears in Pantry. Mock mode's
// MockExtractor returns the same canned extraction regardless of the actual image bytes.
test("receipt photo: scan, confirm, items land in Pantry", async ({ page }) => {
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

// The confirm screen shows, under each line, the cheapest similar item on sale now (a receipt rarely has the brand or
// size a flyer prints, so it looks at the product name), and fresh produce arrives without a size or quantity.
test("receipt photo: lines show similar deals, and produce keeps no quantity", async ({ page }) => {
  await page.goto("/list");
  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Scan a receipt").click();
  await page.getByTestId("receipt-file-input").setInputFiles({
    name: "receipt.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("\xff\xd8\xfffake-receipt-bytes", "latin1"),
  });
  await expect(page.getByText("LOOKS RIGHT")).toBeVisible();

  // The canned flyers carry chicken thigh, banana and eggs, and no oat milk, so exactly those three lines get a deal.
  await expect(page.getByText(/^On sale: .*chicken thigh/i)).toBeVisible();
  await expect(page.getByText(/^On sale: .*banana/i)).toBeVisible();
  await expect(page.getByText(/^On sale: .*egg/i)).toBeVisible();
  await expect(page.getByText(/^On sale:/)).toHaveCount(3);

  // Each row's accessible name is its label then its deal: produce has no "· 1 lb", meat keeps its "· 1 kg".
  await expect(page.getByRole("button", { name: /^banana On sale:/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^PC chicken thigh boneless · 1 kg On sale:/ })).toBeVisible();
});
