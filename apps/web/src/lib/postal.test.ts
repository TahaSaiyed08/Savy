import { describe, expect, it } from "vitest";
import { formatPostal, normalizePostal } from "./postal";

describe("normalizePostal", () => {
  it.each([
    ["V6T1Z4", "V6T1Z4"],
    ["v6t 1z4", "V6T1Z4"],
    [" M5V-2T6 ", "M5V2T6"],
  ])("accepts %s", (raw, want) => expect(normalizePostal(raw)).toBe(want));

  it.each(["", "12345", "V6T1Z", "V6T1Z44", "D6T 1Z4X", "ABCDEF"])("rejects %j", (raw) => expect(normalizePostal(raw)).toBeNull());
});

describe("formatPostal", () => {
  it("puts the space back", () => expect(formatPostal("V6T1Z4")).toBe("V6T 1Z4"));
});
