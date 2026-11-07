// No login: one UUID per device, created on first open, sent as X-User-Id.
// A judge's phone is a fresh user.
const KEY = "realdeal.user_id";

function uuid(): string {
  // crypto.randomUUID needs a secure context; a phone hitting http://<laptop-ip>:3000 is not one.
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function userId(): string {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) localStorage.setItem(KEY, (id = uuid()));
    return id;
  } catch {
    return (globalThis as { __rdUser?: string }).__rdUser ??= uuid(); // private mode: per-session id
  }
}
