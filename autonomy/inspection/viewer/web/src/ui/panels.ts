/** Camera image strip and focus view with 2D boxes, projected 3D boxes, keypoints and panoptic overlay. */
import type { Box2D, Scene } from "../data/bundle";
import type { FrameData, FrameLoader } from "../data/loader";
import type { Store, ViewerState } from "../state";

const STRIP_W = 480;

export class Panels {
  private canvases = new Map<number, HTMLCanvasElement>();
  private focusCanvas: HTMLCanvasElement;
  private focusCap: HTMLElement;
  private lastKey = "";
  private lastFocusKey = "";

  constructor(strip: HTMLElement, focus: HTMLElement, store: Store, private scene: Scene, private loader: FrameLoader) {
    strip.innerHTML = "";
    for (const [k, cal] of Object.entries(scene.cameras).sort((a, b) => Number(a[0]) - Number(b[0]))) {
      const name = Number(k);
      const div = document.createElement("div");
      div.className = "cam";
      div.dataset.cam = k;
      const canvas = document.createElement("canvas");
      canvas.width = STRIP_W;
      canvas.height = Math.round((STRIP_W * cal.height) / cal.width);
      const tag = document.createElement("div");
      tag.className = "tag";
      tag.textContent = cal.name.replace("_", " ");
      div.append(canvas, tag);
      div.addEventListener("click", () => store.patch({ focusCamera: name }));
      strip.append(div);
      this.canvases.set(name, canvas);
    }
    focus.innerHTML = "";
    this.focusCanvas = document.createElement("canvas");
    this.focusCap = document.createElement("div");
    this.focusCap.className = "cap";
    focus.append(this.focusCanvas, this.focusCap);
    focus.addEventListener("click", () => store.patch({ focusCamera: null }));
    store.subscribe((s) => s.focusCamera, (v) => focus.classList.toggle("on", v !== null));
    store.subscribe((s) => s.rig === "pov" ? s.povCamera : -1, (v) => {
      for (const el of strip.querySelectorAll<HTMLElement>(".cam")) el.classList.toggle("pov", Number(el.dataset.cam) === v);
    });
  }

  update(state: ViewerState, frame: number, data: FrameData | undefined): void {
    const key = `${frame}|${!!data}|${state.showSeg}|${state.segOpacity}|${state.showBoxes}|${state.showKeypoints}|${state.selectedTrack}|${JSON.stringify(state.classFilter)}`;
    if (key !== this.lastKey) {
      this.lastKey = key;
      for (const [name, canvas] of this.canvases) this.draw(canvas, name, frame, data, state, false);
    }
    if (state.focusCamera !== null) {
      const fkey = key + "|" + state.focusCamera;
      if (fkey !== this.lastFocusKey) {
        this.lastFocusKey = fkey;
        const cal = this.scene.cameras[String(state.focusCamera)];
        this.focusCanvas.width = cal.width;
        this.focusCanvas.height = cal.height;
        this.draw(this.focusCanvas, state.focusCamera, frame, data, state, true);
        this.focusCap.textContent = `${cal.name} · frame ${frame} · ${cal.width}×${cal.height} · f=${cal.intrinsics.f_u.toFixed(0)}px`;
      }
    } else {
      this.lastFocusKey = "";
    }
  }

  private draw(canvas: HTMLCanvasElement, name: number, frame: number, data: FrameData | undefined, state: ViewerState, full: boolean): void {
    const ctx = canvas.getContext("2d")!;
    const cal = this.scene.cameras[String(name)];
    const sx = canvas.width / cal.width, sy = canvas.height / cal.height;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!data) return;
    const bitmap = full ? data.imagesFull.get(name) ?? data.images.get(name) : data.images.get(name);
    if (bitmap) ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    if (full && !data.imagesFull.get(name)) void this.loader.fullImage(frame, name).then(() => (this.lastFocusKey = ""));
    if (state.showSeg) {
      const pan = data.panoptic.get(name);
      if (pan) {
        const off = new OffscreenCanvas(pan.width, pan.height);
        off.getContext("2d")!.putImageData(new ImageData(pan.rgba as Uint8ClampedArray<ArrayBuffer>, pan.width, pan.height), 0, 0);
        ctx.globalAlpha = state.segOpacity;
        ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = 1;
      } else if (this.scene.frames[frame].cameras[String(name)]?.panoptic) {
        void this.loader.panopticFor(frame, name).then(() => (this.lastKey = ""));
      }
    }
    const lw = full ? 3 : 1.5;
    ctx.lineWidth = lw;
    ctx.font = `${full ? 22 : 10}px ui-monospace, monospace`;
    if (state.showBoxes) {
      const proj = data.ann.projected_boxes[String(name)] ?? [];
      for (const b of proj) this.box(ctx, b, sx, sy, this.scene.palettes.box_colors[String(b[5])] ?? "#fff", state, full, true);
      const cam = data.ann.camera_boxes[String(name)] ?? [];
      for (const b of cam) this.box(ctx, b, sx, sy, "rgba(255,255,255,0.75)", state, full, false);
    }
    if (state.showKeypoints) {
      const kp = data.ann.camera_keypoints[String(name)] ?? {};
      for (const pts of Object.values(kp)) {
        const by = new Map<number, [number, number, number]>();
        for (const [t, x, y, occ] of pts) by.set(t, [x, y, occ]);
        ctx.strokeStyle = "#ffe082";
        ctx.lineWidth = lw;
        for (const [a, b] of this.scene.palettes.keypoint_edges) {
          const pa = by.get(a), pb = by.get(b);
          if (!pa || !pb) continue;
          ctx.globalAlpha = pa[2] || pb[2] ? 0.4 : 0.95;
          ctx.beginPath();
          ctx.moveTo(pa[0] * sx, pa[1] * sy);
          ctx.lineTo(pb[0] * sx, pb[1] * sy);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        ctx.fillStyle = "#fff";
        for (const [x, y] of by.values()) {
          ctx.beginPath();
          ctx.arc(x * sx, y * sy, full ? 4 : 1.8, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
  }

  private box(ctx: CanvasRenderingContext2D, b: Box2D, sx: number, sy: number, color: string, state: ViewerState, full: boolean, projected: boolean): void {
    if (projected && state.classFilter[b[5]] === false) return;
    const [id, cx, cy, w, h] = b;
    const selected = state.selectedTrack === id;
    ctx.strokeStyle = color;
    ctx.globalAlpha = state.selectedTrack && !selected ? 0.35 : 1;
    ctx.lineWidth = selected ? (full ? 5 : 2.5) : full ? 2.5 : 1.2;
    if (!projected) ctx.setLineDash(full ? [8, 6] : [3, 3]);
    ctx.strokeRect((cx - w / 2) * sx, (cy - h / 2) * sy, w * sx, h * sy);
    ctx.setLineDash([]);
    if (full && projected) {
      ctx.fillStyle = color;
      ctx.fillText(id.slice(0, 5), (cx - w / 2) * sx + 4, (cy - h / 2) * sy - 6);
    }
    ctx.globalAlpha = 1;
  }
}
