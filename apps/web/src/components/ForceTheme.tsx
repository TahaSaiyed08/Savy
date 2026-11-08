"use client";
import { useEffect } from "react";

const KEY = "realdeal.theme";
const OLD_KEY = "realdeal.dev.theme"; // pre-ThemeToggle dev-only key; migrated once below

/** Reads the stored override, migrating the old dev-only key to the new one if that's all there is.
 * Pure localStorage access — no `document` — so it's test-friendly on its own. */
function readAndMigrate(): "light" | "dark" | null {
  try {
    const current = localStorage.getItem(KEY);
    if (current === "light" || current === "dark") return current;
    const old = localStorage.getItem(OLD_KEY);
    localStorage.removeItem(OLD_KEY);
    if (old === "light" || old === "dark") {
      localStorage.setItem(KEY, old);
      return old;
    }
  } catch {
    // private mode or storage disabled: behave as "system"
  }
  return null;
}

/** Applies the saved light/dark override (if any) on every page so it survives navigation, and keeps the
 * PWA status bar color in sync. A real user-facing setting now (ThemeToggle), not just /dev/states —
 * layout.tsx's inline script already set the DOM attribute before paint; this just keeps it correct
 * post-hydration (e.g. after the one-time key migration) and syncs theme-color. */
export function ForceTheme() {
  useEffect(() => {
    const saved = readAndMigrate();
    if (saved) document.documentElement.dataset.forceTheme = saved;
    syncThemeColor(saved ?? "system");
  }, []);
  return null;
}

export function setForcedTheme(theme: "light" | "dark" | "system") {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // ignore: private mode or storage disabled
  }
  if (typeof document !== "undefined") {
    if (theme === "system") delete document.documentElement.dataset.forceTheme;
    else document.documentElement.dataset.forceTheme = theme;
  }
  syncThemeColor(theme);
}

export function getForcedTheme(): "light" | "dark" | "system" {
  return readAndMigrate() ?? "system";
}

/** Keeps <meta name="theme-color"> (the PWA/Safari status bar color) matching the active theme. The two
 * tags from layout.tsx's `viewport.themeColor` are each scoped to a `prefers-color-scheme` media query,
 * which a forced override bypasses entirely — so this sets both tags' content directly. Back on "system",
 * each tag is restored to its own natural color and native media-query matching takes over again. */
export function syncThemeColor(theme: "light" | "dark" | "system") {
  if (typeof document === "undefined") return;
  document.querySelectorAll('meta[name="theme-color"]').forEach((el) => {
    const isDarkTag = (el.getAttribute("media") || "").includes("dark");
    const effectiveDark = theme === "system" ? isDarkTag : theme === "dark";
    el.setAttribute("content", effectiveDark ? "#000000" : "#f2f2f7");
  });
}
