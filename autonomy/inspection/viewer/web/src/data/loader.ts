/** Frame loader: fetch + parse .wpc and annotations, prefetch window, byte-bounded LRU, worker image decode. */
import { fetchJson, type FrameAnnotations, type Scene } from "./bundle";
import { parseWpc, type ParsedWpc } from "./wpc";
import type { ImageResult } from "./imageWorker";
import type { PanopticResult } from "./panopticWorker";

export interface FrameData {
  index: number;
  wpc: ParsedWpc;
  ann: FrameAnnotations;
  images: Map<number, ImageBitmap>;
  imagesFull: Map<number, ImageBitmap>;
  panoptic: Map<number, { width: number; height: number; rgba: Uint8ClampedArray }>;
  bytes: number;
}

type Pending = { promise: Promise<FrameData>; ctrl: AbortController };

class WorkerPool<J, R extends { id: number }> {
  private workers: Worker[] = [];
  private next = 0;
  private waiting = new Map<number, (r: R) => void>();
  private seq = 1;
  constructor(make: () => Worker, n: number) {
    for (let i = 0; i < n; i++) {
      const w = make();
      w.onmessage = (e: MessageEvent<R>) => {
        const cb = this.waiting.get(e.data.id);
        this.waiting.delete(e.data.id);
        cb?.(e.data);
      };
      this.workers.push(w);
    }
  }
  run(job: Omit<J, "id">, transfer: Transferable[] = []): Promise<R> {
    const id = this.seq++;
    const w = this.workers[this.next++ % this.workers.length];
    return new Promise((resolve) => {
      this.waiting.set(id, resolve);
      w.postMessage({ ...job, id }, transfer);
    });
  }
}

export class FrameLoader {
  private cache = new Map<number, FrameData>();
  private pending = new Map<number, Pending>();
  private order: number[] = [];
  private bytes = 0;
  private images: WorkerPool<{ url: string; maxWidth: number }, ImageResult>;
  private panoptic: WorkerPool<{ url: string; divisor: number; lut: Uint8Array; instanceMix: number }, PanopticResult>;
  private lut: Uint8Array;
  onEvict: ((frame: number, data: FrameData) => void) | null = null;
  onLoaded: ((frame: number) => void) | null = null;
  prefetchAhead = 8;
  prefetchBehind = 2;
  capacityBytes = 700 * 1024 * 1024;
  planeWidth = 800;
  loadPanoptic = false;

  constructor(public baseUrl: string, public scene: Scene) {
    this.images = new WorkerPool(() => new Worker(new URL("./imageWorker.ts", import.meta.url), { type: "module" }), 3);
    this.panoptic = new WorkerPool(() => new Worker(new URL("./panopticWorker.ts", import.meta.url), { type: "module" }), 1);
    const colors = scene.palettes.camera_semantic_colors;
    this.lut = new Uint8Array(colors.length * 3);
    colors.forEach((hex, i) => {
      const n = parseInt(hex.slice(1), 16);
      this.lut[i * 3] = (n >> 16) & 255;
      this.lut[i * 3 + 1] = (n >> 8) & 255;
      this.lut[i * 3 + 2] = n & 255;
    });
  }

  get(frame: number): FrameData | undefined {
    return this.cache.get(frame);
  }
  has(frame: number): boolean {
    return this.cache.has(frame);
  }
  isPending(frame: number): boolean {
    return this.pending.has(frame);
  }
  cachedFrames(): number[] {
    return [...this.cache.keys()];
  }

  /** Reprioritise around the cursor: fetch a window ahead, abort far-away pending fetches. */
  setCursor(frame: number, direction: 1 | -1 = 1): void {
    const n = this.scene.frames.length;
    const want = new Set<number>();
    for (let d = -this.prefetchBehind; d <= this.prefetchAhead; d++) {
      const f = frame + d * direction;
      if (f >= 0 && f < n) want.add(f);
    }
    for (const [f, p] of this.pending) {
      if (!want.has(f) && Math.abs(f - frame) > this.prefetchAhead * 2) {
        p.ctrl.abort();
        this.pending.delete(f);
      }
    }
    for (let d = 0; d <= this.prefetchAhead; d++) {
      const f = frame + d * direction;
      if (f >= 0 && f < n) void this.request(f);
    }
    for (let d = 1; d <= this.prefetchBehind; d++) {
      const f = frame - d * direction;
      if (f >= 0 && f < n) void this.request(f);
    }
  }

