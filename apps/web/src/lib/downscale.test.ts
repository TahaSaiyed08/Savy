import { afterEach, describe, expect, it, vi } from "vitest";
import { downscaleImage } from "./downscale";

function makeFile(name = "photo.jpg", type = "image/jpeg") {
  return new File([new Uint8Array([1, 2, 3])], name, { type });
}

function stubCanvas(blob: Blob | null = new Blob(["x"], { type: "image/jpeg" })) {
  const ctx = { drawImage: vi.fn() };
  const canvas: { width: number; height: number; getContext: () => typeof ctx; toBlob: (cb: (b: Blob | null) => void) => void } = {
    width: 0,
    height: 0,
    getContext: () => ctx,
    toBlob: (cb) => cb(blob),
  };
  vi.stubGlobal("document", { createElement: () => canvas });
  return { ctx, canvas };
}

describe("downscaleImage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("falls back to the original file when createImageBitmap isn't available (no DOM in the test env)", async () => {
    const file = makeFile();
    const result = await downscaleImage(file);
    expect(result).toBe(file);
  });

  it("scales down to the max edge, preserving aspect ratio, and re-encodes as jpeg", async () => {
    const bitmap = { width: 4000, height: 2000, close: vi.fn() };
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue(bitmap));
    const { ctx, canvas } = stubCanvas();

    const result = await downscaleImage(makeFile("big.heic", "image/heic"), 2000, 0.8);

    expect(canvas.width).toBe(2000);
    expect(canvas.height).toBe(1000); // 4000x2000 at scale 0.5
    expect(ctx.drawImage).toHaveBeenCalledWith(bitmap, 0, 0, 2000, 1000);
    expect(bitmap.close).toHaveBeenCalledOnce();
    expect(result.type).toBe("image/jpeg");
    expect(result.name).toBe("big.jpg"); // HEIC extension swapped for jpg
  });

  it("never upscales an image already under the max edge", async () => {
    const bitmap = { width: 800, height: 600, close: vi.fn() };
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue(bitmap));
    const { canvas } = stubCanvas();

    await downscaleImage(makeFile(), 2000, 0.8);

    expect(canvas.width).toBe(800);
    expect(canvas.height).toBe(600);
  });

  it("falls back to the original file if canvas.toBlob yields nothing", async () => {
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue({ width: 100, height: 100, close: vi.fn() }));
    stubCanvas(null);

    const file = makeFile();
    const result = await downscaleImage(file);
    expect(result).toBe(file);
  });
});
