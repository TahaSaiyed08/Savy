import { defineConfig, devices } from "@playwright/test";

// Plan.md step 9 (WS3): one smoke test — open the PWA, add an item manually, see it in Deals.
// Runs against mock mode (`make dev`), same as the rest of frontend dev.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "cd ../.. && make dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    // Verified: exported vars override uv's --env-file, so this forces mock mode even if .env sets
    // DATABRICKS_HOST (CI's .env is just `touch`ed empty, but this makes the override explicit either way).
    env: { REALDEAL_MOCK: "1", EXTRACTOR: "mock", REALDEAL_LIVE_FLYERS: "0" }, // canned flyers: no network, fixed prices
  },
});
