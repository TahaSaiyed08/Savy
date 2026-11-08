import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { getForcedTheme, setForcedTheme } from "./ForceTheme";

const KEY = "realdeal.theme";
const OLD_KEY = "realdeal.dev.theme";

function fakeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: () => null,
    get length() {
      return store.size;
    },
  } as Storage;
}

function throwingStorage(): Storage {
  const boom = () => {
    throw new Error("storage disabled");
  };
  return { getItem: boom, setItem: boom, removeItem: boom, clear: boom, key: boom, length: 0 } as Storage;
}

beforeEach(() => {
  Object.defineProperty(globalThis, "localStorage", { value: fakeStorage(), writable: true, configurable: true });
});

afterEach(() => {
  delete (globalThis as { localStorage?: Storage }).localStorage;
});

describe("getForcedTheme / setForcedTheme persistence", () => {
  it("defaults to system when nothing is stored", () => {
    expect(getForcedTheme()).toBe("system");
  });

  it("round-trips an explicit choice", () => {
    setForcedTheme("dark");
    expect(getForcedTheme()).toBe("dark");
    expect(localStorage.getItem(KEY)).toBe("dark");

    setForcedTheme("light");
    expect(getForcedTheme()).toBe("light");
  });

  it("clears the stored override when set back to system", () => {
    setForcedTheme("dark");
    setForcedTheme("system");
    expect(getForcedTheme()).toBe("system");
    expect(localStorage.getItem(KEY)).toBeNull();
  });
});

describe("migration from the old dev-only key", () => {
  it("adopts the old key's value once, then removes the old key", () => {
    localStorage.setItem(OLD_KEY, "dark");
    expect(getForcedTheme()).toBe("dark");
    expect(localStorage.getItem(KEY)).toBe("dark");
    expect(localStorage.getItem(OLD_KEY)).toBeNull();
  });

  it("prefers the new key over the old one when both are present", () => {
    localStorage.setItem(KEY, "light");
    localStorage.setItem(OLD_KEY, "dark");
    expect(getForcedTheme()).toBe("light");
  });

  it("ignores a garbage old value and still clears it", () => {
    localStorage.setItem(OLD_KEY, "purple");
    expect(getForcedTheme()).toBe("system");
    expect(localStorage.getItem(OLD_KEY)).toBeNull();
  });
});

describe("storage throwing (private mode / disabled storage)", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "localStorage", { value: throwingStorage(), writable: true, configurable: true });
  });

  it("getForcedTheme falls back to system instead of throwing", () => {
    expect(() => getForcedTheme()).not.toThrow();
    expect(getForcedTheme()).toBe("system");
  });

  it("setForcedTheme swallows the error instead of throwing", () => {
    expect(() => setForcedTheme("dark")).not.toThrow();
  });
});
