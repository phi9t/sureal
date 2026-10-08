import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";

export class PostFX {
  composer: EffectComposer;
  renderPass: RenderPass;
  bloom: UnrealBloomPass;
  constructor(public renderer: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera) {
    this.composer = new EffectComposer(renderer);
    this.renderPass = new RenderPass(scene, camera);
    this.bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.45, 0.55, 0.82);
    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
  }
  setCamera(camera: THREE.Camera): void {
    this.renderPass.camera = camera;
  }
  setSize(w: number, h: number, dpr: number): void {
    this.composer.setPixelRatio(dpr);
    this.composer.setSize(w, h);
    this.bloom.resolution.set(Math.max(1, Math.floor(w / 2)), Math.max(1, Math.floor(h / 2)));
  }
  render(): void {
    this.composer.render();
  }
}
