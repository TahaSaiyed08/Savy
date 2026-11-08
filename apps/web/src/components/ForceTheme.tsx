"use client";
import { useEffect } from "react";

const KEY = "realdeal.dev.theme";

/** Applies a dev-only light/dark override (set via /dev/states) on every page so it survives navigation. */
export function ForceTheme() {
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "light" || saved === "dark") document.documentElement.dataset.forceTheme = saved;
    } catch {
      // ignore
    }
  }, []);
  return null;
}

export function setForcedTheme(theme: "light" | "dark" | "system") {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // ignore
  }
  if (theme === "system") delete document.documentElement.dataset.forceTheme;
  else document.documentElement.dataset.forceTheme = theme;
}

export function getForcedTheme(): "light" | "dark" | "system" {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // ignore
  }
  return "system";
}
