import { expect, test } from "@playwright/test";

// The app's service worker takes over after the first load, and requests it handles skip Playwright's mocks.
test.use({ serviceWorkers: "block" });

test("basket: Done moves a row to the Done section and it stays in Pantry", async ({ page }) => {
  await page.goto("/basket");
  await expect(page.getByText(/^To get \(\d+\)$/i)).toBeVisible();

  await page.getByRole("button", { name: /^Mark done:.*ramen/i }).click();
  await expect(page.getByText(/^Done \(1\)$/i)).toBeVisible();

  await page.getByRole("link", { name: "Pantry" }).click();
  await expect(page.getByText(/^ramen$/i)).toBeVisible();
});

test("flyers: + adds the listing to Pantry and marks the row added", async ({ page }) => {
  await page.goto("/flyers");
  const add = page.getByRole("button", { name: /^Add .* to pantry$/ }).first();
  const label = (await add.getAttribute("aria-label"))!.replace(/^Add /, "").replace(/ to pantry$/, "");
  await add.click();
  await expect(page.getByRole("button", { name: `${label} is in your pantry` })).toBeVisible();
});

test("flyers: tapping a row opens Price Match with the valid dates", async ({ page }) => {
  await page.goto("/flyers");
  await page.locator("li button").first().click();
  await expect(page.getByRole("heading", { name: "Price match" })).toBeVisible();
  await expect(page.getByText(/^Valid /)).toBeVisible();
  await page.getByRole("button", { name: "Flyers" }).click();
  await expect(page.getByRole("heading", { name: "Price match" })).toHaveCount(0);
});

test("flyers: changing the postal code sends it with every request and shows it", async ({ page }) => {
  await page.goto("/flyers");
  await page.getByRole("button", { name: "Change flyer location" }).click();
  await page.getByPlaceholder("V6T 1Z4").fill("m5v 2t6");

  const asked = page.waitForRequest((r) => r.url().includes("/api/flyer-items") && r.headers()["x-postal-code"] === "M5V2T6");
  await page.getByRole("button", { name: "Show flyers near here" }).click();
  await asked;
  await expect(page.getByRole("button", { name: "Change flyer location" })).toContainText("M5V 2T6");
});

test("flyers: a bad postal code is refused before anything is sent", async ({ page }) => {
  await page.goto("/flyers");
  await page.getByRole("button", { name: "Change flyer location" }).click();
  await page.getByPlaceholder("V6T 1Z4").fill("12345");
  await page.getByRole("button", { name: "Show flyers near here" }).click();
  await expect(page.getByText(/Enter a postal code like/i)).toBeVisible();
});

test("add item: typing shows this week's flyer products, and picking one adds it with its price", async ({ page }) => {
  await page.goto("/list");
  const priced = page.getByLabel(/^On sale, /);
  await expect(priced.first()).toBeVisible();
  const before = await priced.count();

  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Type or say it").click();
  await page.getByPlaceholder("e.g. a 4 L jug of 2% milk").fill("milk");

  const flyers = page.getByLabel("From this week's flyers");
  await expect(flyers).toBeVisible();
  await flyers.getByRole("button").first().click();

  await expect(page.getByText("Type or say it")).toHaveCount(0); // sheet closed once saved
  await expect(priced).toHaveCount(before + 1); // the added product is the exact flyer listing, so it has a price
});

test("add item: words that match nothing can still be added as typed", async ({ page }) => {
  await page.goto("/list");
  await page.getByRole("button", { name: "Add item" }).click();
  await page.getByText("Type or say it").click();
  await page.getByPlaceholder("e.g. a 4 L jug of 2% milk").fill("zzzzqq");
  await page.getByRole("button", { name: /Add .zzzzqq. as typed/ }).click();
  await page.getByRole("button", { name: "Add to list" }).click();
  await expect(page.getByText("zzzzqq").first()).toBeVisible();
});

test("price match: links to the store's own page, and nothing links to the flyer source", async ({ page }) => {
  await page.route("**/api/flyer-items**", async (route) => {
    const body = await (await route.fetch()).json();
    Object.assign(body.items[0].cheapest, { store_url: "https://www.nofrills.ca/p/20921434001_EA" });
    await route.fulfill({ json: body });
  });
  await page.goto("/flyers");
  await page.locator("li button").first().click();

  const screen = page.getByRole("heading", { name: "Price match" }).locator("../..");
  const original = screen.getByRole("link", { name: /Original flyer/ });
  await expect(original).toHaveAttribute("href", "https://www.nofrills.ca/p/20921434001_EA");
  await expect(original).toHaveAttribute("target", "_blank");
  await expect(original).toHaveAttribute("rel", /noopener/);
  await expect(page.locator('a[href*="flipp"]')).toHaveCount(0);
});

