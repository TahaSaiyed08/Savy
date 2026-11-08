// Where the shopper is, as a Canadian postal code. Flyers and their prices are local, so this goes to the API in an
// X-Postal-Code header on every request. Unset means the API's own default.
const KEY = "realdeal.postal";

/** "v6t 1z4" -> "V6T1Z4"; null when it isn't a postal code. */
export function normalizePostal(raw: string): string | null {
  const code = raw.replace(/[\s-]/g, "").toUpperCase();
  return /^[A-Z]\d[A-Z]\d[A-Z]\d$/.test(code) ? code : null;
}

/** "V6T1Z4" -> "V6T 1Z4" */
export const formatPostal = (code: string) => (code.length === 6 ? `${code.slice(0, 3)} ${code.slice(3)}` : code);

export function getPostal(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return (globalThis as { __rdPostal?: string }).__rdPostal ?? null; // private mode: this visit only
  }
}

export function setPostal(code: string) {
  try {
    localStorage.setItem(KEY, code);
  } catch {
    (globalThis as { __rdPostal?: string }).__rdPostal = code;
  }
}
