/** Stable color per store (--store-N in globals.css), so the same chain always gets the same dot. */
export function storeColorVar(store?: string | null): string {
  const s = (store ?? "").toLowerCase();
  if (!s) return "var(--label-2)";
  const n = s.includes("safeway") ? 1 : s.includes("save-on") || s.includes("save on") ? 2 : s.includes("no frills") ? 3 : s.includes("walmart") ? 4 : s.includes("freshco") ? 5 : 1 + ([...s].reduce((a, c) => a + c.charCodeAt(0), 0) % 5);
  return `var(--store-${n})`;
}
