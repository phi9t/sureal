/** Camera rigs: orbit, follow-ego, bird's-eye orthographic, and sensor point of view. */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Scene } from "../data/bundle";
import { CAM_AXES, mat4FromRowMajor, THREE_FROM_WAYMO, WaymoCamera } from "../frames";
import type { Rig } from "../state";

export class Rigs {
  perspective = new THREE.PerspectiveCamera(55, 1.5, 0.3, 1200);
  ortho = new THREE.OrthographicCamera(-50, 50, 50, -50, 0.1, 600);
  pov = new WaymoCamera();
  controls: OrbitControls;
  active: THREE.Camera;
  mode: Rig = "orbit";
  private lastEgo = new THREE.Vector3();
  private lastYaw = 0;
  private smoothEgo = new THREE.Vector3();
  private smoothYaw = 0;
  private bevZoom = 1;
  private followInit = false;

  constructor(private scene: Scene, canvas: HTMLCanvasElement) {
    this.controls = new OrbitControls(this.perspective, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.maxPolarAngle = Math.PI * 0.495;
    this.controls.minDistance = 2;
    this.controls.maxDistance = 500;
    this.perspective.position.set(-22, 12, 22);
    this.active = this.perspective;
    canvas.addEventListener("wheel", (e) => {
      if (this.mode === "bev") {
        this.bevZoom = THREE.MathUtils.clamp(this.bevZoom * Math.exp(-e.deltaY * 0.0015), 0.15, 8);
        e.preventDefault();
      }
    }, { passive: false });
  }

  resize(w: number, h: number): void {
    this.perspective.aspect = w / h;
    this.perspective.updateProjectionMatrix();
    const a = w / h;
    this.ortho.left = -60 * a;
    this.ortho.right = 60 * a;
    this.ortho.top = 60;
    this.ortho.bottom = -60;
    this.ortho.updateProjectionMatrix();
  }

  setMode(mode: Rig, povCamera: number, egoWorld: THREE.Vector3, yaw: number): void {
    if (mode === this.mode && mode !== "pov") return;
    this.mode = mode;
    this.controls.enabled = mode === "orbit" || mode === "follow";
    if (mode === "orbit" || mode === "follow") {
      this.active = this.perspective;
      if (mode === "follow") {
        this.followInit = false;
        this.smoothEgo.copy(egoWorld);
        this.smoothYaw = yaw;
      }
    } else if (mode === "bev") {
      this.active = this.ortho;
    } else {
      this.active = this.pov;
      const cal = this.scene.cameras[String(povCamera)];
      if (cal) this.pov.setIntrinsics(cal.intrinsics, cal.width, cal.height, 0.5, 400);
    }
  }

  /** egoWaymo/yaw: ego position in Waymo world and its heading. */
  update(dt: number, frame: number, povCamera: number, egoWaymo: THREE.Vector3, yaw: number): void {
    const ego = egoWaymo.clone().applyMatrix4(THREE_FROM_WAYMO);
    if (this.mode === "orbit") {
      this.controls.update();
    } else if (this.mode === "follow") {
      const k = 1 - Math.exp(-dt / 0.22);
      if (!this.followInit) {
        this.followInit = true;
        this.smoothEgo.copy(ego);
        this.smoothYaw = yaw;
        this.lastEgo.copy(ego);
        this.lastYaw = yaw;
        const target = ego.clone().add(new THREE.Vector3(0, 1.2, 0));
        const back = new THREE.Vector3(-Math.cos(yaw), 0, Math.sin(yaw)).multiplyScalar(-1); // waymo forward in three: (-sin? ) computed below
        void back;
        // Waymo forward (cos yaw, sin yaw, 0) -> three (-sin yaw, 0, -cos yaw).
        const fwd = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
        this.perspective.position.copy(target).addScaledVector(fwd, -20).add(new THREE.Vector3(0, 9, 0));
        this.controls.target.copy(target);
      } else {
        this.smoothEgo.lerp(ego, k);
        let dyaw = yaw - this.smoothYaw;
        dyaw = Math.atan2(Math.sin(dyaw), Math.cos(dyaw));
        this.smoothYaw += dyaw * k;
        const delta = this.smoothEgo.clone().sub(this.lastEgo);
        const rot = this.smoothYaw - this.lastYaw;
        // Move target with the ego and rotate the camera offset with the heading (three y-up: yaw about +y is -waymo yaw).
        const offset = this.perspective.position.clone().sub(this.controls.target);
        offset.applyAxisAngle(new THREE.Vector3(0, 1, 0), rot);
        this.controls.target.add(delta);
        this.perspective.position.copy(this.controls.target).add(offset);
        this.lastEgo.copy(this.smoothEgo);
        this.lastYaw = this.smoothYaw;
      }
      this.controls.update();
    } else if (this.mode === "bev") {
      const fwd = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
      this.ortho.position.copy(ego).add(new THREE.Vector3(0, 200, 0)).addScaledVector(fwd, 12);
      this.ortho.up.copy(fwd);
      this.ortho.lookAt(ego.clone().addScaledVector(fwd, 12));
      this.ortho.zoom = this.bevZoom;
      this.ortho.updateProjectionMatrix();
      this.ortho.updateMatrixWorld();
    } else {
      const cam = this.scene.frames[frame].cameras[String(povCamera)];
      const cal = this.scene.cameras[String(povCamera)];
      if (cam && cal) {
        this.pov.matrixWorld.copy(THREE_FROM_WAYMO).multiply(mat4FromRowMajor(cam.world_from_vehicle)).multiply(mat4FromRowMajor(cal.vehicle_from_camera)).multiply(CAM_AXES);
        this.pov.matrix.copy(this.pov.matrixWorld);
        this.pov.matrixWorldInverse.copy(this.pov.matrixWorld).invert();
        this.pov.matrix.decompose(this.pov.position, this.pov.quaternion, this.pov.scale);
      }
    }
  }

  snapToEgo(egoWaymo: THREE.Vector3): void {
    const ego = egoWaymo.clone().applyMatrix4(THREE_FROM_WAYMO);
    const offset = this.perspective.position.clone().sub(this.controls.target);
    this.controls.target.copy(ego).add(new THREE.Vector3(0, 1.2, 0));
    this.perspective.position.copy(this.controls.target).add(offset);
  }

  get isOrtho(): boolean {
    return this.mode === "bev";
  }
}
