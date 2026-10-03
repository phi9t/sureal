/// <reference lib="webworker" />
/** Decode a 16-bit panoptic PNG and colourise it (semantic LUT + instance hue jitter). */
import { decode } from "fast-png";

export interface PanopticJob { id: number; url: string; divisor: number; lut: Uint8Array; instanceMix: number }
export interface PanopticResult { id: number; width?: number; height?: number; rgba?: Uint8ClampedArray; classes?: number[]; error?: string }

self.onmessage = async (e: MessageEvent<PanopticJob>) => {
  const { id, url, divisor, lut, instanceMix } = e.data;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status}`);
    const png = decode(await r.arrayBuffer());
    if (png.channels !== 1 || png.depth !== 16) throw new Error(`unexpected panoptic PNG: ${png.channels}ch ${png.depth}bit`);
    const src = png.data as Uint16Array;
    const n = png.width * png.height;
    const rgba = new Uint8ClampedArray(n * 4);
    const present = new Set<number>();
    for (let i = 0; i < n; i++) {
      const v = src[i];
      const sem = Math.floor(v / divisor);
      const inst = v % divisor;
      present.add(sem);
      const o = i * 4;
      let rr = lut[sem * 3], gg = lut[sem * 3 + 1], bb = lut[sem * 3 + 2];
      if (inst > 0 && instanceMix > 0) {
        const h = ((inst * 0.618033988749895) % 1) * 6;
        const x = 1 - Math.abs((h % 2) - 1);
        const c = [[1, x, 0], [x, 1, 0], [0, 1, x], [0, x, 1], [x, 0, 1], [1, 0, x]][Math.floor(h) % 6];
        rr = rr * (1 - instanceMix) + c[0] * 255 * instanceMix;
        gg = gg * (1 - instanceMix) + c[1] * 255 * instanceMix;
        bb = bb * (1 - instanceMix) + c[2] * 255 * instanceMix;
      }
      rgba[o] = rr; rgba[o + 1] = gg; rgba[o + 2] = bb; rgba[o + 3] = sem === 0 ? 0 : 255;
    }
    (self as unknown as Worker).postMessage({ id, width: png.width, height: png.height, rgba, classes: [...present] } as PanopticResult, [rgba.buffer]);
  } catch (err) {
    (self as unknown as Worker).postMessage({ id, error: String(err) } as PanopticResult);
  }
};
