/** 3D boxes (fat lines), heading chevrons, labels, trails and speed vectors. */
import * as THREE from "three";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import type { BoxRow, Scene, TrackIndex } from "../data/bundle";
import { mat4FromRowMajor } from "../frames";
import { hexToRgb } from "../palettes";
import type { ViewerState } from "../state";

const EDGES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7],
];

export class Boxes {
  group = new THREE.Group();
  private vehicleGroup = new THREE.Group();
  private worldGroup = new THREE.Group();
  private lines: LineSegments2;
  private trails: LineSegments2;
  private speeds: LineSegments2;
  private lineMat: LineMaterial;
  private trailMat: LineMaterial;
  private speedMat: LineMaterial;
  private labels: CSS2DObject[] = [];
  private colors: Record<number, [number, number, number]> = {};
  private worldCenters = new Map<string, Map<number, THREE.Vector3>>();
  private lastFrame = -1;
  private lastKey = "";
  boxCount = 0;

  constructor(private scene: Scene, private tracks: TrackIndex, resolution: THREE.Vector2) {
    for (const [k, hex] of Object.entries(scene.palettes.box_colors)) this.colors[Number(k)] = hexToRgb(hex);
    this.lineMat = new LineMaterial({ vertexColors: true, linewidth: 2.2, worldUnits: false, transparent: true, opacity: 0.95, resolution });
    this.trailMat = new LineMaterial({ vertexColors: true, linewidth: 1.6, worldUnits: false, transparent: true, opacity: 0.8, resolution });
    this.speedMat = new LineMaterial({ vertexColors: true, linewidth: 3, worldUnits: false, transparent: true, opacity: 0.95, resolution });
    this.lines = new LineSegments2(new LineSegmentsGeometry(), this.lineMat);
    this.trails = new LineSegments2(new LineSegmentsGeometry(), this.trailMat);
    this.speeds = new LineSegments2(new LineSegmentsGeometry(), this.speedMat);
    for (const l of [this.lines, this.trails, this.speeds]) l.frustumCulled = false;
    this.vehicleGroup.matrixAutoUpdate = false;
    this.vehicleGroup.add(this.lines);
    this.worldGroup.add(this.trails, this.speeds);
    this.group.add(this.vehicleGroup, this.worldGroup);
    this.group.name = "boxes";
    // World-frame centres for trails/speeds, computed once.
    const poses = scene.frames.map((f) => mat4FromRowMajor(f.world_from_vehicle));
    for (const [id, rows] of tracks.byId) {
      const m = new Map<number, THREE.Vector3>();
      for (const r of rows) m.set(r.frame, new THREE.Vector3(...r.c).applyMatrix4(poses[r.frame]));
      this.worldCenters.set(id, m);
    }
  }

  setResolution(res: THREE.Vector2): void {
    for (const m of [this.lineMat, this.trailMat, this.speedMat]) m.resolution.copy(res);
  }

  private corners(b: BoxRow, out: THREE.Vector3[]): void {
    const [l, w, h] = b.size;
    const c = Math.cos(b.heading), s = Math.sin(b.heading);
    let i = 0;
    for (const z of [-h / 2, h / 2]) {
      for (const [x, y] of [[l / 2, w / 2], [l / 2, -w / 2], [-l / 2, -w / 2], [-l / 2, w / 2]]) {
        out[i++].set(b.c[0] + x * c - y * s, b.c[1] + x * s + y * c, b.c[2] + z);
      }
    }
  }

