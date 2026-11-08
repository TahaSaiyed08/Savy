import { expect, test } from "@playwright/test";

// A fresh device seeds 5 demo items (mock_data.py SEED_ITEMS), "banana" among them. ListRow's delete
// button sits behind the row, genuinely covered until swiped open — dispatching the click event
// directly exercises the real DELETE call without simulating the full drag gesture or its z-order.
test("delete: removing a row calls DELETE and it disappears from My List", async ({ page }) => {
  await page.goto("/list");

  const bananaRow = page.getByText(/^banana$/i);
  await expect(bananaRow).toBeVisible();

  await page.getByRole("button", { name: /^Delete .*banana/i }).dispatchEvent("click");

  await expect(bananaRow).toHaveCount(0);
});
