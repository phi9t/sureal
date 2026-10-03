/// <reference lib="webworker" />
/** Fetch a JPEG and decode it to an ImageBitmap off the main thread. */
export interface ImageJob { id: number; url: string; maxWidth: number }
export interface ImageResult { id: number; bitmap?: ImageBitmap; error?: string }

self.onmessage = async (e: MessageEvent<ImageJob>) => {
  const { id, url, maxWidth } = e.data;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status}`);
    const blob = await r.blob();
    const opts: ImageBitmapOptions = { colorSpaceConversion: "default", premultiplyAlpha: "none" };
    if (maxWidth > 0) opts.resizeWidth = maxWidth;
    if (maxWidth > 0) opts.resizeQuality = "medium";
    const bitmap = await createImageBitmap(blob, opts);
    (self as unknown as Worker).postMessage({ id, bitmap } as ImageResult, [bitmap]);
  } catch (err) {
    (self as unknown as Worker).postMessage({ id, error: String(err) } as ImageResult);
  }
};
