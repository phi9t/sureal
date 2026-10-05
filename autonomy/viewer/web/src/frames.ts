/** Coordinate conventions: Waymo (x forward, y left, z up) <-> three.js (y up, -z forward). */
import * as THREE from "three";

/** three = THREE_FROM_WAYMO * waymo. A proper rotation: headings and winding survive. */
export const THREE_FROM_WAYMO = new THREE.Matrix4().set(
  0, -1, 0, 0,
  0, 0, 1, 0,
  -1, 0, 0, 0,
  0, 0, 0, 1,
);

/** Waymo camera frame (+x out of lens, +y left, +z up) from a three camera frame (-z forward, +y up). */
export const CAM_AXES = new THREE.Matrix4().set(
  0, 0, -1, 0,
  -1, 0, 0, 0,
  0, 1, 0, 0,
  0, 0, 0, 1,
);

/** Row-major 16-element list (as stored by the exporter) -> Matrix4. */
export function mat4FromRowMajor(a: ArrayLike<number>): THREE.Matrix4 {
  return new THREE.Matrix4().set(
    a[0], a[1], a[2], a[3],
    a[4], a[5], a[6], a[7],
    a[8], a[9], a[10], a[11],
    a[12], a[13], a[14], a[15],
  );
}

export interface Intrinsics {
  f_u: number;
  f_v: number;
  c_u: number;
  c_v: number;
}

/** Perspective camera whose projection is built exactly from pinhole intrinsics (off-centre principal point). */
export class WaymoCamera extends THREE.PerspectiveCamera {
  private frustum: { l: number; r: number; t: number; b: number } | undefined;
  constructor() {
    super(60, 1.5, 0.5, 400);
    this.matrixAutoUpdate = false;
  }
  setIntrinsics(k: Intrinsics, width: number, height: number, near = 0.5, far = 400): void {
    this.near = near;
    this.far = far;
    this.frustum = {
      l: (-k.c_u / k.f_u) * near,
      r: ((width - k.c_u) / k.f_u) * near,
      t: (k.c_v / k.f_v) * near,
      b: (-(height - k.c_v) / k.f_v) * near,
    };
    this.fov = THREE.MathUtils.radToDeg(2 * Math.atan(height / 2 / k.f_v));
    this.aspect = width / height;
    this.updateProjectionMatrix();
  }
  override updateProjectionMatrix(): void {
    const f = this.frustum;
    if (!f) {
      super.updateProjectionMatrix();
      return;
    }
    this.projectionMatrix.makePerspective(f.l, f.r, f.t, f.b, this.near, this.far);
    this.projectionMatrixInverse.copy(this.projectionMatrix).invert();
  }
}

/** Ray direction (Waymo camera frame) for pixel (u, v), ignoring distortion. */
export function pixelRay(k: Intrinsics, u: number, v: number): THREE.Vector3 {
  return new THREE.Vector3(1, -(u - k.c_u) / k.f_u, -(v - k.c_v) / k.f_v);
}
