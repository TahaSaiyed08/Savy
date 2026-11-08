import { expect, test } from "@playwright/test";

// Product photo -> "Which one is it?" chip picker over the extractor's candidates -> add -> in My List.
test("product photo: pick a candidate, add to My List", async ({ page }) => {
  await page.goto("/list");

  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Photo of a product").click();

  await page.getByTestId("photo-file-input").setInputFiles({
    name: "product.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("fake-product-bytes"),
  });

  await expect(page.getByText("Which one is it?")).toBeVisible();
  await expect(page.getByText(/olive oil/i).first()).toBeVisible(); // the default-picked candidate

  await page.getByRole("button", { name: "Add to list" }).click();

  await expect(page.getByText(/olive oil/i).first()).toBeVisible();
});
