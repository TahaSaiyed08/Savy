"use client";
import { useEffect, useState } from "react";
import { Moon, Sun } from "@/components/icons";
import { setForcedTheme } from "@/components/ForceTheme";

type Mode = "light" | "dark";

/** Light/dark switch. Starts from the saved choice, else the OS setting; persists via ForceTheme's storage key. */
export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>("light");
  useEffect(() => {
    const forced = document.documentElement.dataset.forceTheme;
    setMode(forced === "dark" || forced === "light" ? forced : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }, []);
  function toggle() {
    const next: Mode = mode === "dark" ? "light" : "dark";
    setMode(next);
    setForcedTheme(next);
  }
  return (
    <button type="button" onClick={toggle} aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"} className="flex h-11 min-w-[52px] items-center justify-center rounded-full text-label-2">
      {mode === "dark" ? <Sun size={22} /> : <Moon size={22} />}
    </button>
  );
}
