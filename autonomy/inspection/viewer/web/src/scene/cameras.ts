/** Camera frusta and textured image planes at the per-image vehicle pose. */
import * as THREE from "three";
import type { Scene } from "../data/bundle";
import type { FrameData } from "../data/loader";
import { mat4FromRowMajor, pixelRay } from "../frames";
import { hexToRgb } from "../palettes";
import type { ViewerState } from "../state";

const CAMERA_TINT: Record<number, string> = { 1: "#e0f7fa", 2: "#4fc3f7", 3: "#ffb74d", 4: "#ba68c8", 5: "#81c784" };

interface CamNode {
  name: number;
  group: THREE.Group;
  frustum: THREE.LineSegments;
  plane: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  texture: THREE.Texture | null;
  extrinsic: THREE.Matrix4;
  depth: number;
}

export class Cameras {
  group = new THREE.Group();
  private nodes = new Map<number, CamNode>();
  private lastFrame = -1;

  constructor(private scene: Scene) {
    this.group.name = "cameras";
    for (const [k, cal] of Object.entries(scene.cameras)) {
      const name = Number(k);
      const group = new THREE.Group();
      group.matrixAutoUpdate = false;
      const tint = new THREE.Color(...hexToRgb(CAMERA_TINT[name] ?? "#ffffff"));
      const frustum = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: tint, transparent: true, opacity: 0.8 }));
      const plane = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.85, side: THREE.DoubleSide, toneMapped: false, depthWrite: false }));
      plane.renderOrder = 2;
      group.add(frustum, plane);
      this.group.add(group);
      const node: CamNode = { name, group, frustum, plane, texture: null, extrinsic: mat4FromRowMajor(cal.vehicle_from_camera), depth: -1 };
      this.nodes.set(name, node);
      this.rebuild(node, 6);
    }
  }

  private rebuild(node: CamNode, depth: number): void {
    if (node.depth === depth) return;
    node.depth = depth;
    const cal = this.scene.cameras[String(node.name)];
    const k = cal.intrinsics;
    const W = cal.width, H = cal.height;
    const corners = [pixelRay(k, 0, 0), pixelRay(k, W, 0), pixelRay(k, W, H), pixelRay(k, 0, H)].map((r) => r.multiplyScalar(depth));
    const o = new THREE.Vector3();
    const fp: number[] = [];
    for (let i = 0; i < 4; i++) {
      const a = corners[i], b = corners[(i + 1) % 4];
      fp.push(o.x, o.y, o.z, a.x, a.y, a.z, a.x, a.y, a.z, b.x, b.y, b.z);
    }
    node.frustum.geometry.dispose();
    node.frustum.geometry = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(fp, 3));
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(corners.flatMap((c) => [c.x, c.y, c.z]), 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
    g.setIndex([0, 1, 2, 0, 2, 3]);
    node.plane.geometry.dispose();
    node.plane.geometry = g;
  }

  update(state: ViewerState, frame: number, data: FrameData | undefined): void {
    const meta = this.scene.frames[frame];
    for (const node of this.nodes.values()) {
      this.rebuild(node, state.planeDepth);
      const cam = meta.cameras[String(node.name)];
      const pov = state.rig === "pov" && state.povCamera === node.name;
      node.group.visible = !!cam && (state.showFrusta || state.showPlanes);
      node.frustum.visible = state.showFrusta && !pov;
      node.plane.visible = state.showPlanes && !!node.texture;
      node.plane.material.opacity = pov ? 0.3 : state.planeOpacity;
      if (!cam) continue;
      node.group.matrix.copy(mat4FromRowMajor(cam.world_from_vehicle)).multiply(node.extrinsic);
      node.group.matrixWorldNeedsUpdate = true;
      if (frame !== this.lastFrame) {
        const bitmap = data?.images.get(node.name);
        if (bitmap) {
          if (!node.texture) {
            node.texture = new THREE.Texture(bitmap);
            node.texture.colorSpace = THREE.SRGBColorSpace;
            node.texture.flipY = false;
            node.texture.minFilter = THREE.LinearFilter;
            node.texture.generateMipmaps = false;
            node.plane.material.map = node.texture;
            node.plane.material.needsUpdate = true;
          } else {
            node.texture.image = bitmap;
          }
          node.texture.needsUpdate = true;
        }
      }
    }
    if (data) this.lastFrame = frame;
  }
}