  request(frame: number): Promise<FrameData> {
    const cached = this.cache.get(frame);
    if (cached) return Promise.resolve(cached);
    const pending = this.pending.get(frame);
    if (pending) return pending.promise;
    const ctrl = new AbortController();
    const promise = this.load(frame, ctrl.signal)
      .then((data) => {
        this.pending.delete(frame);
        this.insert(frame, data);
        this.onLoaded?.(frame);
        return data;
      })
      .catch((err) => {
        this.pending.delete(frame);
        throw err;
      });
    this.pending.set(frame, { promise, ctrl });
    return promise;
  }

  private async load(frame: number, signal: AbortSignal): Promise<FrameData> {
    const meta = this.scene.frames[frame];
    const [buf, ann] = await Promise.all([
      fetch(this.baseUrl + meta.points, { signal }).then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${meta.points}`);
        return r.arrayBuffer();
      }),
      fetchJson<FrameAnnotations>(this.baseUrl + meta.annotations, signal),
    ]);
    const wpc = parseWpc(buf);
    const images = new Map<number, ImageBitmap>();
    const jobs: Promise<void>[] = [];
    for (const [name, cam] of Object.entries(meta.cameras)) {
      if (!cam.image) continue;
      jobs.push(
        this.images.run({ url: this.baseUrl + cam.image, maxWidth: this.planeWidth }).then((r) => {
          if (r.bitmap) images.set(Number(name), r.bitmap);
        }),
      );
    }
    await Promise.all(jobs);
    let bytes = buf.byteLength;
    for (const b of images.values()) bytes += b.width * b.height * 4;
    return { index: frame, wpc, ann, images, imagesFull: new Map(), panoptic: new Map(), bytes };
  }

  /** Full-resolution bitmap for the focused camera panel (cached on the frame). */
  async fullImage(frame: number, camera: number): Promise<ImageBitmap | undefined> {
    const data = this.cache.get(frame);
    if (!data) return undefined;
    const have = data.imagesFull.get(camera);
    if (have) return have;
    const cam = this.scene.frames[frame].cameras[String(camera)];
    if (!cam?.image) return undefined;
    const r = await this.images.run({ url: this.baseUrl + cam.image, maxWidth: 0 });
    if (r.bitmap && this.cache.get(frame) === data) {
      data.imagesFull.set(camera, r.bitmap);
      data.bytes += r.bitmap.width * r.bitmap.height * 4;
      this.bytes += r.bitmap.width * r.bitmap.height * 4;
    }
    return r.bitmap;
  }

  async panopticFor(frame: number, camera: number, instanceMix = 0.35): Promise<FrameData["panoptic"] extends Map<number, infer V> ? V | undefined : never> {
    const data = this.cache.get(frame);
    if (!data) return undefined;
    const have = data.panoptic.get(camera);
    if (have) return have;
    const cam = this.scene.frames[frame].cameras[String(camera)];
    if (!cam?.panoptic) return undefined;
    const r = await this.panoptic.run({ url: this.baseUrl + cam.panoptic, divisor: cam.panoptic_divisor ?? 1000, lut: this.lut, instanceMix });
    if (r.rgba && r.width && r.height && this.cache.get(frame) === data) {
      const v = { width: r.width, height: r.height, rgba: r.rgba };
      data.panoptic.set(camera, v);
      return v;
    }
    return undefined;
  }

  private insert(frame: number, data: FrameData): void {
    this.cache.set(frame, data);
    this.order.push(frame);
    this.bytes += data.bytes;
    while (this.bytes > this.capacityBytes && this.order.length > 1) {
      const victim = this.order.shift()!;
      const v = this.cache.get(victim);
      if (!v) continue;
      this.cache.delete(victim);
      this.bytes -= v.bytes;
      this.onEvict?.(victim, v);
      for (const b of v.images.values()) b.close();
      for (const b of v.imagesFull.values()) b.close();
    }
  }

  /** Move a frame to the most-recently-used position (called when rendered). */
  touch(frame: number): void {
    const i = this.order.indexOf(frame);
    if (i >= 0) {
      this.order.splice(i, 1);
      this.order.push(frame);
    }
  }

  get bytesUsed(): number {
    return this.bytes;
  }
}
