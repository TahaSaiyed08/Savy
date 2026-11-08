import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests for pure lib functions (src/lib/*). End-to-end coverage lives in e2e/ (Playwright).
// css.postcss: {} — these tests never import styles, and Vite otherwise tries to auto-discover and load
// the project's postcss.config.mjs (Next.js's string-plugin-name format, which Vite's own loader rejects).
export default defineConfig({
  css: { postcss: { plugins: [] } },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } }, // same "@/" as tsconfig paths
  test: {
    include: ["src/**/*.test.ts"],
    exclude: ["e2e/**"],
  },
});
