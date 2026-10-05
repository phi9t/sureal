/** 3D human keypoint skeletons from lidar_hkp (vehicle frame of the frame). */
import * as THREE from "three";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import type { FrameAnnotations, Scene } from "../data/bundle";
import { mat4FromRowMajor } from "../frames";
import type { ViewerState } from "../state";

const LEFT = new Set([5, 6, 7, 8, 9, 10]);

export class Keypoints {
  group = new THREE.Group();
  private lines: LineSegments2;
  private joints: THREE.InstancedMesh;
  private mat: LineMaterial;
  private lastFrame = -1;
  count = 0;

  constructor(private scene: Scene, resolution: THREE.Vector2) {
    this.group.name = "keypoints";
    this.group.matrixAutoUpdate = false;
    this.mat = new LineMaterial({ vertexColors: true, linewidth: 2.5, worldUnits: false, resolution, transparent: true, opacity: 0.95 });
    this.lines = new LineSegments2(new LineSegmentsGeometry(), this.mat);
    this.lines.frustumCulled = false;
    this.joints = new THREE.InstancedMesh(new THREE.SphereGeometry(0.045, 10, 8), new THREE.MeshBasicMaterial({ color: new THREE.Color("#ffffff").multiplyScalar(1.5), toneMapped: false }), 512);
    this.joints.frustumCulled = false;
    this.joints.count = 0;
    this.group.add(this.lines, this.joints);
  }

  setResolution(res: THREE.Vector2): void {
    this.mat.resolution.copy(res);
  }

  update(state: ViewerState, frame: number, ann: FrameAnnotations | undefined): void {
    this.group.visible = state.showKeypoints;
    if (!ann || frame === this.lastFrame) return;
    this.lastFrame = frame;
    this.group.matrix.copy(mat4FromRowMajor(this.scene.frames[frame].world_from_vehicle));
    this.group.matrixWorldNeedsUpdate = true;
    const pos: number[] = [];
    const col: number[] = [];
    const m = new THREE.Matrix4();
    let j = 0;
    this.count = 0;
    const warm = [1.6, 0.9, 0.4], cool = [0.5, 1.2, 1.7], mid = [1.5, 1.5, 1.5];
    for (const pts of Object.values(ann.lidar_keypoints)) {
      const byType = new Map<number, [number, number, number, number]>();
      for (const [t, x, y, z, occ] of pts) byType.set(t, [x, y, z, occ]);
      this.count++;
      for (const [a, b] of this.scene.palettes.keypoint_edges) {
        const pa = byType.get(a), pb = byType.get(b);
        if (!pa || !pb) continue;
        const c = LEFT.has(a) && LEFT.has(b) ? warm : !LEFT.has(a) && !LEFT.has(b) && a >= 13 && b >= 13 ? cool : mid;
        const k = pa[3] || pb[3] ? 0.45 : 1;
        pos.push(pa[0], pa[1], pa[2], pb[0], pb[1], pb[2]);
        col.push(c[0] * k, c[1] * k, c[2] * k, c[0] * k, c[1] * k, c[2] * k);
      }
      for (const [x, y, z] of byType.values()) {
        if (j >= 512) break;
        m.makeTranslation(x, y, z);
        this.joints.setMatrixAt(j++, m);
      }
    }
    this.joints.count = j;
    this.joints.instanceMatrix.needsUpdate = true;
    this.lines.geometry.dispose();
    const g = new LineSegmentsGeometry();
    g.setPositions(pos.length ? pos : [0, 0, 0, 0, 0, 0]);
    g.setColors(col.length ? col : [0, 0, 0, 0, 0, 0]);
    this.lines.geometry = g;
    this.lines.visible = pos.length > 0;
  }
}
