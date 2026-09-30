import type { Scene } from "../data/bundle";
import type { ViewerState } from "../state";

export class Hud {
  private el: HTMLElement;
  private fps = 0;
  private acc = 0;
  private n = 0;
  constructor(root: HTMLElement, private scene: Scene) {
    this.el = root;
  }
  tick(dt: number): void {
    this.acc += dt;
    this.n++;
    if (this.acc >= 0.5) {
      this.fps = this.n / this.acc;
      this.acc = 0;
      this.n = 0;
    }
  }
  render(state: ViewerState, info: { points: number; draws: number; boxes: number; cached: number; bytes: number; loading: boolean; keypoints: number }): void {
    const f = this.scene.frames[state.frame];
    const t0 = this.scene.frames[0].timestamp_micros;
    const t = (f.timestamp_micros - t0) / 1e6;
    const st = f.stats;
    const counts = st ? Object.entries(st.lidar_object_counts).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(" · ") : "";
    this.el.innerHTML = `
      <div class="line"><span class="big">${String(state.frame).padStart(3, "0")}<span class="dim">/${this.scene.frames.length - 1}</span></span><span>${t.toFixed(1)}s ${state.playing ? "▶" : "⏸"} ${state.rate}×</span></div>
      <div class="line dim"><span>${st ? `${st.time_of_day} · ${st.weather} · ${st.location.replace("location_", "")}` : ""}</span></div>
      <div class="line"><span>${counts}</span></div>
      <div class="line dim"><span>${(info.points / 1000).toFixed(0)}k pts · ${info.draws} draws · ${info.boxes} boxes${info.keypoints ? ` · ${info.keypoints} skel` : ""}</span><span>${this.fps.toFixed(0)} fps</span></div>
      <div class="line dim"><span>cache ${info.cached}f · ${(info.bytes / 1048576).toFixed(0)} MB${info.loading ? " · loading…" : ""}${f.has_lidar_segmentation ? " · lidar seg" : ""}</span><span>${state.colorMode} · ${state.rig}</span></div>`;
  }
}
