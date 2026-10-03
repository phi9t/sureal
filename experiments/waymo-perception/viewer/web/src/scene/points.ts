/** Per-frame GPU point clouds with a shared shader material and an accumulation ring. */
import * as THREE from "three";
import type { Scene } from "../data/bundle";
import type { FrameData } from "../data/loader";
import { KIND, sectionKey } from "../data/wpc";
import { mat4FromRowMajor } from "../frames";
import { ember, hexToRgb, rampTexture, RETURN_COLORS, SENSOR_COLORS, turbo } from "../palettes";
import type { ColorMode, ViewerState } from "../state";
import vert from "../render/shaders/points.vert.glsl?raw";
import frag from "../render/shaders/points.frag.glsl?raw";

const MODE_INDEX: Record<ColorMode, number> = { height: 0, intensity: 1, range: 2, semantic: 3, sensor: 4, rgb: 5, return: 6 };

interface FrameEntry {
  group: THREE.Group;
  points: THREE.Points[];
  count: number;
}

export class PointClouds {
  group = new THREE.Group();
  material: THREE.ShaderMaterial;
  private frames = new Map<number, FrameEntry>();
  private ramps: Record<string, THREE.DataTexture>;
  visibleCount = 0;
  drawCalls = 0;

  constructor(private scene: Scene) {
    this.group.name = "points";
    this.ramps = { ember: rampTexture(ember), turbo: rampTexture(turbo) };
    const sem = new Array(32).fill(0).map(() => new THREE.Vector3(0.3, 0.3, 0.3));
    scene.palettes.lidar_semantic_colors.forEach((hex, i) => sem[i].set(...hexToRgb(hex)));
    const sensors = new Array(8).fill(0).map(() => new THREE.Vector3(1, 1, 1));
    for (const [k, hex] of Object.entries(SENSOR_COLORS)) sensors[Number(k)].set(...hexToRgb(hex));
    this.material = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: vert,
      fragmentShader: frag,
      transparent: true,
      depthWrite: true,
      depthTest: true,
      blending: THREE.NormalBlending,
      uniforms: {
        uScale: { value: scene.quantization.xyz.scale_m },
        uPointSize: { value: 2.2 },
        uViewportHeight: { value: 1000 },
        uOrtho: { value: 0 },
        uAge: { value: 0 },
        uHasSemantic: { value: 0 },
        uColorMode: { value: 0 },
        uHeightRange: { value: new THREE.Vector2(-1.5, 6.0) },
        uRangeMax: { value: 75 },
        uIntensityGamma: { value: 0.8 },
        uRamp: { value: this.ramps.ember },
        uSensorColors: { value: sensors },
        uSemanticColors: { value: sem },
        uReturnColors: { value: RETURN_COLORS.map((h) => new THREE.Vector3(...hexToRgb(h))) },
        uDimNlz: { value: 0 },
        uHideNlz: { value: 0 },
        uFogColor: { value: new THREE.Color("#05070c") },
        uFogDensity: { value: 0.004 },
        uGlow: { value: 0 },
        uGlowScale: { value: 0.35 },
      },
    });
  }

  has(frame: number): boolean {
    return this.frames.has(frame);
  }

  build(frame: number, data: FrameData): void {
    if (this.frames.has(frame)) return;
    const meta = this.scene.frames[frame];
    const group = new THREE.Group();
    group.matrixAutoUpdate = false;
    group.matrix.copy(mat4FromRowMajor(meta.world_from_vehicle));
    group.visible = false;
    const points: THREE.Points[] = [];
    let count = 0;
    for (const sec of data.wpc.sections.values()) {
      if (sec.kind !== KIND.xyz) continue;
      const { sensor, ret } = sec;
      const get = (kind: number) => data.wpc.sections.get(sectionKey(sensor, ret, kind));
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(sec.data as Int16Array, 3, false));
      geo.setAttribute("intensity", new THREE.BufferAttribute(get(KIND.intensity)!.data as Uint8Array, 1, true));
      geo.setAttribute("elongation", new THREE.BufferAttribute(get(KIND.elongation)!.data as Uint8Array, 1, true));
      geo.setAttribute("flags", new THREE.BufferAttribute(get(KIND.flags)!.data as Uint8Array, 1, false));
      geo.setAttribute("rgb", new THREE.BufferAttribute(get(KIND.rgb)!.data as Uint8Array, 3, true));
      const semantic = get(KIND.semantic);
      geo.setAttribute("semantic", new THREE.BufferAttribute(semantic ? (semantic.data as Uint8Array) : new Uint8Array(sec.count), 1, false));
      geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 400);
      const pts = new THREE.Points(geo, this.material);
      pts.frustumCulled = false;
      pts.matrixAutoUpdate = false;
      pts.userData = { sensor, ret, hasSemantic: semantic ? 1 : 0, age: 0 };
      pts.onBeforeRender = () => {
        this.material.uniforms.uAge.value = pts.userData.age;
        this.material.uniforms.uHasSemantic.value = pts.userData.hasSemantic;
        this.material.uniformsNeedUpdate = true;
      };
      group.add(pts);
      points.push(pts);
      count += sec.count;
    }
    this.group.add(group);
    this.frames.set(frame, { group, points, count });
  }

  dispose(frame: number): void {
    const e = this.frames.get(frame);
    if (!e) return;
    for (const p of e.points) p.geometry.dispose();
    this.group.remove(e.group);
    this.frames.delete(frame);
  }

  /** Apply state: colour mode, sizes, sensor toggles, and the accumulation ring around `current`. */
  update(state: ViewerState, current: number, viewportHeight: number, ortho: boolean): void {
    const u = this.material.uniforms;
    u.uColorMode.value = MODE_INDEX[state.colorMode];
    u.uPointSize.value = state.pointSize;
    u.uViewportHeight.value = viewportHeight;
    u.uOrtho.value = ortho ? 1 : 0;
    u.uDimNlz.value = state.dimNlz ? 1 : 0;
    u.uRamp.value = state.colorMode === "range" ? this.ramps.turbo : this.ramps.ember;
    u.uFogDensity.value = 0.012 * state.fog;
    u.uGlow.value = state.glow ? 1 : 0;
    u.uGlowScale.value = 0.2 / Math.sqrt(state.accumulate ? state.accumFrames : 1);
    this.material.blending = state.glow ? THREE.AdditiveBlending : THREE.NormalBlending;
    this.material.depthWrite = !state.glow;

    const wanted = new Map<number, number>();
    if (state.accumulate) {
      for (let i = 0; i < state.accumFrames; i++) {
        const f = current - i * state.accumStride;
        if (f >= 0) wanted.set(f, i / Math.max(1, state.accumFrames - 1));
      }
    } else {
      wanted.set(current, 0);
    }
    this.visibleCount = 0;
    this.drawCalls = 0;
    for (const [f, e] of this.frames) {
      const age = wanted.get(f);
      e.group.visible = age !== undefined;
      if (age === undefined) continue;
      for (const p of e.points) {
        const { sensor, ret } = p.userData as { sensor: number; ret: number };
        p.visible = !!state.sensors[sensor] && state.returns[ret - 1];
        p.userData.age = age;
        if (p.visible) {
          this.visibleCount += (p.geometry.getAttribute("position") as THREE.BufferAttribute).count;
          this.drawCalls++;
        }
      }
    }
  }

  /** Estimate the ground height (vehicle frame) from a frame's TOP return-1 points. */
  groundZ(data: FrameData): number {
    const sec = data.wpc.sections.get(sectionKey(1, 1, KIND.xyz));
    if (!sec) return -2.0;
    const xyz = sec.data as Int16Array;
    const zs: number[] = [];
    for (let i = 0; i < sec.count; i += 37) zs.push(xyz[i * 3 + 2]);
    zs.sort((a, b) => a - b);
    return zs.length ? zs[Math.floor(zs.length * 0.03)] * this.scene.quantization.xyz.scale_m : -2.0;
  }
}