test("price match: no Original flyer link when the store has no page for the item", async ({ page }) => {
  await page.route("**/api/flyer-items**", async (route) => {
    const body = await (await route.fetch()).json();
    for (const g of body.items) Object.assign(g.cheapest, { store_url: null });
    await route.fulfill({ json: body });
  });
  await page.goto("/flyers");
  await page.locator("li button").first().click();
  await expect(page.getByRole("heading", { name: "Price match" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Original flyer/ })).toHaveCount(0);
  await expect(page.locator('a[href*="flipp"]')).toHaveCount(0);
});

test("flyers: tapping a row's image opens Price Match in the app", async ({ page }) => {
  await page.goto("/flyers");
  await expect(page.locator('a[href*="flipp"]')).toHaveCount(0);
  await page.locator("li button").first().click({ position: { x: 30, y: 30 } }); // over the thumbnail
  await expect(page.getByRole("heading", { name: "Price match" })).toBeVisible();
  expect(page.context().pages()).toHaveLength(1);
});

test("ask: the Ask button only appears when Genie is set up, and shows its answer and table", async ({ page }) => {
  await page.goto("/flyers");
  await expect(page.getByRole("button", { name: "Change flyer location" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask about deals" })).toHaveCount(0); // not set up: no dead button

  // Pretend Genie is ready and answers, so this runs the same everywhere (CI has no Databricks).
  await page.route("**/api/flyers/status", async (route) => {
    const body = await (await route.fetch()).json();
    await route.fulfill({ json: { ...body, ask_enabled: true } });
  });
  let sent: { question: string; conversation_id?: string | null } | undefined;
  await page.route("**/api/ask", async (route) => {
    sent = route.request().postDataJSON();
    await route.fulfill({
      json: {
        conversation_id: "conv-1",
        answer: "Safeway has the cheapest milk at $5.99.",
        sql: "SELECT store, price FROM live_listings",
        columns: ["store", "price"],
        rows: [["Safeway", "5.99"], ["No Frills", null]],
      },
    });
  });
  await page.goto("/flyers");
  await page.getByRole("button", { name: "Ask about deals" }).click();
  await page.getByRole("button", { name: "Which store has the cheapest eggs?" }).click();

  await expect(page.getByText("Safeway has the cheapest milk at $5.99.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "5.99" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "—" })).toBeVisible();
  expect(sent?.question).toBe("Which store has the cheapest eggs?");

  await page.getByLabel("Ask about this week's deals").fill("and bread?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect.poll(() => sent?.conversation_id).toBe("conv-1"); // a follow-up stays in the same conversation
});

test("ask: a failed question says so and can be asked again", async ({ page }) => {
  await page.route("**/api/flyers/status", async (route) => {
    const body = await (await route.fetch()).json();
    await route.fulfill({ json: { ...body, ask_enabled: true } });
  });
  await page.route("**/api/ask", (route) => route.fulfill({ status: 502, json: { detail: "Genie took too long. Try again in a moment." } }));
  await page.goto("/flyers");
  await page.getByRole("button", { name: "Ask about deals" }).click();
  await page.getByLabel("Ask about this week's deals").fill("cheapest milk?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Genie took too long. Try again in a moment.")).toBeVisible();
});

test("flyers: category chips filter the list through the API", async ({ page }) => {
  const asked: (string | null)[] = [];
  await page.route("**/api/flyer-items**", async (route) => {
    const url = new URL(route.request().url());
    asked.push(url.searchParams.get("category"));
    try {
      const body = await (await route.fetch()).json();
      body.categories = ["Dairy & eggs", "Produce"];
      await route.fulfill({ json: body });
    } catch {
      // the test ended while this request was still on its way
    }
  });
  await page.goto("/flyers");
  const chips = page.getByRole("group", { name: "Categories" });
  await expect(chips.getByRole("button", { name: "Everything" })).toHaveAttribute("aria-pressed", "true");

  await chips.getByRole("button", { name: "Dairy & eggs" }).click();
  await expect(chips.getByRole("button", { name: "Dairy & eggs" })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => asked.at(-1)).toBe("Dairy & eggs");

  await chips.getByRole("button", { name: "Everything" }).click();
  await expect.poll(() => asked.at(-1)).toBeNull();
});

test("flyers: no category chips until the AI has labelled something", async ({ page }) => {
  await page.goto("/flyers");
  await expect(page.getByRole("button", { name: "Change flyer location" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Categories" })).toHaveCount(0);
});
