"use client";
import { useEffect, useState } from "react";
import { getForcedTheme, setForcedTheme } from "@/components/ForceTheme";
import { Moon, Sun } from "@/components/icons";

/** Light/dark switch for the header. Before the first tap it just reflects the OS setting (and keeps
 * tracking it live, via the media query); after a tap it's an explicit override, same storage ForceTheme
 * and /dev/states already use. */
export function ThemeToggle() {
  const [dark, setDark] = useState(false); // SSR-safe default; corrected on mount below

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const recompute = () => {
      const forced = getForcedTheme();
      setDark(forced === "system" ? mq.matches : forced === "dark");
    };
    recompute();
    mq.addEventListener("change", recompute);
    return () => mq.removeEventListener("change", recompute);
  }, []);

  function toggle() {
    const next = dark ? "light" : "dark";
    setForcedTheme(next);
    setDark(!dark);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex size-11 items-center justify-center rounded-full border border-separator bg-bg text-tint transition-transform active:scale-95"
    >
      {dark ? <Moon size={21} /> : <Sun size={22} />}
    </button>
  );
}
