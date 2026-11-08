type Identity = { brand?: string | null; item: string; variant?: string | null; size_qty?: number | null; size_unit?: string | null };

const trim = (n: number) => String(Math.round(n * 100) / 100);
const LB = 453.592;

/** Sizes are stored in ml/g/ea for comparing; this reads them back the way a shelf label does. */
export function displaySize(qty?: number | null, unit?: string | null) {
  if (!qty || !unit) return undefined;
  const u = unit.toLowerCase();
  if (u === "ml" && qty >= 1000) return `${trim(qty / 1000)} L`;
  if (u === "g" && qty >= 1000 && qty % 1000 === 0) return `${trim(qty / 1000)} kg`;
  if (u === "g" && Math.abs(qty / LB - Math.round(qty / LB)) < 0.01) return `${Math.round(qty / LB)} lb`;
  if (u === "g" && qty >= 1000) return `${trim(qty / 1000)} kg`;
  if (u === "l") return `${trim(qty)} L`;
  return `${trim(qty)} ${unit}`;
}

/** "Pampers · Size 7 · 17 ea", leaving out whatever is missing. */
export const itemMeta = (x: Identity) => [x.brand, x.variant, displaySize(x.size_qty, x.size_unit)].filter(Boolean).join(" · ");

export const fullName = (x: Identity) => [x.brand, x.item, x.variant].filter(Boolean).join(" ") || x.item;

const parse = (s: string) => new Date(`${s}T00:00:00`);

export function validRange(from?: string | null, to?: string | null) {
  if (!from || !to) return undefined;
  const fmt = (d: Date) => d.toLocaleDateString("en-CA", { month: "short", day: "numeric" });
  return `${fmt(parse(from))} – ${fmt(parse(to))}`;
}

export function daysLeft(to?: string | null) {
  if (!to) return undefined;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((parse(to).getTime() - today.getTime()) / 86_400_000);
}

export const weekday = (to: string) => parse(to).toLocaleDateString("en-CA", { weekday: "short" });

export const shortDate = (to: string) => parse(to).toLocaleDateString("en-CA", { month: "short", day: "numeric" });
