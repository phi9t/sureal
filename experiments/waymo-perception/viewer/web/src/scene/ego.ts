/** Ego trajectory ribbon with a time pulse, the ego footprint and a fading ground grid. */
import * as THREE from "three";
import type { Scene } from "../data/bundle";
import { mat4FromRowMajor } from "../frames";
import type { ViewerState } from "../state";

const RIBBON_VERT = `
in float t;
uniform float uNow;
out float vT;
out float vD;
void main() {
  vT = t;
  vD = t - uNow;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;
const RIBBON_FRAG = `
in float vT;
in float vD;
uniform vec3 uPast;
uniform vec3 uFuture;
uniform vec3 uPulse;
out vec4 fragColor;
void main() {
  float ahead = step(0.0, vD);
  vec3 base = mix(uPast, uFuture, ahead);
  float pulse = exp(-abs(vD) * 90.0);
  vec3 col = mix(base, uPulse * 1.5, pulse);
  float a = mix(0.55, 0.25, ahead) + pulse * 0.6;
  fragColor = vec4(col, a);
}`;

const GRID_VERT = `
out vec2 vXY;
void main() {
  vXY = position.xy;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;
const GRID_FRAG = `
in vec2 vXY;
uniform vec2 uCenter;
uniform float uRadius;
out vec4 fragColor;
void main() {
  vec2 g = abs(fract(vXY / 10.0 - 0.5) - 0.5) / fwidth(vXY / 10.0);
  float line = 1.0 - min(min(g.x, g.y), 1.0);
  vec2 g2 = abs(fract(vXY / 2.0 - 0.5) - 0.5) / fwidth(vXY / 2.0);
  float minor = (1.0 - min(min(g2.x, g2.y), 1.0)) * 0.35;
  float d = length(vXY - uCenter) / uRadius;
  float fade = exp(-d * d * 2.5);
  float a = max(line, minor) * fade * 0.35;
  fragColor = vec4(vec3(0.45, 0.6, 0.75), a);
}`;

export class Ego {
  group = new THREE.Group();
  private ribbonMat: THREE.ShaderMaterial;
  private gridMat: THREE.ShaderMaterial;
  private grid: THREE.Mesh;
  private footprint: THREE.LineSegments;
  private marker: THREE.Group;
  poses: THREE.Matrix4[];
  positions: THREE.Vector3[];

  constructor(private scene: Scene) {
    this.group.name = "ego";
    this.poses = scene.frames.map((f) => mat4FromRowMajor(f.world_from_vehicle));
    this.positions = this.poses.map((m) => new THREE.Vector3().setFromMatrixPosition(m));
    const n = this.poses.length;
    const verts: number[] = [];
    const ts: number[] = [];
    const idx: number[] = [];
    const y = new THREE.Vector3();
    for (let i = 0; i < n; i++) {
      const p = this.positions[i];
      y.setFromMatrixColumn(this.poses[i], 1).normalize().multiplyScalar(0.55);
      verts.push(p.x + y.x, p.y + y.y, p.z + y.z - 1.6, p.x - y.x, p.y - y.y, p.z - y.z - 1.6);
      ts.push(i / (n - 1), i / (n - 1));
      if (i < n - 1) idx.push(2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 1, 2 * i + 3, 2 * i + 2);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    g.setAttribute("t", new THREE.Float32BufferAttribute(ts, 1));
    g.setIndex(idx);
    this.ribbonMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: RIBBON_VERT,
      fragmentShader: RIBBON_FRAG,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      uniforms: {
        uNow: { value: 0 },
        uPast: { value: new THREE.Color("#2196f3") },
        uFuture: { value: new THREE.Color("#455a64") },
        uPulse: { value: new THREE.Color("#4dd0e1") },
      },
    });
    const ribbon = new THREE.Mesh(g, this.ribbonMat);
    ribbon.frustumCulled = false;
    ribbon.renderOrder = 1;
    this.group.add(ribbon);

    this.gridMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: GRID_VERT,
      fragmentShader: GRID_FRAG,
      transparent: true,
      depthWrite: false,
      uniforms: { uCenter: { value: new THREE.Vector2() }, uRadius: { value: 90 } },
    });
    this.grid = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), this.gridMat);
    this.grid.frustumCulled = false;
    this.grid.renderOrder = -1;
    this.group.add(this.grid);

    // Ego footprint: a 4.9 x 2.1 m outline in the vehicle frame (origin near the rear axle).
    const fp = [[-1.2, -1.05], [3.7, -1.05], [3.7, 1.05], [-1.2, 1.05]];
    const fpv: number[] = [];
    for (let i = 0; i < 4; i++) {
      const a = fp[i], b = fp[(i + 1) % 4];
      fpv.push(a[0], a[1], -1.5, b[0], b[1], -1.5);
    }
    fpv.push(3.7, 0, -1.5, 4.6, 0, -1.5, 3.7, -0.5, -1.5, 4.6, 0, -1.5, 3.7, 0.5, -1.5, 4.6, 0, -1.5);
    this.footprint = new THREE.LineSegments(
      new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(fpv, 3)),
      new THREE.LineBasicMaterial({ color: new THREE.Color("#4dd0e1").multiplyScalar(1.8), transparent: true, opacity: 0.9, toneMapped: false }),
    );
    this.marker = new THREE.Group();
    this.marker.matrixAutoUpdate = false;
    this.marker.add(this.footprint);
    this.group.add(this.marker);
  }

  setGroundZ(z: number, frame: number): void {
    // Grid sits at the ground height of the current pose (vehicle-frame z -> world z).
    const p = new THREE.Vector3(0, 0, z).applyMatrix4(this.poses[frame]);
    this.grid.position.set(0, 0, p.z);
  }

  update(state: ViewerState, frame: number): void {
    const n = this.scene.frames.length;
    this.ribbonMat.uniforms.uNow.value = frame / Math.max(1, n - 1);
    this.marker.matrix.copy(this.poses[frame]);
    this.marker.matrixWorldNeedsUpdate = true;
    this.marker.visible = state.showEgo && !(state.rig === "pov");
    this.group.children[0].visible = state.showEgo;
    this.grid.visible = state.showGrid;
    const p = this.positions[frame];
    this.gridMat.uniforms.uCenter.value.set(p.x, p.y);
    this.grid.position.x = 0;
    this.grid.position.y = 0;
  }

  yawAt(frame: number): number {
    const x = new THREE.Vector3().setFromMatrixColumn(this.poses[frame], 0);
    return Math.atan2(x.y, x.x);
  }
}
