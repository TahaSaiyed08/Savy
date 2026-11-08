/**
 * Resize to at most `maxEdge` px on the long edge and re-encode as JPEG. <canvas> always rasterizes to
 * RGB regardless of the source format, so this also normalizes an iPhone HEIC photo to a JPEG the backend
 * and extractor both accept, and keeps uploads well under the API's 10 MB cap (413).
 */
export async function downscaleImage(file: File, maxEdge = 2000, quality = 0.8): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    try {
      const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
      const w = Math.round(bitmap.width * scale);
      const h = Math.round(bitmap.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) return file;
      ctx.drawImage(bitmap, 0, 0, w, h);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
      if (!blob) return file;
      return new File([blob], file.name.replace(/\.\w+$/, ".jpg"), { type: "image/jpeg" });
    } finally {
      bitmap.close();
    }
  } catch {
    return file; // decode failed (old browser, odd format) — upload the original rather than block intake
  }
}
