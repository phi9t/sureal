import type { Scene } from "../data/bundle";
import type { Store } from "../state";

export class Timeline {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private info: HTMLElement;
  private dragging = false;
  cached: Set<number> = new Set();
  constructor(root: HTMLElement, private store: Store, private scene: Scene) {
    root.innerHTML = `<div class="controls"><button data-a="play">▶ play</button><button data-a="prev">◀</button><button data-a="next">▶</button><button data-a="slower">−</button><span class="t" data-t></span><button data-a="faster">+</button><span class="t" style="margin-left:auto">${scene.frames.length} frames · 10 Hz</span></div>`;
    this.canvas = document.createElement("canvas");
    root.append(this.canvas);
    this.ctx = this.canvas.getContext("2d")!;
    this.info = root.querySelector("[data-t]")!;
    root.querySelectorAll<HTMLButtonElement>("button").forEach((b) =>
      b.addEventListener("click", () => {
        const s = store.get();
        const n = scene.frames.length;
        switch (b.dataset.a) {
          case "play": store.patch({ playing: !s.playing }); break;
          case "prev": store.patch({ frame: (s.frame - 1 + n) % n, playing: false }); break;
          case "next": store.patch({ frame: (s.frame + 1) % n, playing: false }); break;
          case "slower": store.patch({ rate: Math.max(0.1, +(s.rate / 2).toFixed(2)) }); break;
          case "faster": store.patch({ rate: Math.min(8, s.rate * 2) }); break;
        }
      }),
    );
    const seek = (e: PointerEvent) => {
      const r = this.canvas.getBoundingClientRect();
      const t = Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1);
      store.patch({ frame: Math.round(t * (scene.frames.length - 1)) });
    };
    this.canvas.addEventListener("pointerdown", (e) => {
      this.dragging = true;
      this.canvas.setPointerCapture(e.pointerId);
      store.patch({ playing: false });
      seek(e);
    });
    this.canvas.addEventListener("pointermove", (e) => this.dragging && seek(e));
    this.canvas.addEventListener("pointerup", () => (this.dragging = false));
    store.watch(["frame", "playing", "rate", "accumulate", "accumFrames", "accumStride"], () => this.draw());
    new ResizeObserver(() => this.draw()).observe(this.canvas);
  }
  draw(): void {
    const s = this.store.get();
    const n = this.scene.frames.length;
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth * dpr, h = this.canvas.clientHeight * dpr;
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    const c = this.ctx;
    c.clearRect(0, 0, w, h);
    c.fillStyle = "rgba(255,255,255,0.05)";
    c.fillRect(0, 0, w, h);
    const fw = w / n;
    for (let i = 0; i < n; i++) {
      if (this.cached.has(i)) {
        c.fillStyle = "rgba(77,208,225,0.22)";
        c.fillRect(i * fw, 0, Math.max(1, fw - 0.5), h);
      }
      if (this.scene.frames[i].has_lidar_segmentation) {
        c.fillStyle = "rgba(255,183,77,0.9)";
        c.fillRect(i * fw, h - 4 * dpr, Math.max(1, fw), 4 * dpr);
      }
    }
    if (s.accumulate) {
      c.fillStyle = "rgba(77,208,225,0.15)";
      const a = Math.max(0, s.frame - (s.accumFrames - 1) * s.accumStride);
      c.fillRect(a * fw, 0, (s.frame - a + 1) * fw, h);
    }
    c.fillStyle = "#4dd0e1";
    c.fillRect(s.frame * fw, 0, Math.max(2 * dpr, fw), h);
    const t = (this.scene.frames[s.frame].timestamp_micros - this.scene.frames[0].timestamp_micros) / 1e6;
    this.info.innerHTML = `<b>${t.toFixed(1)}s</b> · ${s.rate}×`;
    const play = this.canvas.parentElement?.querySelector<HTMLButtonElement>("[data-a=play]");
    if (play) play.textContent = s.playing ? "⏸ pause" : "▶ play";
  }
}
