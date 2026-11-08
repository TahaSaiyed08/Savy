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
    command: "cd .. && make dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