  update(state: ViewerState, frame: number): void {
    const key = `${frame}|${state.showBoxes}|${state.showLabels}|${state.showTrails}|${state.showSpeed}|${JSON.stringify(state.classFilter)}|${state.selectedTrack}`;
    if (key === this.lastKey) return;
    this.lastKey = key;
    this.lastFrame = frame;
    this.vehicleGroup.matrix.copy(mat4FromRowMajor(this.scene.frames[frame].world_from_vehicle));
    this.vehicleGroup.matrixWorldNeedsUpdate = true;
    const boxes = (this.tracks.byFrame.get(frame) ?? []).filter((b) => state.classFilter[b.type] !== false);
    this.boxCount = boxes.length;
    this.group.visible = state.showBoxes;
    const pos: number[] = [];
    const col: number[] = [];
    const tmp = Array.from({ length: 8 }, () => new THREE.Vector3());
    const push = (a: THREE.Vector3, b: THREE.Vector3, rgb: [number, number, number], k = 1) => {
      pos.push(a.x, a.y, a.z, b.x, b.y, b.z);
      col.push(rgb[0] * k, rgb[1] * k, rgb[2] * k, rgb[0] * k, rgb[1] * k, rgb[2] * k);
    };
    for (const b of boxes) {
      this.corners(b, tmp);
      const rgb = this.colors[b.type] ?? this.colors[0];
      const k = state.selectedTrack && state.selectedTrack !== b.id ? 0.35 : 1.4;
      for (const [i, j] of EDGES) push(tmp[i], tmp[j], rgb, k);
      // Heading chevron on the front face at mid height.
      const c = Math.cos(b.heading), s = Math.sin(b.heading);
      const [l, w] = b.size;
      const tip = new THREE.Vector3(b.c[0] + (l / 2 + 0.7) * c, b.c[1] + (l / 2 + 0.7) * s, b.c[2]);
      const a1 = new THREE.Vector3(b.c[0] + (l / 2) * c - (w / 4) * s, b.c[1] + (l / 2) * s + (w / 4) * c, b.c[2]);
      const a2 = new THREE.Vector3(b.c[0] + (l / 2) * c + (w / 4) * s, b.c[1] + (l / 2) * s - (w / 4) * c, b.c[2]);
      push(a1, tip, rgb, k);
      push(a2, tip, rgb, k);
    }
    this.replace(this.lines, pos, col);

    // Trails and speed vectors live in world coordinates.
    const tpos: number[] = [];
    const tcol: number[] = [];
    const spos: number[] = [];
    const scol: number[] = [];
    const bg: [number, number, number] = [0.02, 0.03, 0.05];
    for (const b of boxes) {
      const rgb = this.colors[b.type] ?? this.colors[0];
      const centers = this.worldCenters.get(b.id)!;
      if (state.showTrails || state.selectedTrack === b.id) {
        const span = state.selectedTrack === b.id ? 400 : 30;
        for (let f = frame - span; f < frame; f++) {
          const a = centers.get(f), c = centers.get(f + 1);
          if (!a || !c) continue;
          const t = 1 - (frame - f) / span;
          const k = 0.15 + 0.85 * t;
          tpos.push(a.x, a.y, a.z, c.x, c.y, c.z);
          for (let q = 0; q < 2; q++) tcol.push(bg[0] + (rgb[0] - bg[0]) * k, bg[1] + (rgb[1] - bg[1]) * k, bg[2] + (rgb[2] - bg[2]) * k);
        }
      }
      if (state.showSpeed && b.speed) {
        const v = new THREE.Vector3(...b.speed);
        if (v.length() > 0.5) {
          const c0 = centers.get(frame)!;
          const c1 = c0.clone().add(v);
          spos.push(c0.x, c0.y, c0.z, c1.x, c1.y, c1.z);
          scol.push(1.6, 1.4, 0.5, 1.9, 0.5, 0.2);
        }
      }
    }
    this.replace(this.trails, tpos, tcol);
    this.replace(this.speeds, spos, scol);

    // Labels.
    let used = 0;
    if (state.showLabels || state.selectedTrack) {
      for (const b of boxes) {
        if (!state.showLabels && state.selectedTrack !== b.id) continue;
        const label = this.labels[used] ?? this.makeLabel();
        this.labels[used] = label;
        used++;
        const el = label.element as HTMLDivElement;
        const speed = b.speed ? Math.hypot(b.speed[0], b.speed[1]) : 0;
        el.textContent = `${this.scene.palettes.box_types[String(b.type)]?.toLowerCase() ?? "?"} ${b.id.slice(0, 5)}${speed > 0.3 ? ` · ${speed.toFixed(1)} m/s` : ""}`;
        el.style.borderColor = this.scene.palettes.box_colors[String(b.type)] ?? "#fff";
        label.position.set(b.c[0], b.c[1], b.c[2] + b.size[2] / 2 + 0.4);
        label.visible = true;
        if (!label.parent) this.vehicleGroup.add(label);
      }
    }
    for (let i = used; i < this.labels.length; i++) this.labels[i].visible = false;
  }

  private makeLabel(): CSS2DObject {
    const el = document.createElement("div");
    el.className = "box-label";
    const o = new CSS2DObject(el);
    o.center.set(0.5, 1);
    return o;
  }

  private replace(obj: LineSegments2, pos: number[], col: number[]): void {
    obj.geometry.dispose();
    const g = new LineSegmentsGeometry();
    if (pos.length) {
      g.setPositions(pos);
      g.setColors(col);
    } else {
      g.setPositions([0, 0, 0, 0, 0, 0]);
      g.setColors([0, 0, 0, 0, 0, 0]);
    }
    obj.geometry = g;
    obj.visible = pos.length > 0;
  }

  get frame(): number {
    return this.lastFrame;
  }
}
